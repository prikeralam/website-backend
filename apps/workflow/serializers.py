from rest_framework import serializers

from .models import WorkflowStatus


class TransitionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=WorkflowStatus.choices)
