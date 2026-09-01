from typing import Optional, Type

from django.db import models
from django.urls import NoReverseMatch, reverse


def endpoint_for_model(model: Type[models.Model]) -> Optional[str]:
    """
    The API list URL a client should query for ``model``, or None.

    Resolved from the routers' own registries and ``reverse()`` rather than by
    joining prefixes: the routers are mounted under a prefix this module has no
    business knowing, and a project can mount them somewhere else entirely.

    Both routers are consulted — camomilla's built-in one and the dynamic
    ``model_api`` one — so a model registered by a project resolves the same way
    as a built-in.
    """
    from camomilla.model_api import router as dynamic_router
    from camomilla.urls import router as builtin_router

    for router in (builtin_router, dynamic_router):
        for _prefix, viewset, basename in router.registry:
            queryset = getattr(viewset, "queryset", None)
            candidate = getattr(viewset, "model", None) or getattr(
                queryset, "model", None
            )
            if candidate is not model:
                continue
            try:
                return reverse(f"{basename}-list")
            except NoReverseMatch:
                # Registered but not mounted in this project's URLConf.
                return None
    return None
