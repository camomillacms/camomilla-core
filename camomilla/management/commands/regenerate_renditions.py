from django.core.management.base import BaseCommand
from camomilla.models import Media


class Command(BaseCommand):
    help = "Regenerates all the media renditions"

    def handle(self, *args, **options):
        for media in Media.objects.all():
            if not media.is_image:
                continue
            media.regenerate_renditions()
            self.stdout.write(
                self.style.SUCCESS(
                    "Successfully regenerated renditions for {0}".format(media.file.url)
                )
            )
