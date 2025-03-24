from rest_framework import serializers
from camomilla.serializers.base import BaseModelSerializer


class CustomBaseArgumentsRegisterModelSerializer(BaseModelSerializer):
    description = serializers.CharField(min_length=3)