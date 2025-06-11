from pathlib import Path
from typing import Sequence
import requests

from django import template as django_template
from os.path import relpath
from camomilla.settings import (
    REGISTERED_TEMPLATES_APPS,
    INTEGRATIONS_ASTRO_ENABLE,
    INTEGRATIONS_ASTRO_URL,
)


def get_templates(request=None) -> Sequence[str]:
    files = []

    for engine in django_template.loader.engines.all():

        if REGISTERED_TEMPLATES_APPS:
            dirs = [
                d
                for d in engine.template_dirs
                if any(app in str(d) for app in REGISTERED_TEMPLATES_APPS)
            ]
        else:
            # Exclude pip installed site package template dirs
            dirs = [
                d
                for d in engine.template_dirs
                if "site-packages" not in str(d) or "camomilla" in str(d)
            ]

        for d in dirs:
            base = Path(d)
            files.extend(relpath(f, d) for f in base.rglob("*.html"))

    if INTEGRATIONS_ASTRO_ENABLE and request is not None:
        try:
            response = requests.get(
                INTEGRATIONS_ASTRO_URL + "/api/templates",
                cookies={
                    "sessionid": request.COOKIES.get("sessionid"),
                    "csrftoken": request.COOKIES.get("csrftoken"),
                },
            )
            if response.status_code == 200:
                astro_templates = response.json()
                for template in astro_templates:
                    files.append(template)
        except:
            pass

    return files
