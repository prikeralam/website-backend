"""
URL configuration for the PRI backend project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.utils import extend_schema
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .health import healthz

# SimpleJWT's views aren't ours to edit, so tag them for Swagger grouping by wrapping here.
_AUTH_TAG = extend_schema(tags=["Module H — Users & Roles"])
TokenObtainPairView = _AUTH_TAG(TokenObtainPairView)
TokenRefreshView = _AUTH_TAG(TokenRefreshView)

urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path("api/v1/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/v1/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.taxonomy.urls")),
    path("api/v1/", include("apps.content.urls")),
    path("api/v1/", include("apps.projects.urls")),
    path("api/v1/", include("apps.publications.urls")),
    path("api/v1/", include("apps.datarepo.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
