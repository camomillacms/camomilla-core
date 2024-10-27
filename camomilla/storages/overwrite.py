from camomilla.storages.default import get_default_storage_class


class OverwriteStorage(get_default_storage_class()):
    def _save(self, name, content):
        if self.exists(name):
            self.delete(name)
        return super(OverwriteStorage, self)._save(name, content)

    def get_available_name(self, name, *args, **kwargs):
        return name
