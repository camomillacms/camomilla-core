import logging

logger = logging.getLogger(__name__)


def autodiscover_context_files():
    """
    Auto-discover INSTALLED_APPS template_context.py modules and fail silently when
    not present. This forces an import on them to register.
    Also import explicit modules.
    """
    import copy
    import sys
    from django.utils.module_loading import module_has_submodule
    from camomilla.templates_context.rendering import ctx_registry
    from importlib import import_module
    from django.apps import apps
    from camomilla.settings import TEMPLATE_CONTEXT_FILES, DEBUG

    mods = [
        (app_config.name, app_config.module) for app_config in apps.get_app_configs()
    ]

    for app, mod in mods:
        module = "%s.template_context" % app
        _model_registry_bkp = copy.copy(ctx_registry._model_registry)
        _template_registry_bkp = copy.copy(ctx_registry._template_registry)

        try:
            import_module(module)
        except Exception:
            ctx_registry._model_registry = _model_registry_bkp
            ctx_registry._template_registry = _template_registry_bkp
            if module_has_submodule(mod, "template_context"):
                raise

    for module in TEMPLATE_CONTEXT_FILES:
        import_module(module)

    if DEBUG:
        try:
            if sys.argv[1] in ("runserver", "runserver_plus"):
                if not ctx_registry.get_registered_info().items():
                    return
                logger.debug("Camomilla context files:")
                for k, v in ctx_registry.get_registered_info().items():
                    logger.debug("%s:", k)
                    models = v.get("models")
                    templates = v.get("templates")
                    if models:
                        logger.debug("  models: %s", models)
                    if templates:
                        logger.debug("  templates: %s", templates)
                    logger.debug("")
        except IndexError:
            pass
