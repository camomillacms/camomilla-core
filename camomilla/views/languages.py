from django.conf import settings
from rest_framework.response import Response
from rest_framework import views
from rest_framework.permissions import AllowAny


class LanguageViewSet(views.APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        languages = []
        for key, language in settings.LANGUAGES:
            languages.append({"id": key, "name": language})
        return Response(
            {"language_code": settings.LANGUAGE_CODE, "languages": languages}
        )
