from django.db.models.query import QuerySet
from django.core.exceptions import ObjectDoesNotExist
from django.apps import apps
from django.db import models
from django.utils import timezone
from django.db.utils import ProgrammingError, OperationalError
from typing import Sequence, Tuple

URL_NODE_RELATED_NAME = "%(app_label)s_%(class)s"


class PageQuerySet(QuerySet):

    __UrlNodeModel = None

    @property
    def UrlNodeModel(self):
        if not self.__UrlNodeModel:
            self.__UrlNodeModel = apps.get_model("camomilla", "UrlNode")
        return self.__UrlNodeModel

    def get_permalink_kwargs(self, kwargs):
        return list(
            set(kwargs.keys()).intersection(
                set(self.UrlNodeModel.LANG_PERMALINK_FIELDS + ["permalink"])
            )
        )

    def get(self, *args, **kwargs):
        permalink_args = self.get_permalink_kwargs(kwargs)
        if len(permalink_args):
            try:
                node = self.UrlNodeModel.objects.get(
                    **{arg: kwargs.pop(arg) for arg in permalink_args}
                )
                kwargs["url_node"] = node
            except ObjectDoesNotExist:
                raise self.model.DoesNotExist(
                    "%s matching query does not exist." % self.model._meta.object_name
                )
        return super(PageQuerySet, self).get(*args, **kwargs)


class UrlNodeManager(models.Manager):
    @property
    def related_names(self):
        self._related_names = getattr(
            self,
            "_related_names",
            super().get_queryset().values_list("related_name", flat=True).distinct(),
        )
        return self._related_names

    def _annotate_fields(
        self,
        qs: models.QuerySet,
        field_names: Sequence[Tuple[str, models.Field, models.Value]],
    ):
        for field_name, output_field, default in field_names:
            whens = [
                models.When(
                    related_name=related_name,
                    then=models.F("__".join([related_name, field_name])),
                )
                for related_name in self.related_names
            ]
            qs = qs.annotate(
                **{
                    field_name: models.Case(
                        *whens, output_field=output_field, default=default
                    )
                }
            )
        return self._annotate_is_public(qs)

    def _annotate_is_public(self, qs: models.QuerySet):
        return qs.annotate(
            is_public=models.Case(
                models.When(status="PUB", then=True),
                models.When(
                    status="PLA", publication_date__lte=timezone.now(), then=True
                ),
                default=False,
                output_field=models.BooleanField(default=False),
            )
        )

    def get_queryset(self):
        try:
            return self._annotate_fields(
                super().get_queryset(),
                [
                    (
                        "indexable",
                        models.BooleanField(),
                        models.Value(None, models.BooleanField()),
                    ),
                    (
                        "status",
                        models.CharField(),
                        models.Value("DRF", models.CharField()),
                    ),
                    (
                        "publication_date",
                        models.DateTimeField(),
                        models.Value(timezone.now(), models.DateTimeField()),
                    ),
                    (
                        "date_updated_at",
                        models.DateTimeField(),
                        models.Value(timezone.now(), models.DateTimeField()),
                    ),
                ],
            )
        except (ProgrammingError, OperationalError):
            return super().get_queryset()
