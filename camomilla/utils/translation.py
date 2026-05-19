import re
from typing import Any, Iterator, List, Optional, Sequence, Union

from django.db.models import Model, Q
from django.utils.translation.trans_real import activate, get_language
from modeltranslation.utils import build_localized_fieldname
from camomilla.settings import BASE_URL, DEFAULT_LANGUAGE, LANGUAGE_CODES
from django.http import QueryDict


def activate_languages(languages: Sequence[str] = LANGUAGE_CODES) -> Iterator[str]:
    """Yield each language code in turn with that language activated.

    Restoration of the caller's original language happens in a ``finally``
    block, so it runs whether the consumer exhausts the generator, breaks
    out early, raises mid-iteration, or has the generator garbage-collected.
    Without that guarantee, an exception inside the consumer's for-body
    would leave the thread pinned to the last-iterated language — a subtle
    bleed that surfaces in cron-like workers or long-lived requests.
    """
    old = get_language() or DEFAULT_LANGUAGE
    try:
        for language in languages:
            activate(language)
            yield language
    finally:
        activate(old)


def localized_fieldname(attr: str, language: Optional[str] = None, target: Optional[Model | type[Model]] = None) -> str:
    """Resolve ``attr`` to its localized column name on ``target``.

    ``target`` may be either a model instance or a model class — anything
    that responds to ``hasattr(target, "<attr>_<lang>")``. Falls back to
    the base name when the localized column doesn't exist (monolingual
    models or ``ENABLE_TRANSLATIONS=False``) or no language is active.

    Use this whenever you need to *name* the column to hand to an
    F-expression, Case/When lookup, or update_fields list. Use
    :func:`get_nofallbacks` / :func:`set_nofallbacks` when you need the
    *value* from an instance.
    """
    language = language or get_language()
    if not language:
        return attr
    local = build_localized_fieldname(attr, language)
    return local if hasattr(target, local) else attr


def set_nofallbacks(instance: Model, attr: str, value: Any, **kwargs) -> None:
    attr = localized_fieldname(attr, kwargs.pop("language", None), instance)
    return setattr(instance, attr, value)


def get_nofallbacks(instance: Model, attr: str, *args, **kwargs) -> Any:
    attr = localized_fieldname(attr, kwargs.pop("language", None), instance)
    return getattr(instance, attr, *args, **kwargs)


def url_lang_decompose(url):
    if BASE_URL and url.startswith(BASE_URL):
        url = url[len(BASE_URL) :]
    data = {"url": url, "permalink": url, "language": DEFAULT_LANGUAGE}
    result = re.match(rf"^/?({'|'.join(LANGUAGE_CODES)})?/(.*)", url)  # noqa: W605
    groups = result and result.groups()
    if groups and len(groups) == 2:
        data["language"] = groups[0]
        data["permalink"] = "/%s" % groups[1]
    return data


def get_field_translations(instance: Model, field_name: str, *args, **kwargs):
    return {
        lang: get_nofallbacks(instance, field_name, language=lang, *args, **kwargs)
        for lang in LANGUAGE_CODES
    }


def lang_fallback_query(**kwargs):
    current_lang = get_language()
    query = Q()
    for lang in LANGUAGE_CODES:
        query |= Q(**{f"{key}_{lang}": value for key, value in kwargs.items()})
    if current_lang:
        query = query & Q(
            **{f"{key}_{current_lang}__isnull": True for key in kwargs.keys()}
        )
        query |= Q(**{f"{key}_{current_lang}": value for key, value in kwargs.items()})
    return query


def is_translatable(model: Model) -> bool:
    from modeltranslation.translator import translator

    return model in translator.get_registered_models()


def plain_to_nest(data, fields, accessor="translations"):
    """
    This function transforms a plain dictionary with translations fields (es. {"title_en": "Hello"})
    into a dictionary with nested translations fields (es. {"translations": {"en": {"title": "Hello"}}}).
    """
    trans_data = {}
    for lang in LANGUAGE_CODES:
        lang_data = {}
        for field in fields:
            trans_field_name = build_localized_fieldname(field, lang)
            if trans_field_name in data:
                lang_data[field] = data.pop(trans_field_name)
        if lang_data.keys():
            trans_data[lang] = lang_data
    if trans_data.keys():
        data[accessor] = trans_data
    return data


def nest_to_plain(
    data: Union[dict, QueryDict], fields: List[str], accessor="translations"
):
    """
    This function is the inverse of plain_to_nest.
    It transforms a dictionary with nested translations fields (es. {"translations": {"en": {"title": "Hello"}}})
    into a plain dictionary with translations fields (es. {"title_en": "Hello"}).
    """
    if isinstance(data, QueryDict):
        data = data.dict()
    translations = data.pop(accessor, {})
    for lang in LANGUAGE_CODES:
        nest_trans = translations.pop(lang, {})
        for k in fields:
            data.pop(k, None)  # this removes all trans field without lang
            if k in nest_trans:
                # this saves on the default field the default language value
                if lang == DEFAULT_LANGUAGE:
                    data[k] = nest_trans[k]
                key = build_localized_fieldname(k, lang)
                data[key] = data.get(key, nest_trans[k])
    return data
