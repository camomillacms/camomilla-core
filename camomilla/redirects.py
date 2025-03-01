from django.urls import path
from django.shortcuts import redirect


url_patterns = [
    path(
        "profiles/me/", lambda _: redirect("../../users/current/"), name="profiles-me"
    ),
    path("sitemap/", lambda _: redirect("../pages/"), name="sitemap"),
]
