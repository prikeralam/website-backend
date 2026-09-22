from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import SubThemeViewSet, ThemeViewSet

router = DefaultRouter()
router.register(r"themes", ThemeViewSet, basename="theme")

subtheme_list = SubThemeViewSet.as_view({"get": "list", "post": "create"})
subtheme_detail = SubThemeViewSet.as_view(
    {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}
)

urlpatterns = [
    path("themes/<int:theme_pk>/subthemes/", subtheme_list, name="subtheme-list"),
    path("themes/<int:theme_pk>/subthemes/<int:pk>/", subtheme_detail, name="subtheme-detail"),
] + router.urls
