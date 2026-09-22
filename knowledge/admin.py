from django.contrib import admin

# Register your models here.
from django.contrib import admin

from .models import (
    KnowledgeArticle,
    Service,
    Product,
    TrainingCourse,
)


@admin.register(KnowledgeArticle)
class KnowledgeArticleAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "category",
        "is_active",
        "priority",
        "updated_at",
    )

    list_filter = (
        "category",
        "is_active",
    )

    search_fields = (
        "title",
        "content",
        "keywords",
    )


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "is_active",
        "updated_at",
    )

    list_filter = (
        "category",
        "is_active",
    )

    search_fields = (
        "name",
        "short_description",
        "description",
        "features",
    )


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "product_type",
        "price",
        "currency",
        "is_active",
    )

    list_filter = (
        "product_type",
        "is_active",
    )

    search_fields = (
        "name",
        "short_description",
        "description",
        "features",
    )


@admin.register(TrainingCourse)
class TrainingCourseAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "level",
        "duration",
        "price",
        "currency",
        "is_active",
    )

    list_filter = (
        "level",
        "is_active",
    )

    search_fields = (
        "name",
        "description",
    )