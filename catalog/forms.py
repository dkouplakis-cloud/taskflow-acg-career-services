
"""
Forms for TaskFlow's career services catalogue.

Provide server-side validation and support
for the custom administration interface.
"""

from django import forms
from django.utils.text import slugify

from .models import Category


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