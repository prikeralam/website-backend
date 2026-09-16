from rest_framework import serializers

from .models import AuditLog, Role, User


class MyRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "role"]


class RoleUpdateSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=Role.choices)


class AuditLogSerializer(serializers.ModelSerializer):
    actor = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = AuditLog
        fields = ["id", "actor", "module", "action", "target", "metadata", "timestamp"]
