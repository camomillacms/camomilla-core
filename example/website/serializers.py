from rest_framework import serializers
from camomilla.serializers.mixins.page import AbstractPageMixin
from .models import RelatedPageModel, ExposedRelatedPageModel


class CustomPageSerializer(AbstractPageMixin):
    serializer_custom_field = serializers.SerializerMethodField()

    def get_serializer_custom_field(self, instance):
        return f"I'm coming from CustomPageSerializer! 🫡"


class RelatedPageModelSerializer(AbstractPageMixin):
    class Meta:
        model = RelatedPageModel
        fields = "__all__"


class ExposedRelatedPageModelSerializer(AbstractPageMixin):
    related_pages = RelatedPageModelSerializer(many=True, read_only=True)

    class Meta:
        model = ExposedRelatedPageModel
        fields = ["id", "related_pages"]


class InvalidSerializer(serializers.Serializer):
    pass
