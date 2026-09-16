from django.urls import path

from .views import AuditLogListView, MyRoleView, UserRoleUpdateView

urlpatterns = [
    path("users/me/role/", MyRoleView.as_view(), name="my-role"),
    path("users/<int:pk>/role/", UserRoleUpdateView.as_view(), name="user-role-update"),
    path("audit-log/", AuditLogListView.as_view(), name="audit-log-list"),
]
