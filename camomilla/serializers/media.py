from django.db.models import Model
from rest_framework import serializers

from ..models import Media, MediaFolder
from ..storages import OverwriteStorage
from .base import BaseTranslatableModelSerializer
from django.core.exceptions import ObjectDoesNotExist

class MediaListSerializer(BaseTranslatableModelSerializer):
    is_image = serializers.SerializerMethodField("get_is_image")

    def get_is_image(self, obj):
        return obj.is_image

    class Meta:
        model = Media
        fields = "__all__"


class MediaSerializer(BaseTranslatableModelSerializer):
    links = serializers.SerializerMethodField("get_linked_instances")
    is_image = serializers.SerializerMethodField("get_is_image")

    class Meta:
        model = Media
        fields = "__all__"

    def get_linked_instances(self, obj):
        result = []
        links = obj.get_foreign_fields()
        for link in links:
            if not hasattr(obj, link):
                # if the link is a one to one field,
                # and this one to one field is not set,
                # let's continue to the next relation
                continue
            
            manager = getattr(obj, link)

            if isinstance(manager, Model):
                # in this case it's not a manager but a one to one field
                # so the manager is the actual single item
                item = manager
                result.append(                            {
                    "model": item.__class__.__name__,
                    "name": item.__str__(),
                    "id": item.pk,
                })
            else: # otherwise it's a regular to many relationship
                if hasattr(manager, "language"):
                    manager = manager.language()

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


class MediaFolderSerializer(BaseTranslatableModelSerializer):
    icon = MediaSerializer(read_only=True)

    class Meta:
        model = MediaFolder
        fields = "__all__"
