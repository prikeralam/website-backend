from django.db import transaction
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenBlacklistView, TokenObtainPairView

from .models import AuditLog, Role, User
from .serializers import (
    AuditLogSerializer,
    MyRoleSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RoleUpdateSerializer,
    UserCreateSerializer,
    UserSerializer,
)
from .services import audit, guard_admin_lockout, send_password_email
from .throttles import LoginRateThrottle, PasswordResetRateThrottle

MODULE_TAG = "Module H — Users & Roles"


@extend_schema(tags=[MODULE_TAG])
class LoginView(TokenObtainPairView):
    """Exchanges a username and password for an access/refresh token pair.

    Throttled per username: the sixth attempt within a minute answers 429.
    """

    throttle_classes = [LoginRateThrottle]


@extend_schema(tags=[MODULE_TAG])
class LogoutView(TokenBlacklistView):
    """Signs out: blacklists the refresh token so it can no longer mint access tokens."""


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == "admin")


class MyRoleView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=[MODULE_TAG], responses=MyRoleSerializer)
    def get(self, request):
        serializer = MyRoleSerializer(request.user)
        return Response(serializer.data)


class UserRoleUpdateView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(tags=[MODULE_TAG], request=RoleUpdateSerializer, responses=MyRoleSerializer)
    def patch(self, request, pk):
        serializer = RoleUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_role = serializer.validated_data["role"]

        try:
            target_user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        old_role = target_user.role
        if old_role == Role.ADMIN and new_role != Role.ADMIN:
            guard_admin_lockout(request.user, target_user)
        target_user.role = new_role
        target_user.save(update_fields=["role"])

        audit(request.user, "role_change", target_user, old_role=old_role, new_role=new_role)

        return Response(MyRoleSerializer(target_user).data)


@extend_schema(tags=[MODULE_TAG])
@extend_schema_view(
    list=extend_schema(
        parameters=[OpenApiParameter("q", str, description="Matches username, email, first or last name")]
    )
)
class UserViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Admin user management. Users are deactivated, never deleted: content keeps its author."""

    queryset = User.objects.order_by("username")
    permission_classes = [IsAuthenticated, IsAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["role", "is_active"]
    http_method_names = ["get", "post", "patch", "head", "options"]
    # Keeps /users/me/ and /users/me/role/ out of the `{id}` routes.
    lookup_value_regex = r"\d+"

    def get_serializer_class(self):
        return UserCreateSerializer if self.action == "create" else UserSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        term = self.request.query_params.get("q", "").strip()
        if term:
            queryset = queryset.filter(
                Q(username__icontains=term)
                | Q(email__icontains=term)
                | Q(first_name__icontains=term)
                | Q(last_name__icontains=term)
            )
        return queryset

    @transaction.atomic
    def perform_create(self, serializer):
        # Sent inside the transaction: if the invite can't be sent, no account is left without a way in.
        invite = not serializer.validated_data.get("password")
        user = serializer.save()
        audit(self.request.user, "user_create", user, role=user.role, invite=invite)
        if invite:
            send_password_email(user)

    def perform_update(self, serializer):
        before = {field: getattr(serializer.instance, field) for field in serializer.validated_data}
        user = serializer.save()
        changes = {field: [old, getattr(user, field)] for field, old in before.items() if old != getattr(user, field)}
        if changes:
            audit(self.request.user, "user_update", user, changes=changes)

    def set_active(self, request, active):
        user = self.get_object()
        if user.is_active != active:
            if not active:
                guard_admin_lockout(request.user, user)
            user.is_active = active
            user.save(update_fields=["is_active"])
            audit(request.user, "user_reactivate" if active else "user_deactivate", user)
        return Response(UserSerializer(user).data)

    @extend_schema(request=None, responses=UserSerializer)
    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        """Blocks sign-in and invalidates the user's existing tokens on their next use."""
        return self.set_active(request, False)

    @extend_schema(request=None, responses=UserSerializer)
    @action(detail=True, methods=["post"])
    def reactivate(self, request, pk=None):
        return self.set_active(request, True)

    @extend_schema(request=None, responses={204: None})
    @action(detail=True, methods=["post"], url_path="send-password-reset")
    def send_password_reset(self, request, pk=None):
        """Emails a set-password link: a fresh invite if the user never set a password, else a reset."""
        user = self.get_object()
        if not user.is_active:
            return Response({"detail": "Reactivate the user first."}, status=status.HTTP_400_BAD_REQUEST)
        send_password_email(user)
        audit(request.user, "password_reset_sent", user)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=[MODULE_TAG])
class MeView(APIView):
    """The signed-in user's own profile. `must_change_password` tells the frontend to force a change."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses=UserSerializer)
    def get(self, request):
        return Response(UserSerializer(request.user).data)

    @extend_schema(request=UserSerializer, responses=UserSerializer)
    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


@extend_schema(tags=[MODULE_TAG])
class MyPasswordView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=PasswordChangeSerializer, responses={204: None})
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=[MODULE_TAG])
class PasswordResetView(APIView):
    """Emails a reset link. Always answers 204, so it can't reveal which emails have accounts."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PasswordResetRateThrottle]

    @extend_schema(request=PasswordResetRequestSerializer, responses={204: None})
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(email__iexact=serializer.validated_data["email"], is_active=True).first()
        if user is not None:
            send_password_email(user)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=[MODULE_TAG])
class PasswordResetConfirmView(APIView):
    """Sets a new password from an emailed reset or invite link. Each link works once."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(request=PasswordResetConfirmSerializer, responses={204: None})
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        user.set_password(serializer.validated_data["new_password"])
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=[MODULE_TAG])
class AuditLogListView(ListAPIView):
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["module", "actor"]
