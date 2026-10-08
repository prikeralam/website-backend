from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ApplicationSubmissionView, ApplicationViewSet, JobOpeningViewSet

router = DefaultRouter()
router.register(r"jobs", JobOpeningViewSet, basename="job")
router.register(r"applications", ApplicationViewSet, basename="application")

# The public form posts to `apply/`; `applications/` is the staff inbox.
urlpatterns = [path("apply/", ApplicationSubmissionView.as_view(), name="apply"), *router.urls]
