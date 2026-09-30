from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AccessRequestQueueView,
    AccessRequestReviewView,
    CollectionViewSet,
    DashboardViewSet,
    DatasetViewSet,
)

router = DefaultRouter()
router.register(r"datasets", DatasetViewSet, basename="dataset")
router.register(r"dashboards", DashboardViewSet, basename="dashboard")
router.register(r"collections", CollectionViewSet, basename="collection")

urlpatterns = [
    path("access-requests/", AccessRequestQueueView.as_view(), name="access-request-queue"),
    path("access-requests/<int:pk>/", AccessRequestReviewView.as_view(), name="access-request-review"),
] + router.urls
