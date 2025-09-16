from django.forms import ValidationError
from camomilla.serializers.base import BaseModelSerializer
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.models import Permission
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from django.db.models import Q


class PermissionSerializer(BaseModelSerializer):
    class Meta:
        model = Permission
        fields = "__all__"


class UserProfileSerializer(BaseModelSerializer):
    user_permissions = PermissionSerializer(read_only=True, many=True)
    group_permissions = serializers.SerializerMethodField()
    all_permissions = serializers.SerializerMethodField()
    password = serializers.CharField(
        write_only=True, required=False, allow_null=True, allow_blank=True
    )
    repassword = serializers.CharField(
        write_only=True, required=False, allow_null=True, allow_blank=True
    )

    class Meta:
        model = get_user_model()
        fields = "__all__"

    def get_group_permissions(self, instance):
        return PermissionSerializer(
            Permission.objects.filter(
                group__pk__in=instance.groups.values_list("pk", flat=True)
            ),
            context=self.context,
            many=True,
        ).data

    def get_all_permissions(self, instance):
        return PermissionSerializer(
            Permission.objects.filter(
                Q(group__pk__in=instance.groups.values_list("pk", flat=True))
                | Q(pk__in=instance.user_permissions.values_list("pk", flat=True))
            ),
            context=self.context,
            many=True,
        ).data

    def validate_password(self, value):
        password_validation.validate_password(value)
        return value

    def validate_repassword(self, value):
        if "password" in self.initial_data:
            if not value:
                raise ValidationError(_("This field is required"))
            if self.initial_data["password"] != value:
                raise ValidationError(_("Passwords do not match."))
        return value

    def update(self, instance, validated_data):
        user = super(UserSerializer, self).update(instance, validated_data)
        if "password" in validated_data:
            user.set_password(validated_data["password"])
            user.save()
        return user


class UserSerializer(BaseModelSerializer):
    id = serializers.IntegerField(read_only=True)
    password = serializers.CharField(
        write_only=True, required=False, allow_null=True, allow_blank=True
    )
    level = serializers.CharField(required=False)
    has_token = serializers.SerializerMethodField("get_token", read_only=True)

    def get_token(self, obj):
        return hasattr(obj, "auth_token")

    class Meta:
        model = get_user_model()
        fields = (
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "password",
            "level",
            "user_permissions",
            "has_token",
            "is_superuser",
            "is_staff",
            "is_active",
            "date_joined",
            "last_login",
        )

    def validate_password(self, value):
        password_validation.validate_password(value)
        return value

    def create(self, validated_data):
        user = super(UserSerializer, self).create(validated_data)
        user.set_password(validated_data["password"])
        user.save()
        return user

    def update(self, instance, validated_data):
        user = super(UserSerializer, self).update(instance, validated_data)
        if "password" in validated_data:
            user.set_password(validated_data["password"])
            user.save()
        return user
