from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers

from .models import AuditLog, Purpose, Role, User
from .tokens import email_verification_token


def check_password_strength(field, password, user):
    try:
        validate_password(password, user=user)
    except DjangoValidationError as error:
        raise serializers.ValidationError({field: error.messages}) from error


class MyRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "role"]


class RoleUpdateSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=Role.choices)


class UserSerializer(serializers.ModelSerializer):
    download_count = serializers.SerializerMethodField()

    def get_download_count(self, obj) -> int:
        # The admin list annotates it; a single profile (e.g. /users/me/) counts on demand.
        annotated = getattr(obj, "download_count", None)
        return annotated if annotated is not None else obj.dataset_downloads.count()

    """A user as admins see them, and as a user sees themselves at /users/me/.

    Only contact details and sign-up answers are writable here: the role has its own audited endpoint,
    `is_active` its deactivate/reactivate actions, passwords their own flows, and `email_verified` changes
    only through a confirmation link.
    """

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "first_name", "last_name", "role",
            "is_active", "must_change_password", "date_joined", "last_login",
            "email_verified", "organisation", "purpose", "newsletter_opt_in", "download_count",
        ]
        read_only_fields = [
            "id", "username", "role", "is_active", "must_change_password", "date_joined", "last_login",
            "email_verified",
        ]
        extra_kwargs = {"email": {"required": True, "allow_blank": False}}

    def validate_email(self, value):
        # Password resets are requested by email, so an address must identify one account.
        taken = User.objects.filter(email__iexact=value)
        if self.instance is not None:
            taken = taken.exclude(pk=self.instance.pk)
        if taken.exists():
            raise serializers.ValidationError("Another account already uses this email.")
        return value


class UserCreateSerializer(UserSerializer):
    """Creates an account with either a temporary password or, when none is given, an emailed invite."""

    password = serializers.CharField(write_only=True, required=False, style={"input_type": "password"})

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ["password"]
        read_only_fields = ["id", "is_active", "must_change_password", "date_joined", "last_login"]
        extra_kwargs = {"email": {"required": True, "allow_blank": False}, "role": {"required": True}}

    def validate(self, attrs):
        password = attrs.get("password")
        if password:
            candidate = User(**{k: v for k, v in attrs.items() if k != "password"})
            check_password_strength("password", password, candidate)
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        # An admin vouches for the address, and the invite or reset link proves it anyway.
        user = User(**validated_data, email_verified=True)
        if password:
            user.set_password(password)
            user.must_change_password = True
        else:
            user.set_unusable_password()
        user.save()
        return user


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    new_password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_old_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate_new_password(self, value):
        validate_password(value, user=self.context["request"].user)
        return value


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, attrs):
        try:
            user = User.objects.get(pk=force_str(urlsafe_base64_decode(attrs["uid"])), is_active=True)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            user = None
        if user is None or not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError({"detail": "This link is invalid or has expired."})
        check_password_strength("new_password", attrs["new_password"], user)
        attrs["user"] = user
        return attrs


class RegisterSerializer(serializers.Serializer):
    """A visitor's own sign-up. The email doubles as the username; `next` is where the confirmation link returns."""

    email = serializers.EmailField(max_length=150)
    password = serializers.CharField(write_only=True, max_length=128, style={"input_type": "password"})
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    organisation = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    purpose = serializers.ChoiceField(choices=Purpose.choices)
    newsletter_opt_in = serializers.BooleanField(required=False, default=False)
    next = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")

    def validate(self, attrs):
        attrs["email"] = attrs["email"].strip().lower()
        candidate = User(username=attrs["email"], email=attrs["email"], first_name=attrs["first_name"])
        check_password_strength("password", attrs["password"], candidate)
        return attrs


class VerifyEmailSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()

    def validate(self, attrs):
        try:
            user = User.objects.get(pk=force_str(urlsafe_base64_decode(attrs["uid"])), is_active=True)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            user = None
        if user is None or not email_verification_token.check_token(user, attrs["token"]):
            raise serializers.ValidationError({"detail": "This link is invalid, has expired or has already been used."})
        attrs["user"] = user
        return attrs


class ResendVerificationSerializer(serializers.Serializer):
    next = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class AuditLogSerializer(serializers.ModelSerializer):
    actor = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = AuditLog
        fields = ["id", "actor", "module", "action", "target", "metadata", "timestamp"]
