from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from .pagination import *
from .ordering import *
from ...permissions import CamomillaBasePermissions
from django.utils import translation


class GetUserLanguageMixin(object):
    def _get_user_language(self, request):
        self.active_language = request.GET.get(
            "language",
            request.GET.get(
                "language_code", translation.get_language_from_request(request)
            ),
        )
        self.language_fallbacks = True
        if (
            len(self.active_language.split("-")) == 2
            and self.active_language.split("-")[0] == "nofallbacks"
        ):
            self.language_fallbacks = False
            self.active_language = self.active_language.split("-")[1]
        translation.activate(self.active_language)
        return self.active_language

    def initialize_request(self, request, *args, **kwargs):
        self._get_user_language(request)
        return super().initialize_request(request, *args, **kwargs)

    def get_queryset(self):
        return self.model.objects.all()


class CamomillaBasePermissionMixin:
    def get_permissions(self):
        return [*super().get_permissions(), CamomillaBasePermissions()]


class OptimViewMixin:
    def get_serializer_class(self):
        if hasattr(self, "action_serializers"):
            if self.action in self.action_serializers:
                return self.action_serializers[self.action]
        return super().get_serializer_class()

    def get_serializer_context(self):
        return {"request": self.request, "action": self.action}

    def get_queryset(self):
        queryset = super().get_queryset()
        serializer = self.get_serializer_class()
        if hasattr(serializer, "setup_eager_loading"):
            queryset = self.get_serializer_class().setup_eager_loading(queryset)
        return queryset


class BulkDeleteMixin(object):
    @action(
        detail=False, methods=["post"], permission_classes=(CamomillaBasePermissions,)
    )
    def bulk_delete(self, request):
        try:
            self.model.objects.filter(pk__in=request.data).delete()
            return Response(
                {"detail": "Eliminazione multipla andata a buon fine"},
                status=status.HTTP_200_OK,
            )
        except Exception:
            return Response(
                {"detail": "Eliminazione multipla non riuscita"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
