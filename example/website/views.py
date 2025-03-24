from .serializers import CustomBaseArgumentsRegisterModelSerializer
from camomilla.views.base import BaseModelViewset


class CustomBaseArgumentsRegisterModelViewSet(BaseModelViewset):
    serializer_class = CustomBaseArgumentsRegisterModelSerializer
    search_fields = ["description"]
