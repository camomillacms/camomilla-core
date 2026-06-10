# 🧩 Use Pages Context

With new page models we lost the ability to write view functions. Then we are giving you a way to inject more context inside a page in a simple manner.

You are going to apply the registration approach.

The game rules are simple, first of all:

 - Make a file called `template_context.py` in your app directory.
Camomilla is built to autodiscover those files.

Inside the file you can provide context with the register function in 2 different ways.

### Template based registration

To register some additional context to a specific template wite in the template_context.py file the following:

```python
from camomilla.templates_context.rendering import register
from camomilla.models import Media

@register("website/home.html")
def home_page():
    return {
    "title": "My fantastic title",
    "content": "My wanderfull content",
    "media_gallery": Media.objects.all(),
    }
```

### Model based registration

To register some additional context to a specific page wite in the template_context.py file the following:

```python
from camomilla.templates_context.rendering import register
from camomilla.models import Media, Page

@register(page_model=Page)
def home_page():
    return {
    "title": "My fantastic title",
    "content": "My wanderfull content",
    "media_gallery": Media.objects.all(),
    }
```

### Additional **kwargs

You can access to two usefull kwargs in template_context functions.
The request kwarg contains the django http request.
The super_ctx kwarg contains the context coming from upper functions or camomilla default context


```python
from camomilla.templates_context.rendering import register
from camomilla.models import Media, Page

@register(page_model=Page)
def home_page(request, super_ctx):
    # your custom code can use request or super_ctx to provide more precise context
    return {
    "title": "My fantastic title",
    "content": "My wanderfull content",
    "media_gallery": Media.objects.all(),
    }
```

