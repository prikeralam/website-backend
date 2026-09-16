from rest_framework.routers import DefaultRouter

from .views import PublicationViewSet

router = DefaultRouter()
router.register(r"publications", PublicationViewSet, basename="publication")

urlpatterns = router.urls
