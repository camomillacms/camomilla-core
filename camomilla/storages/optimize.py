import traceback
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image

from camomilla import settings
from camomilla.storages.default import get_default_storage_class


class OptimizedStorage(get_default_storage_class()):
    MEDIA_MAX_WIDTH = settings.MEDIA_OPTIMIZE_MAX_WIDTH
    MEDIA_MAX_HEIGHT = settings.MEDIA_OPTIMIZE_MAX_HEIGHT
    MEDIA_DPI = settings.MEDIA_OPTIMIZE_DPI
    MEDIA_OPTIMIZE_JPEG_QUALITY = settings.MEDIA_OPTIMIZE_JPEG_QUALITY

    def __init__(self, *args, **kwargs) -> None:
        self.MEDIA_MAX_WIDTH = int(kwargs.pop("max_width", self.MEDIA_MAX_WIDTH))
        self.MEDIA_MAX_HEIGHT = int(kwargs.pop("max_height", self.MEDIA_MAX_HEIGHT))
        self.MEDIA_DPI = int(kwargs.pop("dpi", self.MEDIA_DPI))
        self.MEDIA_OPTIMIZE_JPEG_QUALITY = int(
            kwargs.pop("jpeg_quality", self.MEDIA_OPTIMIZE_JPEG_QUALITY)
        )
        super().__init__(*args, **kwargs)

    def _save(self, name: str, content: ContentFile):
        if settings.ENABLE_MEDIA_OPTIMIZATION:
            content, _ = self._optimize(name, content)
        return super(OptimizedStorage, self)._save(name, content)

    def _optimize(self, name: str, content: ContentFile):
        try:
            image = Image.open(content)
            original_size = content.size
            width, height = image.size

            if width > self.MEDIA_MAX_WIDTH or height > self.MEDIA_MAX_HEIGHT:
                if width <= height:
                    selected_width = int((self.MEDIA_MAX_HEIGHT / height) * width)
                    selected_height = self.MEDIA_MAX_HEIGHT
                else:
                    selected_height = int((self.MEDIA_MAX_WIDTH / width) * height)
                    selected_width = self.MEDIA_MAX_WIDTH

                image = image.resize(
                    [selected_width, selected_height], resample=Image.LANCZOS
                )
            dpi = (self.MEDIA_DPI, self.MEDIA_DPI)
            image.info["dpi"] = dpi
            tmp = BytesIO()
            ext = name.split(".")[-1].lower().replace("jpg", "jpeg")
            image.save(
                tmp,
                ext,
                dpi=dpi,
                optimize=True,
                quality=self.MEDIA_OPTIMIZE_JPEG_QUALITY,
            )
            tmp_size = len(tmp.getvalue())

            if tmp_size > original_size:
                tmp.close()
                return content, False
            optimized_content = ContentFile(tmp.getvalue())
            tmp.close()
            content.close()
            return optimized_content, True
        except Exception as e:
            traceback.print_exc()
            print(f"Error optimizing image {name}: {str(e)}")
            return content, False
