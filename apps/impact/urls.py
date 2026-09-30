from rest_framework.routers import DefaultRouter

from .views import MentionViewSet, RecognitionViewSet

router = DefaultRouter()
router.register(r"mentions", MentionViewSet, basename="mention")
router.register(r"recognition", RecognitionViewSet, basename="recognition")

urlpatterns = router.urls
