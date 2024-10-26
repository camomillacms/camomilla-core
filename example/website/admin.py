from django.contrib import admin
from .models import TestModel, SimpleRelationModel


class SimpleRelationModelAdmin(admin.ModelAdmin):
    pass


class TestModelAdmin(admin.ModelAdmin):
    pass


admin.site.register(SimpleRelationModel, SimpleRelationModelAdmin)
admin.site.register(TestModel, TestModelAdmin)
