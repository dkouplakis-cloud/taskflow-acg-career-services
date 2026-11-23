from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .forms import CategoryForm
from .models import Category
from core.models import UserProfile

class ManagementDashboardTests(TestCase):
    """
    Test access to TaskFlow's custom
    catalogue administration dashboard.
    """

    def test_administrator_can_access_dashboard(self):
        # Create a temporary user in the test database.
        user = get_user_model().objects.create_user(
            username="catalog_admin_test",
            password="TestPassword123!"
        )

        # Assign the Administrator role.
        profile = user.profile
        profile.role = UserProfile.Role.ADMIN
        profile.save()

        # Authenticate the temporary administrator.
        self.client.force_login(user)

        # Request the actual dashboard URL.
        response = self.client.get(
            reverse("catalog_management:dashboard")
        )

        # Verify successful access.
        self.assertEqual(
            response.status_code,
            200
        )

        # Verify Django renders the correct template.
        self.assertTemplateUsed(
            response,
            "catalog/management/dashboard.html"
        )

        # Verify that dashboard content is present.
        self.assertContains(
            response,
            "Catalogue Overview"
        )
    
    def test_regular_user_cannot_access_dashboard(self):
        """
        Regular Users must not access the
        custom catalogue management dashboard.
        """

        user = get_user_model().objects.create_user(
            username="catalog_regular_test",
            password="TestPassword123!"
        )

        # New accounts automatically receive
        # the Regular User role.
        self.assertEqual(
            user.profile.role,
            UserProfile.Role.REGULAR
        )

        self.client.force_login(user)

        response = self.client.get(
            reverse("catalog_management:dashboard")
        )

        self.assertEqual(
            response.status_code,
            403
        )

class CategoryFormTests(TestCase):
    """
    Verify category creation, slug generation,
    editing, and hierarchy validation.
    """

    def test_creating_top_level_category(self):
        form = CategoryForm(
            data={
                "name": "Career Workshops",
                "description": "Professional development",
                "parent": "",
                "is_active": "on",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        category = form.save()

        self.assertEqual(
            category.slug,
            "career-workshops"
        )
        self.assertIsNone(category.parent)
        self.assertTrue(category.is_active)

    def test_duplicate_names_generate_unique_slugs(self):
        Category.objects.create(
            name="Career Workshops",
            slug="career-workshops"
        )

        form = CategoryForm(
            data={
                "name": "Career Workshops",
                "description": "",
                "parent": "",
                "is_active": "on",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        category = form.save()

        self.assertEqual(
            category.slug,
            "career-workshops-2"
        )

    def test_existing_slug_is_preserved_when_editing(self):
        category = Category.objects.create(
            name="Career Workshops",
            slug="career-workshops"
        )

        form = CategoryForm(
            data={
                "name": "Updated Career Workshops",
                "description": "",
                "parent": "",
                "is_active": "on",
            },
            instance=category
        )

        self.assertTrue(form.is_valid(), form.errors)
        updated = form.save()

        self.assertEqual(
            updated.slug,
            "career-workshops"
        )

    def test_subcategory_can_have_parent(self):
        parent = Category.objects.create(
            name="Career Services",
            slug="career-services"
        )

        form = CategoryForm(
            data={
                "name": "Interview Preparation",
                "description": "",
                "parent": str(parent.pk),
                "is_active": "on",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        subcategory = form.save()

        self.assertEqual(
            subcategory.parent,
            parent
        )

    def test_circular_category_relationship_is_rejected(self):
        parent = Category.objects.create(
            name="Career Services",
            slug="career-services"
        )

        child = Category.objects.create(
            name="Interview Preparation",
            slug="interview-preparation",
            parent=parent
        )

        # Attempt to make the parent a child
        # of its own existing subcategory.
        form = CategoryForm(
            data={
                "name": "Career Services",
                "description": "",
                "parent": str(child.pk),
                "is_active": "on",
            },
            instance=parent
        )

        self.assertFalse(form.is_valid())
        self.assertIn("parent", form.errors)