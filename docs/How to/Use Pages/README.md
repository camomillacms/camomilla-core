# 📝 Use Pages

## 📎 The Page Model

Camomilla has it's own page model. The page model has an attribute for every relevant data in a web page. It takes care of SEO data and permalinks and template, and exposes jsonfields to manage additional data.

To use camomilla pages you need to add the dynamic url resolver at the end of your website urlpatterns:

```python
# <project_name>/urls.py
urlpatterns += path('', include("camomilla.dynamic_pages_urls"))
```

To handle multilanguage pages use:

```python
# <project_name>/urls.py
urlpatterns += i18n_patterns(
    path('', include("camomilla.dynamic_pages_urls")),
    prefix_default_language=False
)
```

This resolver is made to check any permalink that does not match anything in the url pattern and look in the database for a page with that permalink.

::: warning ⚠️ Beware!
The `dynamic_pages_urls` handler should always be the last handler of your urlpatterns list.
:::

### Choose the template

The page model has a field that determines which html template to use for rendering.
The default value is `defaults/pages/default.html`. If a value is stored in this field it will be used. The rendering part is yelded by the default [django template engine](https://docs.djangoproject.com/en/4.2/topics/templates/).
The default value can be changed with a setting:

```python
# <project_name>/settings.py
CAMOMILLA = {
    "RENDER": { "PAGE": {"DEFAULT_TEMPLATE": "website/my_template.html" }}
}
```

### Add template data

::: warning ⚠️ Beware!
[🧩 Use Page Context](../Use%20Pages%20Context/README.md) to inject context in a more safe way.
:::

The data that will be available in the rendering engine should be saved in the template_data field. This field is a django JSONField. So it will accept any json structure.
The data in this field will be accessible inside the template through `page.template_data`.
If you need to enrich the template context with other data that are not stored in the template data you can provide an `inject_context` function in camomilla settings:

```python
# <project_name>/settings.py

# import from external file
from my_project_app.template_rendering import page_inject_context

# or define explicitly in settings
def page_inject_context(request, super_ctx):
    from my_project_app.models import Category
    return {"all_categories": Category.objects.all()} # the all_category values will be accessible inside the template context.


CAMOMILLA = {
    "RENDER": { "PAGE": {"INJECT_CONTEXT": page_inject_context }}
}
```

### Set the permalink

By default camomilla Page autogenerates it's permalink by slugification of the SEO title.
If the page has a `parent_page` field and a page model associated with it, the permalink will be generated as a concatenation of the parent page permalink and the current page slug.

For example to generate the permalink `page_1/page_2` you will need to create 2 Pages, one with title `Page 1` and one with the title `Page 2` then set the first page as the parent page of the second and save it.

Otherwise, you can set the permalink manually by setting the `permalink` field.
Manual permalink modification is available only if `autopermalink` field is set to `False`.
While editing in django admin, if the user manually sets the permalink, the `autopermalink` field will be set to `False` automatically.

## 🖇️ The AbstractPage Model

Camomilla comes with an `AbstractPage` model. AbstractPage is different from Page model, it is Abstract.
This means that the AbstractPage by itself does not create a database table. The only whay an AbstractPage can have its own db table is to be inherited by a concrete model like this:

```python
from camomilla.models import AbstractPage

class MyPageModel(AbstractPage):
    # ... custom logic there
    pass

```

The AbstractPage contains all the logics of Page model. This means that you can override anything and define multiple custom page models. This is very usefull if you need to build complex sites, where you can have also other kid of data that need to be rendered and treated like a page (es. product, category, blog, anything..).

You can also define some intresting properties when you are defining your own page model.:

### Define page options with PageMeta

Many "settings" of the page model are stored inside a `PageMeta` class like this:

```python
from camomilla.models import AbstractPage

class MyPageModel(AbstractPage):
    class PageMeta:
        parent_page_field = "parent_page"
        default_template = "website/my_template.html"
        def inject_context_func(request, super_ctx):
            from my_project_app.models import Category
            return {"all_categories": Category.objects.all()}
```

From PageMeta class you can define:

- `parent_page_field` ==> set a different propery to store page parent. Like `category` or anything else.
- `default_template` ==> set a different default template.
- `inject_context_func` ==> add more data inside template context

::: warning ⚠️ Beware!
[🧩 Use Page Context](../Use%20Pages%20Context/README.md) to inject context in a more safe way.
:::

### Override the page context

This has almost the same functionality of `inject_context_func` PageMeta option but it runs at a more deep level. Overriding this will override the context and not only add things to it.

```python
from camomilla.models import AbstractPage

class MyPageModel(AbstractPage):
    def get_context(request):
        from my_project_app.models import Category
        return {"page": self, "all_categories": Category.objects.all()}
```

We suggest to always return `{ "page": self }` in the context.

## 🌐 Build a sitemap.xml

To build a sitemap.xml you can use the standard django sitemap framework. Camomilla comes with a `CamomillaPageSitemap` class that you can use to include camomilla pages in your sitemap.xml.

```python
# <project_name>/sitemap.py
from django.contrib.sitemaps import Sitemap
from camomilla.sitemaps import CamomillaPageSitemap

# declare your custom sitemaps
class StaticViewSitemap(Sitemap):
    def items(self):
        return ['home', 'about', 'contact']

    def location(self, item):
        return reverse(item)

sitemaps = {
    'pages': CamomillaPageSitemap, # add the camomilla sitemap
    'static': StaticViewSitemap, # add your custom sitemaps to the camomilla sitemaps
}
```

```python
# <project_name>/urls.py
from django.contrib.sitemaps.views import sitemap
from .sitemap import sitemaps

urlpatterns += [
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap')
]
```

To customize the camomilla sitemap you can override the `CamomillaPageSitemap` class. Overriding this class will allow you to customize changefreq, priority and also items.

```python
from camomilla.sitemaps import CamomillaPageSitemap

class MyCamomillaPageSitemap(CamomillaPageSitemap):
    changefreq = "monthly"
    priority = 0.5

    def items(self):
        return super().items().filter(status="PUB")
```

Remember that items is a queryset of `UrlNode` objects and to access the page model you need to use the `page` property of the `UrlNode` object.

## 🗂️ Pages router API endpoint

::: warning ⚠️ Beware!
If you need to create an api endpoint for a model inheriting from the `AbstractPage` model remember to use inside the serializer the `AbstractPageMixin`.
:::

Camomilla comes with a builtin pages router endpoint that allows you to browse your pages by url.

**URL Structure:**

- `api/camomilla/pages-router/<page_url>`

You can provide as the page_url parameter the full url of the page without language prefix.
The language you want to match against is taken from the request params.
If no language is specified, the default language is used.

To specify the language in the request params you can use the `lang` parameter:

`/api/camomilla/pages-router/<page_url>?lang=en`

When you try to get a page from the url, the router will always take in to account the active language.
If you are trying to get a page with a certain language, make sure to set the language in the request params.
If the specified url is not present in current language, the router endpoint will return a 404 error.

**Simple Response:**

```json
{
  "id": 1,
  "is_public": false,
  "status": "DRF",
  "indexable": true,
  "alternates": {
    "it": "/",
    "en": "/en/"
  },
  "permalink": "/",
  "related_name": "camomilla_page",
  "breadcrumbs": [
    {
      "permalink": "/",
      "title": null
    }
  ],
  "routerlink": "/",
  "template": "website/home.html",
  "title": null,
  "description": null,
  "og_description": null,
  "og_title": null,
  "og_type": null,
  "og_url": null,
  "canonical": null,
  "meta": {},
  "date_created": "2023-09-07T13:16:24.762269Z",
  "date_updated_at": "2023-09-08T17:38:03.155480Z",
  "breadcrumbs_title": null,
  "slug": null,
  "template_data": {},
  "identifier": "4ee68c88-dd1a-4515-bf50-7839f2cf1e72",
  "pubblication_date": null,
  "ordering": 0,
  "og_image": null,
  "url_node": {
    "id": 46,
    "permalink": "/",
    "related_name": "camomilla_page"
  },
  "parent_page": null
}
```

The respose will not include field translations since the response has the content already translated in the active language.
But if you need also some other language you can specify the `included_translations` parameter in the request.

`/api/camomilla/pages-router/<page_url>?included_translations=it`

The `included_translations` parameter accepts a comma separated list of languages or the value `all` to include all the translations.
