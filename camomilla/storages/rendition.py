from camomilla.storages.default import get_default_storage_class


class RenditionStorage(get_default_storage_class()):
    def _save(self, name, content):
        if self.exists(name):
            self.delete(name)
        return super(RenditionStorage, self)._save(name, content)

    def get_available_name(self, name, *args, **kwargs):
        return name
