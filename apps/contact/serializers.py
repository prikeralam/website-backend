from rest_framework import serializers

from .models import ContactMessage


class ContactSubmissionSerializer(serializers.ModelSerializer):
    """What a visitor sends. `website` is a honeypot: the form hides it, so only bots fill it in."""

    website = serializers.CharField(required=False, allow_blank=True, write_only=True, max_length=200)

    class Meta:
        model = ContactMessage
        fields = ["category", "name", "email", "message", "website"]
        extra_kwargs = {"message": {"max_length": 5000}}

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Please enter your name.")
        return value

    def validate_message(self, value):
        value = value.strip()
        if len(value) < 10:
            raise serializers.ValidationError("Please write a little more (at least 10 characters).")
        return value


class ContactMessageSerializer(serializers.ModelSerializer):
    """A message as staff see it. Only `status` can be changed."""

    class Meta:
        model = ContactMessage
        fields = ["id", "category", "name", "email", "message", "status", "created_at", "handled_at", "handled_by"]
        read_only_fields = ["id", "category", "name", "email", "message", "created_at", "handled_at", "handled_by"]
