from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, ValidationError as DRFValidationError

from camomilla.models import MetaInstance, MetaType
from camomilla.serializers.base import BaseModelSerializer
from camomilla.views.base import BaseModelViewset


class MetaTypeSerializer(BaseModelSerializer):
    class Meta:
        model = MetaType
        fields = "__all__"


class MetaTypeViewSet(BaseModelViewset):
    queryset = MetaType.objects.all()
    serializer_class = MetaTypeSerializer
    model = MetaType
    search_fields = ("name", "key")

    @action(detail=True, methods=["get"], url_path="schema")
    def schema(self, request, pk=None):
        meta_type = self.get_object()
        return Response(meta_type.get_json_schema())


class MetaInstanceSerializer(BaseModelSerializer):
    data = serializers.JSONField()

    class Meta:
        model = MetaInstance
        fields = "__all__"

    def _resolve_meta_type(self, attrs):
        meta_type = attrs.get("meta_type")
        if meta_type is None and self.instance is not None:
            meta_type = self.instance.meta_type
        return meta_type

    def validate(self, attrs):
        attrs = super().validate(attrs)
        meta_type = self._resolve_meta_type(attrs)
        if meta_type is None:
            raise DRFValidationError({"meta_type": "This field is required."})
        model_cls = meta_type.get_pydantic_model()
        try:
            validated = model_cls.model_validate(attrs.get("data") or {})
        except Exception as exc:
            raise DRFValidationError({"data": str(exc)})
        attrs["data"] = validated.model_dump(mode="json")
        return attrs


class MetaInstanceViewSet(BaseModelViewset):
    queryset = MetaInstance.objects.select_related("meta_type")
    serializer_class = MetaInstanceSerializer
    model = MetaInstance
    search_fields = ("identifier",)

    @action(detail=False, methods=["get"], url_path="schema")
    def schema(self, request):
        meta_type_id = request.GET.get("meta_type")
        if not meta_type_id:
            raise DRFValidationError({"meta_type": "Query parameter required."})
        try:
            meta_type = MetaType.objects.get(pk=meta_type_id)
        except MetaType.DoesNotExist:
            raise NotFound("MetaType not found")
        return Response(meta_type.get_json_schema())
