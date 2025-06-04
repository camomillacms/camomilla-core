# 🚀 Bootstrap your project

Ready to start building amaing things with camomilla?

This guide will help you to setup your project in a few steps!

## 📦 Quick Setup

::: tip Env Virtualization 👾
Use a virtualenv to isolate your project's dependencies from the system's python installation before starting. Check out [virtualenvwrapper](https://virtualenvwrapper.readthedocs.io/en/latest/) for more information.
:::

Install django-camomilla-cms and django from pip

```bash
$ pip install django
$ pip install django-camomilla-cms==6.0.0
```

Create a new django project

```bash
$ django-admin startproject <project_name>
$ cd <project_name>
```

Create a dedicated folder for camomilla migrations

```bash
$ mkdir -p camomilla_migrations
$ touch camomilla_migrations.__init__.py
```

Create migrations and prepare the database

```bash
$ python manage.py makemigrations camomilla
$ python manage.py migrate
```

Add camomilla and camomilla dependencies to your project's INSTALLED_APPS

```python
# <project_name>/settings.py

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

Run the server

```bash
$ python manage.py runserver
```
