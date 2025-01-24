# camomilla django cms [![PyPI](https://img.shields.io/pypi/v/django-camomilla-cms?style=flat-square)](https://pypi.org/project/django-camomilla-cms) ![Codecov](https://img.shields.io/codecov/c/github/camomillacms/camomilla-core?style=flat-square) ![GitHub Workflow Status](https://img.shields.io/github/workflow/status/camomillacms/camomilla-core/Test,%20Coverage%20and%20Release?style=flat-square) [![GitHub](https://img.shields.io/github/license/camomillacms/camomilla-core?style=flat-square)](./LICENSE)

## Install 

```shell
$ pip install django-camomilla-cms
```

## Setup 
```shell
$ mkdir -p camomilla_migrations
$ touch camomilla_migrations.__init__.py
$ python manage.py makemigrations camomilla
$ python manage.py migrate camomilla
```


## Settings

Camomilla brings a lot of default settings you can include in your project's ones

    from camomilla.defaults import *

Remember to add all the required applications in your project

```python
INSTALLED_APPS = [
    ...
    'camomilla', # always needed
    'camomilla.theme', # needed to customize admin interface
    'djsuperadmin', # needed if you whant to use djsuperadmin for contents
    'modeltranslation', # needed if your website is multilanguage (can be added later)
    'rest_framework',  # always needed
    'rest_framework.authtoken',  # always needed
    ...
]
```

## Run the server

    $ python manage.py runserver

## Run tests

    pip install -r requirements-dev.txt
    make test
