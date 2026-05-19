"""Apply pending Drafts whose ``scheduled_for`` moment has passed.

The cron walks :func:`camomilla.preview.resolve_scheduled_pages`, which
yields ``(page, language)`` pairs from due Draft rows. For each pair we
activate the language (so the per-language ``published_at_<lang>``
stamp lands in the right column) and call ``page.publish()`` — the model
loads the Draft row, applies it through the publish serializer, and
deletes the Draft.

Intended to be run from cron/celery-beat/systemd-timer::

    python manage.py camomilla_publish_scheduled
"""

from django.core.management.base import BaseCommand
from django.utils import translation

from camomilla.preview import resolve_scheduled_pages


class Command(BaseCommand):
    help = "Publish drafts whose scheduled_for moment has passed."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List drafts that would be published without changing state.",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        count = 0
        for page, lang in resolve_scheduled_pages():
            count += 1
            lang_label = f" [{lang}]" if lang else ""
            label = f"{page._meta.label} pk={page.pk}{lang_label} -> {page}"
            if dry_run:
                self.stdout.write(f"[dry-run] would publish {label}")
                continue
            original_language = translation.get_language()
            try:
                if lang:
                    translation.activate(lang)
                page.publish(comment="Scheduled publish")
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(f"Failed to publish {label}: {exc}")
                continue
            finally:
                if original_language:
                    translation.activate(original_language)
            self.stdout.write(self.style.SUCCESS(f"Published {label}"))
        if count == 0:
            self.stdout.write("No scheduled drafts to publish.")
