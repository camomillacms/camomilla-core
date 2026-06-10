# 🎭 Use Modeltranslation

Camomilla comes with [django-modeltranslation](https://django-modeltranslation.readthedocs.io/en/latest/index.html) installed and configured.
Modeltranslation is a django app that allows you to translate your models fields.

To use it, you need to add the `modeltranslation` app to your `INSTALLED_APPS` setting:

```python
# <project_name>/settings.py

INSTALLED_APPS = [
    ...
    "modeltranslation",
    ...
]
```

## 🪡 Register your models

To translate a model, you need to register in the `modeltranslation` registry.
To register a model, you need to create a `translation.py` file in your django app folder and register your models there.

Let's see an example:

```python
# <project_name>/<app_name>/translation.py

from modeltranslation.translator import translator, TranslationOptions
from .models import MyModel

class MyModelTranslationOptions(TranslationOptions):
    fields = ("title", "description")

translator.register(MyModel, MyModelTranslationOptions)
```

In this example we registered the `MyModel` model and we specified that we want to translate the `title` and `description` fields.

TranslationOptions fields can be inherited from other TranslationOptions, so you can create a base TranslationOptions class and inherit from it in your models TranslationOptions.

For models that inherit from camomilla AbstractPage, should use the `AbstractPageTranslationOptions` class, to inherit all needed fields to translate.

```python
# <project_name>/<app_name>/translation.py

from modeltranslation.translator import translator, TranslationOptions
from camomilla.translation import AbstractPageTranslationOptions
from .models import MyModel

class MyModelTranslationOptions(AbstractPageTranslationOptions):
    fields = ("title", "description")

translator.register(MyModel, MyModelTranslationOptions)
```

## 🚨 Caveats with Rest Framework

If you are using [Django Rest Framework](https://www.django-rest-framework.org/) you should always declare get_queryset in your viewsets, otherwise the statically declared queryset will not provide results in the requested language.

```python
# <project_name>/<app_name>/views.py

from rest_framework import viewsets

class MyModelViewSet(viewsets.ModelViewSet):
    queryset = MyModel.objects.all() # this will not work

    def get_queryset(self):
        return MyModel.objects.all()
```


For more information about django-modeltranslation, please refer to the [official documentation](https://django-modeltranslation.readthedocs.io/en/latest/index.html).