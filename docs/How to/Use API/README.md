# 🐝 Use API 

Camomilla comes with many api endpoint builded with Django Rest Framework. 

To use the endpoints you need to add the handler to the project urls.py

```python
# <project_name>/urls.py
urlpatterns += path('api/camomilla/', include('camomilla.urls'))
```

::: warning ⚠️ Beware!
Remember that if you use camomilla pages `dynamic_pages_urls` handler should always be the last handler of your urlpatterns list.
:::

By default every endpoint comes with a full CRUD in the style of django rest framework with some mode feature beaked in.

## 🧱 Base Classes

If you need to implement your own api, we suggest to use camomilla `BaseModelSerializer` and `BaseModelViewset` as the base class of your serializer and viewset respectively. 

```python
class MyModelSerializer(BaseModelSerializer):
    class Meta:
        model = MyModel
        fields = "__all__"
        depth = 5
```

```python
class MyModelViewSet(BaseModelViewset):
    queryset = MyModel.objects.all()
    serializer_class = MyModelSerializer
    permission_classes = (CamomillaBasePermissions,)
    model = MyModel
    search_fields = ["title", "description",]
```

This will provide to your endpoint all the features of standard camomilla api.


## 🖲️ The model_api.register decorator
If you need to create a standard api endpoint  you can take advantage of model_api register decorator. 
To use this aproach you need to add the model_api handler to your project urls.py

```python
# <project_name>/urls.py
urlpatterns += path('api/models/', include('camomilla.model_api'))
```

Then you just need to decorate your model with `@model_api.register`

```python
from camomilla import model_api

@model_api.register()
class MyModel(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
```

This will create an api endpoint with url  `/api/models/my-model` with full camomilla api capabilities.

You can also personalize the view or the serializer passing some parameter to the register function:

-  `base_serializer`: The base serializer to use for the model.
-  `base_viewset`: The base viewset to use for the model.
-  `serializer_meta`: The meta class to use for the serializer.
-  `viewset_attrs`: The attributes to add to the viewset.
-  `filters`: The filters to apply to the queryset.


## 🗂️ List endpoint

__URL Structure:__
 - `api/camomilla/<model_name>`

__Simple Response:__
```json
[
    { ... single model data ... }, {}, {}
]
```

### Use Pagination

List api comes with a builtin paginator.
The paginated response is disabled by defualt to be compliant with default rest framework lists. 
If you want a paginated response you need to specify the page size in the request as a GET parameter.

For example, the request `/api/camomilla/<model_name>?items=10`, will return data splittet 10 elements per page.

__Paginated Response:__
```json
{
    "items": [
        { ... single model data ... }, {}, {}
    ],
    "paginator": {
        "count": 1, // number of elements
        "page": 1, // current page number
        "has_next": false, // has a next page
        "has_previous": false, // has a previous page
        "pages": 1, // total number of pages
        "page_size": 10 // number of elements per page (depends on items parameter)
    }
}
```

### Use Filtering
List api comes with a builtin filter syntax.
You can filter data with GET query parameters using the following sintax:

```/api/camomilla/<model_name>?fltr=field_name=value```

This syntax can be repeated multiple times.

```/api/camomilla/<model_name>?fltr=field_name=value&fltr=field_name=value```

In place of `field_name` you can use any [django filter argument](https://docs.djangoproject.com/en/4.2/topics/db/queries/#retrieving-specific-objects-with-filters).  

If the value has commas and is between square brackets like `[val1,val2,val3]` it will be treated as an array.
For example you can filter some model like this:

```/api/camomilla/<model_name>?fltr=field_name__in=[val1,val2]```

### Use Search

You can also full text search your model with query param `search`:

```/api/camomilla/<model_name>?search=q_string```


## 🗂️ Detail endpoint

Retrieve api just returns model data serialized in a json.
The serialization goes through nested objects by default, creating on the fly nested serializers.
You can modify this behaviour decreasing the value `depth` in Serializer Meta for a single serializer or change the default option in camomilla settings.

```python
CAMOMILLA = {
    "MEDIA": {
        "API": {"NESTING_DEPTH": 10 }
    },
}
```

__URL Structure:__
 - `api/camomilla/<model_name>/<primary_key>`

__Simple Response:__
```json
{ ... single model data ... }
```
