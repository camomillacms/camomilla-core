from django.db.models.query import QuerySet
from django.core.exceptions import ObjectDoesNotExist
from django.apps import apps

URL_NODE_RELATED_NAME = "%(app_label)s_%(class)s"


class PageQuerySet(QuerySet):

    __UrlNodeModel = None

    @property
    def UrlNodeModel(self):
        if not self.__UrlNodeModel:
            self.__UrlNodeModel = apps.get_model("camomilla", "UrlNode")
        return self.__UrlNodeModel

    def get_permalink_kwargs(self, kwargs):
        return list(set(kwargs.keys()).intersection(set(self.UrlNodeModel.LANG_PERMALINK_FIELDS + ["permalink"])))

    def get(self, *args, **kwargs):
        permalink_args = self.get_permalink_kwargs(kwargs)
        if len(permalink_args):
            try:
                node = self.UrlNodeModel.objects.get(**{arg: kwargs.pop(arg) for arg in permalink_args})
                kwargs["url_node"] = node
            except ObjectDoesNotExist:
                raise self.model.DoesNotExist(
                    "%s matching query does not exist." % self.model._meta.object_name
                )
        return super(PageQuerySet, self).get(*args, **kwargs)
