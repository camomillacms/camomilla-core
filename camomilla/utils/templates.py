from pathlib import Path
from typing import Sequence

from django import template as django_template
from os.path import relpath
from camomilla.settings import REGISTERED_TEMPLATES_APPS


def get_all_templates_files() -> Sequence[str]:
    files = []

    for engine in django_template.loader.engines.all():

        if REGISTERED_TEMPLATES_APPS:
            dirs = [
                d for d in engine.template_dirs
                if any(app in str(d) for app in REGISTERED_TEMPLATES_APPS)
            ]
        else:
            # Exclude pip installed site package template dirs
            dirs = [
                d for d in engine.template_dirs
                if "site-packages" not in str(d) or "camomilla" in str(d)
            ]

        for d in dirs:
            base = Path(d)
            files.extend(
                relpath(f, d)
                for f in base.rglob("*.html")
            )

    return files
