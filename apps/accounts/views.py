from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenBlacklistView, TokenObtainPairView

from .models import AuditLog, User
from .serializers import AuditLogSerializer, MyRoleSerializer, RoleUpdateSerializer
from .throttles import LoginRateThrottle

MODULE_TAG = "Module H — Users & Roles"


@extend_schema(tags=[MODULE_TAG])
class LoginView(TokenObtainPairView):
    """Exchanges a username and password for an access/refresh token pair.

    Throttled per username: the sixth attempt within a minute answers 429.
    """

    throttle_classes = [LoginRateThrottle]


@extend_schema(tags=[MODULE_TAG])
class LogoutView(TokenBlacklistView):
    """Signs out: blacklists the refresh token so it can no longer mint access tokens."""


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == "admin")


class MyRoleView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=[MODULE_TAG], responses=MyRoleSerializer)
    def get(self, request):
        serializer = MyRoleSerializer(request.user)
        return Response(serializer.data)


class UserRoleUpdateView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(tags=[MODULE_TAG], request=RoleUpdateSerializer, responses=MyRoleSerializer)
    def patch(self, request, pk):
        serializer = RoleUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_role = serializer.validated_data["role"]

        try:
            target_user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        old_role = target_user.role
        target_user.role = new_role
        target_user.save(update_fields=["role"])

        AuditLog.objects.create(
            actor=request.user,
            module="accounts",
            action="role_change",
            target=f"user:{target_user.pk}",
            metadata={"old_role": old_role, "new_role": new_role},
        )

        return Response(MyRoleSerializer(target_user).data)


@extend_schema(tags=[MODULE_TAG])
class AuditLogListView(ListAPIView):
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["module", "actor"]
