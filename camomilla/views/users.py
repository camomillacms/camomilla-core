from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.models import Permission
from django.db.models import Q
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from camomilla.permissions import CamomillaSuperUser, ReadOnly
from camomilla.serializers import (
    PermissionSerializer,
    UserProfileSerializer,
    UserSerializer,
)
from camomilla.views.base import BaseModelViewset


class CamomillaObtainAuthToken(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key})


class UserViewSet(BaseModelViewset):
    queryset = get_user_model().objects.all()
    serializer_class = UserSerializer
    model = get_user_model()

    @action(detail=False, methods=["get", "put"], permission_classes=(IsAuthenticated,))
    def current(self, request):
        user = request.user
        if request.method == "PUT":
            serialized_user = UserProfileSerializer(
                user, data=request.data, partial=True
            )
            if serialized_user.is_valid(raise_exception=True):
                user = serialized_user.save()
        return Response(UserProfileSerializer(user, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def kickout(self, request, pk=None):
        user = self.get_object()
        try:
            user.auth_token.delete()
        except Exception:
            pass
        return Response({})


class PermissionViewSet(BaseModelViewset):
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    model = Permission
    permission_classes = (CamomillaSuperUser | ReadOnly,)
    http_method_names = ["get", "put", "options", "head"]

    def get_queryset(self):
        permissions = Permission.objects.filter(
            Q(content_type__app_label__contains="camomilla")
            | Q(content_type__app_label__contains="plugin_")
            | Q(content_type__model="token")
            | Q(content_type__model="user")
        )
        return permissions


class CamomillaAuthLogin(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        login(request, user)
        return Response({"detail": "Logged in"})


class CamomillaAuthLogout(APIView):
    def get(self, request, *args, **kwargs):
        if request.user:
            logout(request)
        return Response({"detail": "Logged out"})
