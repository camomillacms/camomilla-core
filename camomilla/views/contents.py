import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action

from camomilla.models import Content, ContentVersion
from camomilla.permissions import CamomillaBasePermissions
from camomilla.serializers import ContentSerializer
from camomilla.views.base import BaseModelViewset
from camomilla.views.mixins import BulkDeleteMixin, GetUserLanguageMixin


class ContentViewSet(GetUserLanguageMixin, BulkDeleteMixin, BaseModelViewset):
    queryset = Content.objects.all()
    serializer_class = ContentSerializer
    model = Content

    MAX_CONTENT_VERSIONS = 20

    def _prune(self, content):
        stale = list(
            content.versions.values_list("id", flat=True)[self.MAX_CONTENT_VERSIONS:]
        )
        if stale:
            content.versions.filter(id__in=stale).delete()

    @action(detail=True, methods=["get", "patch"])
    def djsuperadmin(self, request, pk):
        content = get_object_or_404(Content, pk=pk)
        if request.method == "PATCH":
            data = json.loads(request.body)
            content_data = data["content"]
            if content.content != content_data:
                ContentVersion.objects.create(content=content, data=content.content)
                self._prune(content)
            content.content = content_data
            content.save()
        return JsonResponse({"content": content.content})

    @action(detail=True, methods=["get"], url_path="djsuperadmin/history")
    def djsuperadmin_history(self, request, pk):
        content = get_object_or_404(Content, pk=pk)
        versions = content.versions.all()[: self.MAX_CONTENT_VERSIONS]
        return JsonResponse(
            {
                "versions": [
                    {"created_at": v.created_at.isoformat(), "data": v.data}
                    for v in versions
                ]
            }
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="get-or-create",
        permission_classes=(CamomillaBasePermissions,),
    )
    def get_or_create(self, request):
        content, _ = Content.objects.get_or_create(
            content_type_id=request.data.get("content_type") or None,
            object_id=request.data.get("object_id") or None,
            identifier=request.data.get("identifier"),
            defaults={"content": request.data.get("content") or ""},
        )
        return JsonResponse({"id": content.pk, "content": content.content})
