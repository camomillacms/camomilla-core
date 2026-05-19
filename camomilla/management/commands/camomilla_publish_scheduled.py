"""Publish pages whose ``publish_at`` has passed.

``publish_at`` is per-language: each translation can have its own scheduled
publish moment. ``resolve_scheduled_pages`` already cycles through the
languages via ``activate_languages`` while it builds the worklist — so for
every ``(page, lang)`` pair it yields, the active language is *already*
``lang`` at yield time. The cron just calls ``page.publish()`` and the
``published_at_<lang>`` stamp lands on the right column.

Intended to be run from cron/celery-beat/systemd-timer:

    python manage.py camomilla_publish_scheduled
"""

from django.core.management.base import BaseCommand

from camomilla.preview import resolve_scheduled_pages


class Command(BaseCommand):
    help = "Publish pages whose publish_at has passed (materialise pending drafts)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List pages that would be published without changing state.",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        count = 0
        # NOTE: ``resolve_scheduled_pages`` drives ``activate_languages``
        # internally, so by the time we receive each ``(page, lang)`` pair
        # the matching language is already active in the current thread.
        # Do NOT wrap ``publish()`` in another language activation here —
        # it would clobber the generator's bookkeeping.
        for page, lang in resolve_scheduled_pages():
            count += 1
            lang_label = f" [{lang}]" if lang else ""
            label = f"{page._meta.label} pk={page.pk}{lang_label} -> {page}"
            if dry_run:
                self.stdout.write(f"[dry-run] would publish {label}")
                continue
            try:
                page.publish(comment="Scheduled publish")
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(f"Failed to publish {label}: {exc}")
                continue
            self.stdout.write(self.style.SUCCESS(f"Published {label}"))
        if count == 0:
            self.stdout.write("No scheduled pages to publish.")
