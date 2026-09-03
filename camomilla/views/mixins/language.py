from django.utils import translation
from camomilla import settings


def resolve_request_language(view, request):
    """Activate the language this request addresses, and record how we got it.

    Precedence: ``?language=`` / ``?language_code=``, then ``Accept-Language``
    (via Django's own resolver), then ``LANGUAGE_CODE``. Stamps
    ``active_language``, ``language_fallbacks`` and ``language_explicit`` on
    ``view``.

    A module function rather than only a mixin method because
    :class:`~camomilla.views.base.BaseModelViewset` calls it directly: making
    the base *inherit* ``GetUserLanguageMixin`` would break every project
    viewset that lists the mixin itself (documented pattern) with an
    inconsistent MRO.
    """
    active_language_from_request = translation.get_language_from_request(request)
    active_language = (
        active_language_from_request
        if active_language_from_request
        else settings.DEFAULT_LANGUAGE
    )
    # Whether the caller NAMED a language, as opposed to us deriving one from
    # Accept-Language. Actions whose body already carries a language (see
    # ``PageLifecycleMixin.draft``) need to tell the two apart: an explicit
    # parameter must win, a derived fallback must not.
    view.language_explicit = (
        "language" in request.GET or "language_code" in request.GET
    )
    active_language = request.GET.get("language_code", active_language)
    active_language = request.GET.get("language", active_language)
    view.active_language = active_language
    view.language_fallbacks = True
    if (
        len(view.active_language.split("-")) == 2
        and view.active_language.split("-")[0] == "nofallbacks"
    ):
        view.language_fallbacks = False
        view.active_language = view.active_language.split("-")[1]
    translation.activate(view.active_language)
    return view.active_language


class GetUserLanguageMixin:
    """Kept for viewsets that list it explicitly — including project ones.

    ``BaseModelViewset`` already resolves the request language, so mixing this
    in adds nothing on a camomilla-based viewset. It stays because it is public,
    documented API: removing it, or folding it into the base class list, would
    break `class MyViewSet(GetUserLanguageMixin, …, BaseModelViewset)`. Running
    twice is harmless — the resolution is idempotent.
    """

    def _get_user_language(self, request):
        return resolve_request_language(self, request)

    def initialize_request(self, request, *args, **kwargs):
        self._get_user_language(request)
        return super().initialize_request(request, *args, **kwargs)

    def get_queryset(self):
        if hasattr(super(), "get_queryset"):
            return super().get_queryset()
        return self.model.objects.all()
