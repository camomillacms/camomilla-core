import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from .utils.api import login_superuser
from camomilla.models import Tag, Article

client = APIClient()


@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_create_tag_no_access():
    response = client.post("/api/camomilla/tags/", {"name_en": "First tag"})
    assert response.status_code == 401


@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_crud_tag():
    # Create
    token = login_superuser()
    client.credentials(HTTP_AUTHORIZATION="Token " + token)
    response = client.post("/api/camomilla/tags/", {"name_en": "First tag"})

    assert response.json()["name"] == "First tag"
    assert len(Tag.objects.all()) == 1
    assert response.status_code == 201

    # Create another with a different language
    response = client.post("/api/camomilla/tags/", {"name_it": "Secondo tag"})
    assert response.json()["translations"]["it"]["name"] == "Secondo tag"
    assert len(Tag.objects.all()) == 2
    assert response.status_code == 201

    # Translate the second one in english
    response = client.patch(
        "/api/camomilla/tags/2/",
        {"translations": {"en": {"name": "Second tag"}}},
        format="json",
    )
    assert response.json()["translations"]["en"]["name"] == "Second tag"
    assert response.json()["translations"]["it"]["name"] == "Secondo tag"
    assert len(Tag.objects.all()) == 2

    assert response.status_code == 200

    # Get the tags in english
    response = client.get("/api/camomilla/tags/")

    assert response.json()[0]["name"] == "Second tag"

    # Get the tags in italianith fallbacks!
    response = client.get("/api/camomilla/tags/?language=it")

    assert response.json()[0]["name"] == "Secondo tag"

    # Delete the tag
    response = client.delete("/api/camomilla/tags/2/")

    assert len(Tag.objects.all()) == 1

    assert response.status_code == 204


@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_create_article_with_nested_tags():
    """Test creating an article with tags as nested data to cover RelatedField.to_internal_value and many_init"""
    token = login_superuser()
    client.credentials(HTTP_AUTHORIZATION="Token " + token)
    
    # Create tags first
    tag1_response = client.post("/api/camomilla/tags/", {"name_en": "Tech"})
    tag2_response = client.post("/api/camomilla/tags/", {"name_en": "News"})
    
    tag1_id = tag1_response.json()["id"]
    tag2_id = tag2_response.json()["id"]
    
    # Create article with tags as nested data (this exercises RelatedField.to_internal_value with dict input)
    article_data = {
        "title_en": "Test Article",
        "permalink": "test-article",
        "content": "Test content",
        "tags": [
            {"id": tag1_id},  # Dict input with existing tag
            {"id": tag2_id}   # Dict input for another existing tag
        ]
    }
    
    response = client.post("/api/camomilla/articles/", article_data, format="json")
    assert response.status_code == 201
    
    article = Article.objects.get(id=response.json()["id"])
    assert article.title_en == "Test Article"
    assert article.tags.count() == 2  # Should have 2 tags
    
    tag_names = [tag.name for tag in article.tags.all()]
    assert "Tech" in tag_names
    assert "News" in tag_names


@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_create_and_update_user():
    """Test creating and updating users to cover UserSerializer validation and CRUD methods"""
    token = login_superuser()
    client.credentials(HTTP_AUTHORIZATION="Token " + token)
    
    # Create user (exercises UserSerializer.create and validate_password)
    user_data = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpass123",
        "first_name": "Test",
        "last_name": "User"
    }
    
    response = client.post("/api/camomilla/users/", user_data, format="json")
    assert response.status_code == 201
    
    user_id = response.json()["id"]
    user = get_user_model().objects.get(id=user_id)
    assert user.username == "testuser"
    assert user.email == "test@example.com"
    assert user.check_password("testpass123")
    
    # Update user password (exercises UserSerializer.update)
    update_data = {
        "password": "newpass123"
    }
    
    response = client.patch(f"/api/camomilla/users/{user_id}/", update_data, format="json")
    assert response.status_code == 200
    
    user.refresh_from_db()
    assert user.check_password("newpass123")


@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_current_user_profile():
    """Test current user endpoint to cover UserProfileSerializer methods"""
    from django.contrib.auth.models import Group, Permission
    
    token = login_superuser()
    client.credentials(HTTP_AUTHORIZATION="Token " + token)
    
    # Create a group with permissions
    group = Group.objects.create(name="Test Group")
    perm = Permission.objects.filter(codename="add_user").first()
    if perm:
        group.permissions.add(perm)
    
    # Get current user (should be superuser created by login_superuser)
    response = client.get("/api/camomilla/users/current/")
    assert response.status_code == 200
    
    data = response.json()
    # Check that group_permissions and all_permissions are included (covers get_group_permissions and get_all_permissions)
    assert "group_permissions" in data
    assert "all_permissions" in data
    assert isinstance(data["group_permissions"], list)
    assert isinstance(data["all_permissions"], list)
    
    # Update current user password (covers UserProfileSerializer.validate_password, validate_repassword, update)
    update_data = {
        "password": "newpassword123",
        "repassword": "newpassword123"
    }
    
    response = client.put("/api/camomilla/users/current/", update_data, format="json")
    assert response.status_code == 200


@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_content_djsuperadmin_action():
    """Test the djsuperadmin action in ContentViewSet to cover the custom action method"""
    token = login_superuser()
    client.credentials(HTTP_AUTHORIZATION="Token " + token)
    
    # Create a content first
    content_data = {
        "identifier": "test-content",
        "content_en": "Initial content"
    }
    
    response = client.post("/api/camomilla/contents/", content_data, format="json")
    assert response.status_code == 201
    content_id = response.json()["id"]
    
    # Test GET on djsuperadmin action
    response = client.get(f"/api/camomilla/contents/{content_id}/djsuperadmin/")
    assert response.status_code == 200
    data = response.json()
    assert "content" in data
    assert data["content"] == "Initial content"
    
    # Test PATCH on djsuperadmin action
    patch_data = {"content": "Updated content via djsuperadmin"}
    response = client.patch(f"/api/camomilla/contents/{content_id}/djsuperadmin/", patch_data, format="json")
    assert response.status_code == 200
    data = response.json()
    assert data["content"] == "Updated content via djsuperadmin"
    
    # Verify the content was actually updated in the database
    from camomilla.models import Content
    content = Content.objects.get(id=content_id)
    assert content.content == "Updated content via djsuperadmin"


@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_languages_endpoint():
    """Test the languages endpoint to cover LanguageViewSet"""
    token = login_superuser()
    client.credentials(HTTP_AUTHORIZATION="Token " + token)
    
    response = client.get("/api/camomilla/languages/")
    assert response.status_code == 200
    data = response.json()
    assert "language_code" in data
    assert "languages" in data
    assert isinstance(data["languages"], list)
    assert len(data["languages"]) > 0
