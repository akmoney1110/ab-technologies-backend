from django.db import models

# Create your models here.
from django.db import models


class KnowledgeArticle(models.Model):
    CATEGORY_CHOICES = [
        ("company", "Company"),
        ("service", "Service"),
        ("industry", "Industry"),
        ("product", "Product"),
        ("training", "Training"),
        ("faq", "FAQ"),
        ("policy", "Policy"),
        ("general", "General"),
    ]

    title = models.CharField(max_length=255)

    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default="general",
    )

    content = models.TextField()

    keywords = models.TextField(
        blank=True,
        help_text="Comma-separated keywords."
    )

    is_active = models.BooleanField(default=True)

    priority = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-priority", "-updated_at"]

    def __str__(self):
        return self.title
    


class Service(models.Model):
    name = models.CharField(max_length=255)

    slug = models.SlugField(
        unique=True
    )

    short_description = models.TextField()

    description = models.TextField(
        blank=True
    )

    category = models.CharField(
        max_length=100,
        blank=True
    )

    industries = models.TextField(
        blank=True,
        help_text="Comma-separated industries."
    )

    features = models.TextField(
        blank=True,
        help_text="Comma-separated features."
    )

    is_active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name    
    




class Product(models.Model):
    PRODUCT_TYPES = [
        ("software", "Software"),
        ("hardware", "Hardware"),
        ("saas", "SaaS"),
        ("digital", "Digital Product"),
        ("other", "Other"),
    ]

    name = models.CharField(
        max_length=255
    )

    slug = models.SlugField(
        unique=True
    )

    product_type = models.CharField(
        max_length=30,
        choices=PRODUCT_TYPES,
        default="software",
    )

    short_description = models.TextField()

    description = models.TextField(
        blank=True
    )

    features = models.TextField(
        blank=True
    )

    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )

    currency = models.CharField(
        max_length=10,
        default="USD"
    )

    is_active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name    
    



class TrainingCourse(models.Model):
    name = models.CharField(
        max_length=255
    )

    slug = models.SlugField(
        unique=True
    )

    description = models.TextField()

    level = models.CharField(
        max_length=50,
        blank=True
    )

    duration = models.CharField(
        max_length=100,
        blank=True
    )

    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )

    currency = models.CharField(
        max_length=10,
        default="USD"
    )

    is_active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name    