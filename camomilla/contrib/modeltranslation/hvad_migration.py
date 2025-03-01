from django.conf import settings
from django.db import migrations, connection


class KeepTranslationsMixin:
    """
    This mixin make it possible to keep translations when migrating from django-hvad to modeltranslation and viceversa.
    To use it, you have to add a dictionary to your migration class called "keep_translations".
    The dictionary must have model paths as keys and a list of fields to keep as values.


    Example:
    ```python
    class Migration(KeepTranslationsMixin, migrations.Migration):
        keep_translations = {
            "app.Model": ("field1", "field2", "field3")
        }
    ```
    """

    _saved_data_from_plain = {}
    language_codes = dict(getattr(settings, "LANGUAGES", {})).keys()

    def is_operation_legit(self, o):
        return not (
            isinstance(o, migrations.RemoveField)
            and o.name == "master"
            and o.model_name.endswith("translation")
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.operations = [o for o in self.operations if self.is_operation_legit(o)]
        self.operations.insert(
            0, migrations.RunPython(self._getDataFromHvad, self._restoreDataToHvad)
        )
        self.operations.append(
            migrations.RunPython(
                self._restoreDataToModelTranslation, self._getDataFromModelTranslation
            )
        )

    def _getDataFromHvad(self, apps, schemaeditor):
        for modelPath, fields in self.keep_translations.items():
            Model = apps.get_model(*modelPath.split("."))
            table = Model._meta.db_table + "_translation"
            if "language_code" not in fields:
                fields = ("language_code",) + fields
            with connection.cursor() as cursor:
                cursor.execute("SELECT master_id FROM {0};".format(table))
                masters = list(set(cursor.fetchall()))
                for master in masters:
                    cursor.execute(
                        "SELECT {0} FROM {1} WHERE master_id={2};".format(
                            ",".join(fields), table, master[0]
                        )
                    )
                    rows = cursor.fetchall()
                    self._saved_data_from_plain[modelPath] = (
                        self._saved_data_from_plain.get(modelPath, {})
                    )
                    self._saved_data_from_plain[modelPath][master[0]] = (
                        self._saved_data_from_plain[modelPath].get(master[0], [])
                    )
                    for row in rows:
                        self._saved_data_from_plain[modelPath][master[0]].append(
                            dict(zip(fields, row))
                        )

    def _getDataFromModelTranslation(self, apps, schemaeditor):
        for modelPath, fields in self.keep_translations.items():
            Model = apps.get_model(*modelPath.split("."))
            table = Model._meta.db_table
            for lang in self.language_codes:
                t_fields = ("id",) + tuple(
                    "{0}_{1}".format(f, lang) for f in fields if f != "id"
                )
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT {0} FROM {1}".format(
                            ",".join(t_fields),
                            table,
                        )
                    )
                    rows = cursor.fetchall()
                    self._saved_data_from_plain[modelPath] = (
                        self._saved_data_from_plain.get(modelPath, [])
                    )
                    for row in rows:
                        row_data = dict(zip(("master_id", *fields), row))
                        row_data.update({"language_code": lang})
                        self._saved_data_from_plain[modelPath].append(row_data)

    def _restoreDataToModelTranslation(self, apps, schemaeditor):
        for key, master_dict in self._saved_data_from_plain.items():
            Model = apps.get_model(*key.split("."))
            for pk, translations in master_dict.items():
                try:
                    obj = Model.objects.get(pk=pk)
                except Model.DoesNotExist:
                    continue
                for translation in translations:
                    lang = translation.pop("language_code")
                    for attr, value in translation.items():
                        setattr(obj, "{0}_{1}".format(attr, lang), value)
                obj.save()

    def _restoreDataToHvad(self, apps, schemaeditor):
        for key, rows in self._saved_data_from_plain.items():
            Model = apps.get_model(*key.split("."))
            table = Model._meta.db_table + "_translation"
            for row in rows:
                with connection.cursor() as cursor:
                    print(row)
                    cursor.execute(
                        "INSERT INTO {0} ({1}) VALUES ({2});".format(
                            table,
                            ",".join(row.keys()),
                            ",".join(
                                [
                                    "'{}'".format(v).replace("'None'", "NULL")
                                    for v in row.values()
                                ]
                            ),
                        )
                    )
