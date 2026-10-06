from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ContactMessageViewSet, ContactSubmissionView

router = DefaultRouter()
router.register(r"contact-messages", ContactMessageViewSet, basename="contact-message")

urlpatterns = [path("contact/", ContactSubmissionView.as_view(), name="contact"), *router.urls]
