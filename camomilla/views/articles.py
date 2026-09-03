from camomilla.models import Article
from camomilla.serializers import ArticleSerializer
from camomilla.views.base import BaseModelViewset
from camomilla.views.mixins import BulkDeleteMixin, PageLifecycleMixin


class ArticleViewSet(PageLifecycleMixin, BulkDeleteMixin, BaseModelViewset):
    queryset = Article.objects.all()
    serializer_class = ArticleSerializer
    search_fields = ["title", "identifier", "content", "permalink"]
    model = Article
