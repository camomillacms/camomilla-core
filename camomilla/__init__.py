__version__ = "6.1.0"


def get_core_apps():
    return ["rest_framework", "rest_framework.authtoken"]


def autodiscover():
    from camomilla.templates_context.autodiscover import autodiscover_context_files

    autodiscover_context_files()
