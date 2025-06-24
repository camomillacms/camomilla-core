from rest_framework import serializers
from camomilla.serializers.base import BaseModelSerializer
from camomilla.serializers.mixins.page import AbstractPageMixin


class CustomBaseArgumentsRegisterModelSerializer(BaseModelSerializer):
    description = serializers.CharField(min_length=3)


class CustomPageSerializer(AbstractPageMixin):
    serializer_custom_field = serializers.SerializerMethodField()
    
    def get_serializer_custom_field(self, instance):
        return f"I'm coming from CustomPageSerializer! 🫡"
    
    
class InvalidSerializer(serializers.Serializer):
    pass