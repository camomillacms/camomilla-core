from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from ...permissions import CamomillaBasePermissions


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
