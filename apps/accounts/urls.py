from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    AuditLogListView,
    MeView,
    MyPasswordView,
    MyRoleView,
    PasswordResetConfirmView,
    PasswordResetView,
    UserRoleUpdateView,
    UserViewSet,
)

router = SimpleRouter()
router.register("users", UserViewSet, basename="user")

urlpatterns = [
    path("users/me/", MeView.as_view(), name="me"),
    path("users/me/role/", MyRoleView.as_view(), name="my-role"),
    path("users/me/password/", MyPasswordView.as_view(), name="my-password"),
    path("users/<int:pk>/role/", UserRoleUpdateView.as_view(), name="user-role-update"),
    path("password-reset/", PasswordResetView.as_view(), name="password-reset"),
    path("password-reset/confirm/", PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
    path("audit-log/", AuditLogListView.as_view(), name="audit-log-list"),
    *router.urls,
]
