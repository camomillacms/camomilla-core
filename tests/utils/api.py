from django.contrib.auth.models import User
from rest_framework.test import APIClient

client = APIClient()


def login_superuser():
    User.objects.create_superuser("admin", "admin@test.com", "adminadmin")
    response = client.post(
        "/api/camomilla/token-auth/", {"username": "admin", "password": "adminadmin"}
    )
    return response.json()["token"]


def login_user():
    User.objects.create_user("user", "user@test.com", "useruser")
    response = client.post(
        "/api/camomilla/token-auth/", {"username": "user", "password": "useruser"}
    )
    return response.json()["token"]


def login_staff():
    User.objects.create_user("staff", "staff@test.com", "staffstaff", is_staff=True)
    response = client.post(
        "/api/camomilla/token-auth/", {"username": "staff", "password": "staffstaff"}
    )
    return response.json()["token"]
