from rest_framework import serializers
from camomilla.serializers.mixins.page import AbstractPageMixin
from .models import RelatedPageModel, ExposedRelatedPageModel, CustomApiSerializerModel


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


class CustomApiSerializerModelSerializer(AbstractPageMixin):
    description = serializers.SerializerMethodField()
    added_field = serializers.SerializerMethodField()

    def get_description(self, obj):
        return f"{obj.description}-CustomApiSerializer"
    
    def get_added_field(self, obj):
        return "This is an added field from CustomApiSerializerModelSerializer"

    class Meta:
        model = CustomApiSerializerModel
        fields = fields = "__all__"



class InvalidSerializer(serializers.Serializer):
    pass
