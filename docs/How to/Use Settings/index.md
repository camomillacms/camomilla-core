# ⚙️ Use Settings

Camomilla comes with a set of settings that you can use to customize the behaviour of the app.

Here is a list of all the settings you can use, with their default values:

```python
# <project_name>/settings.py

CAMOMILLA = {
    "PROJECT_TITLE": "" # the title of your project (a rarely used setting :P),
    "ROUTER": {
        "BASE_URL": "" # change this if you want to serve camomilla from a subpath
    },
    "MEDIA": {
        "OPTIMIZE": {
            "MAX_WIDTH": 1980, # max width for images optimization
            "MAX_HEIGHT": 1400, # max height for images optimization
            "DPI": 30, # dpi for images optimization
            "ENABLE": True # enable or disable images optimization
        },
        "THUMBNAIL": {
            "FOLDER": "", # folder where thumbnails will be saved
            "WIDTH": 50, # default width for thumbnails
            "HEIGHT": 50 # default height for thumbnails
        }
    },
    "RENDER": {
        "TEMPLATE_CONTEXT_FILES": [], # add here the path to your custom context files
        "AUTO_CREATE_HOMEPAGE": True, # if True, a homepage will be created automatically
        "ARTICLE": {
            "DEFAULT_TEMPLATE": "", # default template for articles
            "INJECT_CONTEXT": None # function to inject context in articles templates
        },
        "PAGE": {
            "DEFAULT_TEMPLATE": "", # default template for pages
            "INJECT_CONTEXT": None # function to inject context in pages templates
        }
    },
    "STRUCTURED_FIELD": {
        "CACHE_ENABLED": True # if True, the structured field will use a cache system to avoid multiple queries to the database
    }
    "API": {
        "NESTING_DEPTH": 10 # default nesting depth for serializers
    },
    "DEBUG": False # enable or disable debug mode
}
```

You can find more information about each setting in the relative section of intrest. Browse [How to](../How%20to/README.md) guides to find what you are looking for!