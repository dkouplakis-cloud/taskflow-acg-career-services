from django.core.exceptions import ValidationError
from django.db import models

from decimal import Decimal
from django.core.validators import MinValueValidator


class Category(models.Model):
    """
    Organize catalogue items into categories
    and subcategories.
    """

    name = models.CharField(max_length=100)

    slug = models.SlugField(
        max_length=120,
        unique=True
    )

    description = models.TextField(blank=True)

    # A category without a parent is a top-level category.
    # A category with a parent is a subcategory.
    parent = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='subcategories'
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'categories'

    def clean(self):
        """
        Prevent categories from becoming their own
        ancestors through circular relationships.
        """
        super().clean()

        ancestor = self.parent
        visited = set()

        while ancestor is not None:
            if ancestor.pk == self.pk or ancestor.pk in visited:
                raise ValidationError({
                    'parent': 'A circular category relationship is not allowed.'
                })

            visited.add(ancestor.pk)
            ancestor = ancestor.parent

    def __str__(self):
        if self.parent:
            return f'{self.parent.name} / {self.name}'

        return self.name


class CatalogItem(models.Model):
    """
    Represent a career service, workshop, event,
    or resource in the public TaskFlow catalogue.

    Prices are simulated for the academic project.
    """

    class DeliveryFormat(models.TextChoices):
        IN_PERSON = 'in_person', 'In Person'
        ONLINE = 'online', 'Online'
        HYBRID = 'hybrid', 'Hybrid'

    name = models.CharField(max_length=150)

    slug = models.SlugField(
        max_length=170,
        unique=True
    )

    description = models.TextField()

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='items'
    )

    image = models.ImageField(
        upload_to='catalog/items/'
    )

    price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[
            MinValueValidator(Decimal('0.00'))
        ]
    )

    delivery_format = models.CharField(
        max_length=20,
        choices=DeliveryFormat.choices,
        default=DeliveryFormat.IN_PERSON
    )

    target_audience = models.CharField(
        max_length=120,
        blank=True
    )

    duration_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)]
    )

    is_available = models.BooleanField(
        default=True
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
        ordering = ['name']

    def __str__(self):
        return self.name