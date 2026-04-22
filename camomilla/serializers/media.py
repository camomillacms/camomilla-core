from rest_framework import serializers

from camomilla.models import Media, MediaFolder
from camomilla.serializers.base import BaseModelSerializer
from camomilla.storages import OverwriteStorage


def _build_renditions_payload(obj, request):
    if not obj.renditions:
        return {}
    payload = {}
    for name, entry in obj.renditions.items():
        if not isinstance(entry, dict):
            continue
        url = entry.get("url", "")
        if request is not None and url:
            url = request.build_absolute_uri(url)
        payload[name] = {
            "url": url,
            "width": entry.get("width"),
            "height": entry.get("height"),
            "format": entry.get("format"),
            "size": entry.get("size"),
        }
    return payload


def _build_srcset_payload(renditions_payload):
    by_format = {}
    for entry in renditions_payload.values():
        fmt = entry.get("format")
        width = entry.get("width")
        url = entry.get("url")
        if not fmt or not width or not url:
            continue
        by_format.setdefault(fmt, []).append((width, url))
    result = {}
    for fmt, items in by_format.items():
        items.sort(key=lambda x: x[0])
        result[fmt] = ", ".join("{} {}w".format(url, w) for w, url in items)
    return result


class MediaListSerializer(BaseModelSerializer):
    is_image = serializers.SerializerMethodField("get_is_image")
    renditions = serializers.SerializerMethodField("get_renditions")
    srcset = serializers.SerializerMethodField("get_srcset")

    def get_is_image(self, obj):
        return obj.is_image

    def get_renditions(self, obj):
        return _build_renditions_payload(obj, self.context.get("request"))

    def get_srcset(self, obj):
        return _build_srcset_payload(self.get_renditions(obj))

    class Meta:
        model = Media
        fields = "__all__"


class MediaSerializer(BaseModelSerializer):
    links = serializers.SerializerMethodField("get_linked_instances")
    is_image = serializers.SerializerMethodField("get_is_image")
    renditions = serializers.SerializerMethodField("get_renditions")
    srcset = serializers.SerializerMethodField("get_srcset")

    class Meta:
        model = Media
        fields = "__all__"

    def get_linked_instances(self, obj):
        result = []
        links = obj.get_foreign_fields()
        for link in links:
            manager = getattr(obj, link)
            for item in manager.all():
                if item.__class__.__name__ != "MediaTranslation":
                    result.append(
                        {
                            "model": item.__class__.__name__,
                            "name": item.__str__(),
                            "id": item.pk,
                        }
                    )
        return result

    def update(self, instance, data):
        same_url = self.initial_data.get("same_url", False)
        if same_url:
            new_file = data.pop("file", None)
            if new_file:
                instance = super().update(instance, data)
                instance.file.storage = OverwriteStorage()
                instance.file.save(instance.file.name, new_file, save=True)
                return instance
        return super().update(instance, data)

    def get_is_image(self, obj):
        return obj.is_image

    def get_renditions(self, obj):
        return _build_renditions_payload(obj, self.context.get("request"))

    def get_srcset(self, obj):
        return _build_srcset_payload(self.get_renditions(obj))


class MediaFolderSerializer(BaseModelSerializer):
    icon = MediaSerializer(read_only=True)

    class Meta:
        model = MediaFolder
        fields = "__all__"
