from django.utils import translation
from camomilla import settings


class GetUserLanguageMixin:
    def _get_user_language(self, request):
        active_language_from_request = translation.get_language_from_request(request)
        active_language = (
            active_language_from_request
            if active_language_from_request
            else settings.DEFAULT_LANGUAGE
        )
        active_language = request.GET.get("language_code", active_language)
        active_language = request.GET.get("language", active_language)
        self.active_language = active_language
        self.language_fallbacks = True
        if (
            len(self.active_language.split("-")) == 2
            and self.active_language.split("-")[0] == "nofallbacks"
        ):
            self.language_fallbacks = False
            self.active_language = self.active_language.split("-")[1]
        translation.activate(self.active_language)
        return self.active_language

    def initialize_request(self, request, *args, **kwargs):
        self._get_user_language(request)
        return super().initialize_request(request, *args, **kwargs)

    def get_queryset(self):
        if hasattr(super(), "get_queryset"):
            return super().get_queryset()
        return self.model.objects.all()
