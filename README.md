[![PyPI](https://img.shields.io/pypi/v/django-camomilla-cms?style=flat-square)](https://pypi.org/project/django-camomilla-cms)
[![Django Versions](https://img.shields.io/badge/django-3.2%20%7C%204.2%20%7C%205.1-blue?style=flat-square)](https://www.djangoproject.com/)
[![Build](https://img.shields.io/github/actions/workflow/status/camomillacms/camomilla-core/ci.yml?branch=master&style=flat-square)](https://github.com/camomillacms/camomilla-core/actions)
[![Last Commit](https://img.shields.io/github/last-commit/camomillacms/camomilla-core?style=flat-square)](https://github.com/camomillacms/camomilla-core/commits/master)
[![Contributors](https://img.shields.io/github/contributors/camomillacms/camomilla-core?style=flat-square)](https://github.com/camomillacms/camomilla-core/graphs/contributors)
[![Open Issues](https://img.shields.io/github/issues/camomillacms/camomilla-core?style=flat-square)](https://github.com/camomillacms/camomilla-core/issues)
[![Codecov](https://img.shields.io/codecov/c/github/camomillacms/camomilla-core?style=flat-square)](https://app.codecov.io/gh/camomillacms/camomilla-core/tree/master/camomilla)
[![License](https://img.shields.io/github/license/camomillacms/camomilla-core?style=flat-square)](./LICENSE)


<br>
<br>
<br>
<br>
<div align="center">
    <picture>
        <source media="(prefers-color-scheme: dark)" srcset="https://camomillacms.github.io/camomilla-core/images/camomilla-logo-dark.svg?v=1">
        <source media="(prefers-color-scheme: light)" srcset="https://camomillacms.github.io/camomilla-core/images/camomilla-logo-light.svg?v=1">
        <img alt="Fallback image description" src="https://camomillacms.github.io/camomilla-core/images/camomilla-logo-light.svg?v=1" style="width: 250px; height: auto;">
    </picture>
</div>
<h3 align="center"">Our beloved Django CMS</h3>
<br>

## ⭐️ Features

<!-- Highlight some of the features your module provide here -->

- 🧘‍♀️ &nbsp;Built on top of the django framework
- 🥨 &nbsp;Beaked page abstract model to let you manage everything you need as a page.
- 🏞️ &nbsp;Optimized media management with autoresize
- 👯 &nbsp;Enable relations inside django JSONFields
- ⚡️ &nbsp;AutoCreate api endpoints from models
- 🚧 &nbsp;Enable JsonSchema directly in models endpoints

Camomilla is a Django CMS that allows you to create and manage your website's content with ease. It provides a simple and intuitive interface for managing pages, media, and other content types. Camomilla is built on top of the Django framework, which means it inherits all the features and benefits of Django framework.
We try to continuously improve Camomilla by adding new features and fixing bugs. You can check the [CHANGELOG](./CHANGELOG.md) to see what has been added in the latest releases.

## 📦 Quick Start

Here you can find some quick setup instructions to get started with Camomilla. For more detailed information, please refer to the [documentation](https://camomillacms.github.io/camomilla-core/).

> [!TIP]
>
> #### Env Virtualization 👾
>
> Use a virtualenv to isolate your project's dependencies from the system's python installation before starting. Check out [virtualenvwrapper](https://virtualenvwrapper.readthedocs.io/en/latest/) for more information.

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

## 🧑‍💻 How to Contribute

We welcome contributions to Camomilla! If you want to contribute, please read our [contributing guide](./CONTRIBUTING.md) for more information on how to get started.
