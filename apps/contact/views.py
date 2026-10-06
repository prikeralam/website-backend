from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

from apps.accounts.models import AuditLog
from apps.datarepo.views import IsStaffRole

from .models import ContactMessage
from .serializers import ContactMessageSerializer, ContactSubmissionSerializer
from .services import notify_staff
from .throttles import ContactEmailRateThrottle, ContactGlobalRateThrottle

MODULE_TAG = "Module G — Contact"


@extend_schema(tags=[MODULE_TAG])
class ContactSubmissionView(APIView):
    """The public contact form. Anyone may send a message; it is stored and emailed to PRI."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ContactEmailRateThrottle, ContactGlobalRateThrottle]

    @extend_schema(
        request=ContactSubmissionSerializer,
        responses={
            201: OpenApiResponse(description="Received."),
            400: OpenApiResponse(description="Invalid fields."),
            429: OpenApiResponse(description="Too many messages."),
        },
    )
    def post(self, request):
        serializer = ContactSubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # A filled honeypot is a bot: answer as if it worked, and keep nothing.
        if serializer.validated_data.pop("website", ""):
            return Response({"detail": "Received."}, status=status.HTTP_201_CREATED)
        message = serializer.save()
        notify_staff(message)
        return Response({"detail": "Received."}, status=status.HTTP_201_CREATED)


@extend_schema(tags=[MODULE_TAG])
class ContactMessageViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, GenericViewSet):
    """The inbox: editors and admins read messages and mark them handled (or new again)."""

    queryset = ContactMessage.objects.all()
    serializer_class = ContactMessageSerializer
    permission_classes = [IsStaffRole]
    filterset_fields = ["status", "category"]
    http_method_names = ["get", "patch", "head", "options"]

    def perform_update(self, serializer):
        previous = serializer.instance.status
        new = serializer.validated_data.get("status", previous)
        if new == previous:
            serializer.save()
            return
        handled = new == ContactMessage.Status.HANDLED
        message = serializer.save(
            handled_at=timezone.now() if handled else None, handled_by=self.request.user if handled else None
        )
        AuditLog.objects.create(
            actor=self.request.user,
            module="contact",
            action="contact_status",
            target=f"contact_message:{message.pk}",
            metadata={"from": previous, "to": new},
        )
