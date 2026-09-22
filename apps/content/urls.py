from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ContentBlockViewSet,
    DocumentViewSet,
    LatestUpdatesView,
    PersonProfileViewSet,
    TestimonialViewSet,
)

router = DefaultRouter()
router.register(r"content-blocks", ContentBlockViewSet, basename="content-block")
router.register(r"testimonials", TestimonialViewSet, basename="testimonial")
router.register(r"people", PersonProfileViewSet, basename="person")
router.register(r"documents", DocumentViewSet, basename="document")

urlpatterns = [
    path("updates/latest/", LatestUpdatesView.as_view(), name="latest-updates"),
] + router.urls
