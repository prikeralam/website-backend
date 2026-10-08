from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from apps.accounts.models import AuditLog
from apps.datarepo.views import IsStaffRole
from apps.workflow.permissions import CanSubmitDraft
from apps.workflow.views import WorkflowViewSetMixin

from .models import Application, JobOpening
from .serializers import ApplicationSerializer, ApplicationSubmissionSerializer, JobOpeningSerializer
from .services import notify_staff
from .throttles import ApplicationEmailRateThrottle, ApplicationGlobalRateThrottle

MODULE_TAG = "Module D — Careers & Applications"


@extend_schema(tags=[MODULE_TAG])
class JobOpeningViewSet(WorkflowViewSetMixin, ModelViewSet):
    queryset = JobOpening.objects.all()
    serializer_class = JobOpeningSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, CanSubmitDraft]
    lookup_field = "slug"


@extend_schema(tags=[MODULE_TAG])
class ApplicationSubmissionView(APIView):
    """The public application form (fellowships, internships and job openings), with a CV and an SOP."""

    permission_classes = [AllowAny]
    authentication_classes = []
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [ApplicationEmailRateThrottle, ApplicationGlobalRateThrottle]

    @extend_schema(
        request={"multipart/form-data": ApplicationSubmissionSerializer},
        responses={
            201: OpenApiResponse(description="Received."),
            400: OpenApiResponse(description="Invalid fields."),
            429: OpenApiResponse(description="Too many applications."),
        },
    )
    def post(self, request):
        serializer = ApplicationSubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # A filled honeypot is a bot: answer as if it worked, and keep nothing.
        if serializer.validated_data.pop("website", ""):
            return Response({"detail": "Received."}, status=status.HTTP_201_CREATED)
        application = serializer.save()
        notify_staff(application)
        return Response({"detail": "Received."}, status=status.HTTP_201_CREATED)


@extend_schema(tags=[MODULE_TAG])
class ApplicationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, GenericViewSet):
    """Staff read applications, open their files and mark them reviewed (or new again)."""

    queryset = Application.objects.select_related("job")
    serializer_class = ApplicationSerializer
    permission_classes = [IsStaffRole]
    filterset_fields = ["status", "kind"]
    http_method_names = ["get", "patch", "head", "options"]

    @extend_schema(
        parameters=[OpenApiParameter("document", str, enum=["cv", "sop"], location=OpenApiParameter.PATH)],
        responses={200: OpenApiResponse(description='{"file": "<short-lived URL>"}')},
    )
    @action(detail=True, methods=["get"], url_path=r"files/(?P<document>cv|sop)")
    def files(self, request, pk=None, document=None):
        """A link to the applicant's CV or SOP. On S3 it is presigned and expires; never stored on the page."""
        application = self.get_object()
        return Response({"file": request.build_absolute_uri(getattr(application, document).url)})

    def perform_update(self, serializer):
        previous = serializer.instance.status
        new = serializer.validated_data.get("status", previous)
        if new == previous:
            serializer.save()
            return
        reviewed = new == Application.Status.REVIEWED
        application = serializer.save(
            handled_at=timezone.now() if reviewed else None, handled_by=self.request.user if reviewed else None
        )
        AuditLog.objects.create(
            actor=self.request.user,
            module="careers",
            action="application_status",
            target=f"application:{application.pk}",
            metadata={"from": previous, "to": new},
        )
