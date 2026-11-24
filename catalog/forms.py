
"""
Forms for TaskFlow's career services catalogue.

Provide server-side validation and support
for the custom administration interface.
"""

from django import forms
from django.utils.text import slugify
from django.core.files.uploadedfile import UploadedFile
from .models import Category, CatalogItem


class CategoryForm(forms.ModelForm):
    """
    Create and edit catalogue categories.

    Generate unique slugs automatically and
    validate category relationships.
    """

    class Meta:
        model = Category

        fields = [
            "name",
            "description",
            "parent",
            "is_active",
        ]

        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g. Career Workshops",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Describe this category...",
                }
            ),
            "parent": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # A category may have no parent.
        self.fields["parent"].required = False
        self.fields["parent"].empty_label = (
            "No parent — top-level category"
        )

        # Prevent selecting the category itself.
        # The Category model also rejects circular
        # relationships involving descendants.
        if self.instance.pk:
            self.fields["parent"].queryset = (
                Category.objects.exclude(
                    pk=self.instance.pk
                )
            )

    def save(self, commit=True):
        category = super().save(commit=False)

        # Keep an existing slug stable when editing.
        if not category.slug:

            base_slug = (
                slugify(
                    category.name,
                    allow_unicode=True
                )[:110].strip("-") or "category"
            )

            candidate = base_slug
            counter = 2

            # Create a unique slug if another
            # category already uses this name.
            while Category.objects.filter(
                slug=candidate
            ).exclude(pk=category.pk).exists():

                suffix = f"-{counter}"
                candidate = (
                    base_slug[:120 - len(suffix)]
                    + suffix
                )
                counter += 1

            category.slug = candidate

        if commit:
            category.save()
            self.save_m2m()

        return category

class CatalogItemForm(forms.ModelForm):
    """
    Create and edit career services catalogue items.

    Validate item information and generate unique
    slugs while preserving existing slugs on edit.
    """

    class Meta:
        model = CatalogItem

        fields = [
            "name",
            "description",
            "category",
            "image",
            "price",
            "delivery_format",
            "target_audience",
            "duration_minutes",
            "is_available",
            "is_active",
        ]

        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g. CV Writing Workshop",
                }
            ),

            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": "Describe this career service...",
                }
            ),

            "category": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "image": forms.ClearableFileInput(
                attrs={
                    "class": "form-control",
                    "accept": ".jpg,.jpeg,.png,.webp",
                }
            ),

            "price": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0",
                    "step": "0.01",
                }
            ),

            "delivery_format": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "target_audience": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g. Undergraduate students",
                }
            ),

            "duration_minutes": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "1",
                    "step": "1",
                }
            ),

            "is_available": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),

            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),
        }

    
    def clean_image(self):
        """
        Validate uploaded catalogue images.

        Allow JPEG, PNG, and WebP images up to
        5 MiB. Preserve existing images on edit.
        """

        image = self.cleaned_data.get("image")

        # No new file was uploaded.
        # An existing image may be retained on edit.
        if not isinstance(image, UploadedFile):
            return image

        # Maximum allowed upload size: 5 MiB.
        max_size = 5 * 1024 * 1024

        if image.size > max_size:
            raise forms.ValidationError(
                "The image must not exceed 5 MB."
            )

        # Django's ImageField has already used
        # Pillow to validate the uploaded image.
        allowed_formats = {"JPEG", "PNG", "WEBP"}

        image_format = getattr(
            getattr(image, "image", None),
            "format",
            None
        )

        if image_format not in allowed_formats:
            raise forms.ValidationError(
                "Only JPEG, PNG, and WebP images are allowed."
            )

        return image

    def save(self, commit=True):
        """
        Automatically generate a unique slug.

        Preserve the original slug when editing
        an existing catalogue item.
        """

        item = super().save(commit=False)

        if not item.slug:

            base_slug = (
                slugify(
                    item.name,
                    allow_unicode=True
                )[:160].strip("-") or "catalog-item"
            )

            candidate = base_slug
            counter = 2

            while CatalogItem.objects.filter(
                slug=candidate
            ).exclude(pk=item.pk).exists():

                suffix = f"-{counter}"

                candidate = (
                    base_slug[:170 - len(suffix)]
                    + suffix
                )

                counter += 1

            item.slug = candidate

        if commit:
            item.save()
            self.save_m2m()

        return item