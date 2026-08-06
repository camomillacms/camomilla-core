"""Page-related helpers that don't belong on a model or manager.

The ``UrlNode`` -> page query optimisation that used to live here is now
``UrlNode.objects.prefetch_pages()`` (see
:class:`camomilla.managers.pages.UrlNodeManager`) — the manager already knows
how to enumerate the concrete page subclasses, so it is the right owner.

Deliberately NOT star-imported from :mod:`camomilla.utils` (``__init__.py``):
``camomilla.models.page`` imports ``camomilla.utils``, so pulling a module that
touches the models into that package's import would close a cycle. Import it
explicitly instead::

    from camomilla.utils.pages import public_path
"""

from typing import Optional

from django.conf import settings as django_settings

from camomilla.settings import DEFAULT_LANGUAGE, ENABLE_TRANSLATIONS


def public_path(language_code: Optional[str], permalink: str) -> str:
    """Full public path a visitor hits for ``(language, permalink)``.

    Mirrors Django's ``i18n_patterns`` + ``APPEND_SLASH`` — the same shape
    :attr:`UrlRedirect.redirect_to` produces. ``/about`` in the non-default
    language ``it`` → ``/it/about/``; the homepage ``/`` → ``/`` (``/it/``
    for ``it``). This is the key the static builder maps to an output file.

    ``language_code`` may be ``None``: ``UrlRedirect.language_code`` is
    nullable, and a redirect with no language is not scoped to one, so it
    gets the unprefixed path exactly like the default language does.
    """
    path = "/" + (permalink or "/").lstrip("/")
    if getattr(django_settings, "APPEND_SLASH", True) and not path.endswith("/"):
        path += "/"
    if language_code and language_code != DEFAULT_LANGUAGE and ENABLE_TRANSLATIONS:
        path = "/" + language_code + path
    return path
