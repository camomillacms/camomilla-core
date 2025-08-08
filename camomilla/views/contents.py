import json

from django.http import JsonResponse
from rest_framework.decorators import action

from camomilla.models import Content
from camomilla.serializers import ContentSerializer
from camomilla.views.base import BaseModelViewset
from camomilla.views.mixins import BulkDeleteMixin, GetUserLanguageMixin


class ContentViewSet(GetUserLanguageMixin, BulkDeleteMixin, BaseModelViewset):
    queryset = Content.objects.all()
    serializer_class = ContentSerializer
    model = Content

    @action(detail=True, methods=["get", "patch"])
    def djsuperadmin(self, request, pk):
        try:
            content = Content.objects.get(pk=pk)
        except Content.DoesNotExist:
            content, _ = Content.objects.get_or_create(pk=pk)
        if request.method == "GET":
            return JsonResponse({"content": content.content})
        if request.method == "PATCH":
            data = json.loads(request.body)
            content_data = data["content"]
            content.content = content_data
            content.save()
            return JsonResponse({"content": content_data})
