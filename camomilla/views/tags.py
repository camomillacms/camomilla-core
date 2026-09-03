from camomilla.models import Tag
from camomilla.serializers import TagSerializer
from camomilla.views.base import BaseModelViewset
from camomilla.views.mixins import BulkDeleteMixin


class TagViewSet(BulkDeleteMixin, BaseModelViewset):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    model = Tag
