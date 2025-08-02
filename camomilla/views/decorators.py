import functools
from django.utils.translation import activate
from django.views.decorators.cache import cache_page
from camomilla.settings import LANGUAGE_CODES, DEFAULT_LANGUAGE


def active_lang(*args, **kwargs):
    def decorator(func):
        @functools.wraps(func)
        def wrapped_func(*args, **kwargs):
            if len(args) and hasattr(args[0], "request"):
                request = args[0].request
            else:
                request = args[0] if len(args) else kwargs.get("request", None)
            lang = DEFAULT_LANGUAGE
            if request and hasattr(request, "GET"):
                lang = request.GET.get("lang", request.GET.get("language", lang))
            if request and hasattr(request, "data"):
                lang = request.data.pop("lang", request.data.pop("language", lang))
            if lang and lang in LANGUAGE_CODES:
                activate(lang)
                request.LANGUAGE_CODE = lang
            return func(*args, **kwargs)

        return wrapped_func

    return decorator


def staff_excluded_cache(timing=None):
    def decorator(func):
        if timing is None:
            return func  # No caching applied

        @functools.wraps(func)
        def wrapped_func(*args, **kwargs):
            request = args[0] if len(args) else kwargs.get("request", None)
            if request and hasattr(request, "user"):
                user = request.user
                if user.is_authenticated and user.is_staff:
                    return func(*args, **kwargs)
            return cache_page(timing)(func)(*args, **kwargs)

        return wrapped_func

    return decorator
