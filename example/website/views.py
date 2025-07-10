from rest_framework import serializers
from camomilla.serializers.base import BaseModelSerializer
from camomilla.views.base import BaseModelViewset


class CustomBaseArgumentsRegisterModelViewSet(BaseModelViewset):
    class CustomBaseArgumentsRegisterModelSerializer(BaseModelSerializer):
        description = serializers.CharField(min_length=3)

    serializer_class = CustomBaseArgumentsRegisterModelSerializer
    search_fields = ["description"]
