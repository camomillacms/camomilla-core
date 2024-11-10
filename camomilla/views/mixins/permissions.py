from camomilla.permissions import CamomillaBasePermissions


class CamomillaBasePermissionMixin:
    def get_permissions(self):
        return [*super().get_permissions(), CamomillaBasePermissions()]
