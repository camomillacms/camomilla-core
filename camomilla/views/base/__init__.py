from ..mixins import OptimViewMixin, PaginateStackMixin, OrderingMixin, CamomillaBasePermissionMixin
from rest_framework import viewsets


class BaseModelViewset(
    CamomillaBasePermissionMixin, OptimViewMixin, OrderingMixin, PaginateStackMixin, viewsets.ModelViewSet
):
    pass
