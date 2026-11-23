from django.core.exceptions import ValidationError
from django.db import models

from django.conf import settings
from django.core.validators import MaxValueValidator
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

class CatalogRating(models.Model):
    """
    Store a user's rating and optional review
    for a catalogue item.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='catalog_ratings'
    )

    item = models.ForeignKey(
        CatalogItem,
        on_delete=models.CASCADE,
        related_name='ratings'
    )

    score = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(5)
        ]
    )

    review = models.TextField(
        max_length=2000,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ['-updated_at']

        constraints = [
            models.UniqueConstraint(
                fields=['user', 'item'],
                name='unique_catalog_rating_per_user'
            ),
            models.CheckConstraint(
                condition=models.Q(
                    score__gte=1,
                    score__lte=5
                ),
                name='catalog_rating_score_1_to_5'
            )
        ]

    def __str__(self):
        return (
            f'{self.user} rated '
            f'{self.item.name}: {self.score}/5'
        )

class CatalogActivity(models.Model):
    """
    Track authenticated users' catalogue views
    and searches for personalized recommendations.
    """

    class ActivityType(models.TextChoices):
        VIEW = 'view', 'Item View'
        SEARCH = 'search', 'Catalogue Search'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='catalog_activities'
    )

    activity_type = models.CharField(
        max_length=10,
        choices=ActivityType.choices
    )

    item = models.ForeignKey(
        CatalogItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activities'
    )

    search_query = models.CharField(
        max_length=200,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ['-created_at']

        indexes = [
            models.Index(
                fields=['user', '-created_at']
            )
        ]

    def clean(self):
        super().clean()

        if self.activity_type == self.ActivityType.VIEW:
            if self.item_id is None:
                raise ValidationError({
                    'item': 'An item view requires a catalogue item.'
                })

        if self.activity_type == self.ActivityType.SEARCH:
            if not self.search_query.strip():
                raise ValidationError({
                    'search_query': 'A search query is required.'
                })

    def __str__(self):
        return (
            f'{self.user} - '
            f'{self.get_activity_type_display()}'
        )

class Order(models.Model):
    """
    Represent a simulated catalogue checkout.

    No real payment is processed.
    """

    class OrderStatus(models.TextChoices):
        PLACED = 'placed', 'Placed'
        CONFIRMED = 'confirmed', 'Confirmed'
        CANCELLED = 'cancelled', 'Cancelled'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='catalog_orders'
    )

    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.PLACED
    )

    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[
            MinValueValidator(Decimal('0.00'))
        ]
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Order #{self.pk} - {self.user}'

class OrderItem(models.Model):
    """
    Store an individual item within a simulated order.

    Item details and prices are captured at checkout
    to preserve the original order history.
    """

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items'
    )

    catalog_item = models.ForeignKey(
        CatalogItem,
        on_delete=models.PROTECT,
        related_name='order_items'
    )

    item_name = models.CharField(
        max_length=150
    )

    quantity = models.PositiveIntegerField(
        validators=[
            MinValueValidator(1)
        ]
    )

    unit_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal('0.00'))
        ]
    )

    class Meta:
        ordering = ['pk']

    @property
    def subtotal(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return (
            f'{self.quantity} x {self.item_name} '
            f'(Order #{self.order_id})'
        )