from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.conf import settings
from django.shortcuts import resolve_url
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

class CategoryManagementViewTests(TestCase):
    """
    Test the custom Category Management views,
    including CRUD operations and permissions.
    """

    def setUp(self):
        """
        Create and authenticate a temporary
        administrator in the isolated test database.
        """

        self.admin_user = get_user_model().objects.create_user(
            username="catalog_crud_admin_test",
            password="TestPassword123!"
        )

        profile = self.admin_user.profile
        profile.role = UserProfile.Role.ADMIN
        profile.save()

        self.client.force_login(self.admin_user)

    def test_administrator_can_create_category(self):
        """
        Verify that an administrator can create
        a category using the actual Django view.
        """

        response = self.client.post(
            reverse("catalog_management:category_create"),
            data={
                "name": "Interview Preparation",
                "description": "Interview skills workshops",
                "parent": "",
                "is_active": "on",
            }
        )

        # Verify successful redirect.
        self.assertRedirects(
            response,
            reverse("catalog_management:category_list")
        )

        # Verify the category was saved.
        category = Category.objects.get(
            name="Interview Preparation"
        )

        self.assertEqual(
            category.slug,
            "interview-preparation"
        )

        self.assertIsNone(category.parent)
        self.assertTrue(category.is_active)
    
    def test_administrator_can_edit_category(self):
        """
        Verify that an administrator can update
        an existing category through the edit view.
        """

        # Create a category in the test database.
        category = Category.objects.create(
            name="Career Workshops",
            slug="career-workshops",
            description="Original description",
            is_active=True
        )

        # Submit changes through the actual edit URL.
        response = self.client.post(
            reverse(
                "catalog_management:category_edit",
                args=[category.pk]
            ),
            data={
                "name": "Professional Workshops",
                "description": "Updated workshop description",
                "parent": "",
                "is_active": "on",
            }
        )

        # Verify redirect to the category directory.
        self.assertRedirects(
            response,
            reverse("catalog_management:category_list")
        )

        # Reload the category from the database.
        category.refresh_from_db()

        # Verify the changes were saved.
        self.assertEqual(
            category.name,
            "Professional Workshops"
        )

        self.assertEqual(
            category.description,
            "Updated workshop description"
        )

        # Existing slugs must remain unchanged.
        self.assertEqual(
            category.slug,
            "career-workshops"
        )

        # Editing must not create a duplicate.
        self.assertEqual(
            Category.objects.count(),
            1
        )
    
    def test_administrator_can_delete_empty_category(self):
        """
        Verify that an administrator can delete
        an empty category through the delete view.
        """

        # Create a disposable category in the test database.
        category = Category.objects.create(
            name="Temporary Category",
            slug="temporary-category",
            description="Category for deletion testing",
            is_active=False
        )

        category_id = category.pk

        # Submit the deletion confirmation via POST.
        response = self.client.post(
            reverse(
                "catalog_management:category_delete",
                args=[category_id]
            )
        )

        # Verify redirect to the category directory.
        self.assertRedirects(
            response,
            reverse("catalog_management:category_list")
        )

        # Verify the category no longer exists.
        self.assertFalse(
            Category.objects.filter(pk=category_id).exists()
        )

        # Verify no categories remain in the test database.
        self.assertEqual(
            Category.objects.count(),
            0
        )
    
    def test_cannot_delete_category_with_subcategories(self):
        """
        Verify that a parent category cannot be
        deleted while it contains subcategories.
        """

        # Create a parent category.
        parent = Category.objects.create(
            name="Career Services",
            slug="career-services"
        )

        # Create a subcategory belonging to the parent.
        child = Category.objects.create(
            name="Interview Preparation",
            slug="interview-preparation",
            parent=parent
        )

        # Attempt to delete the parent through POST.
        response = self.client.post(
            reverse(
                "catalog_management:category_delete",
                args=[parent.pk]
            )
        )

        # The request should redirect without deletion.
        self.assertRedirects(
            response,
            reverse("catalog_management:category_list")
        )

        # The parent must remain in the database.
        self.assertTrue(
            Category.objects.filter(pk=parent.pk).exists()
        )

        # The child must also remain in the database.
        self.assertTrue(
            Category.objects.filter(pk=child.pk).exists()
        )

        # Their relationship must remain unchanged.
        child.refresh_from_db()

        self.assertEqual(
            child.parent_id,
            parent.pk
        )
    
    def test_regular_user_cannot_access_category_management(self):
        """
        Verify that regular users cannot access
        administrator-only category management pages.
        """

        # Create a regular user in the test database.
        regular_user = get_user_model().objects.create_user(
            username="catalog_regular_crud_test",
            password="TestPassword123!"
        )

        self.assertEqual(
            regular_user.profile.role,
            UserProfile.Role.REGULAR
        )

        # Create a category for testing edit/delete access.
        category = Category.objects.create(
            name="Protected Category",
            slug="protected-category"
        )

        # Switch from administrator to regular user.
        self.client.force_login(regular_user)

        # Every management page must reject regular users.
        protected_urls = [
            reverse("catalog_management:category_list"),
            reverse("catalog_management:category_create"),
            reverse(
                "catalog_management:category_edit",
                args=[category.pk]
            ),
            reverse(
                "catalog_management:category_delete",
                args=[category.pk]
            ),
        ]

        for url in protected_urls:
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertEqual(
                    response.status_code,
                    403
                )
    
    def test_regular_user_cannot_modify_categories_via_post(self):
        """
        Verify that regular users cannot create,
        edit, or delete categories using direct
        POST requests.
        """

        regular_user = get_user_model().objects.create_user(
            username="catalog_post_regular_test",
            password="TestPassword123!"
        )

        category = Category.objects.create(
            name="Protected Category",
            slug="protected-category",
            description="Original description"
        )

        # Authenticate as a regular user.
        self.client.force_login(regular_user)

        # Attempt all three write operations.
        attempts = [
            (
                reverse("catalog_management:category_create"),
                {
                    "name": "Unauthorized Category",
                    "description": "Should not be created",
                    "parent": "",
                    "is_active": "on",
                }
            ),
            (
                reverse(
                    "catalog_management:category_edit",
                    args=[category.pk]
                ),
                {
                    "name": "Unauthorized Update",
                    "description": "Should not be saved",
                    "parent": "",
                    "is_active": "on",
                }
            ),
            (
                reverse(
                    "catalog_management:category_delete",
                    args=[category.pk]
                ),
                {}
            ),
        ]

        for url, data in attempts:
            with self.subTest(url=url):
                response = self.client.post(
                    url,
                    data=data
                )

                self.assertEqual(
                    response.status_code,
                    403
                )

        # Confirm the original record still exists.
        category.refresh_from_db()

        self.assertEqual(
            category.name,
            "Protected Category"
        )

        self.assertEqual(
            category.description,
            "Original description"
        )

        # No additional categories were created.
        self.assertEqual(
            Category.objects.count(),
            1
        )
    
    def test_get_request_does_not_delete_category(self):
        """
        Verify that visiting the deletion
        confirmation page never deletes
        a category.
        """

        category = Category.objects.create(
            name="Safe Category",
            slug="safe-category"
        )

        # Open the deletion confirmation page.
        response = self.client.get(
            reverse(
                "catalog_management:category_delete",
                args=[category.pk]
            )
        )

        # The confirmation page should load.
        self.assertEqual(
            response.status_code,
            200
        )

        self.assertTemplateUsed(
            response,
            "catalog/management/category_confirm_delete.html"
        )

        # The category must remain in the database.
        self.assertTrue(
            Category.objects.filter(pk=category.pk).exists()
        )

        # The page should show the correct category.
        self.assertContains(
            response,
            "Safe Category"
        )
    
    def test_category_delete_requires_csrf_token(self):
        """
        Verify that deleting a category through POST
        without a CSRF token is rejected.
        """

        category = Category.objects.create(
            name="CSRF Protected Category",
            slug="csrf-protected-category"
        )

        # Enable actual CSRF enforcement in the test client.
        csrf_client = Client(enforce_csrf_checks=True)

        # Authenticate as the existing administrator.
        csrf_client.force_login(self.admin_user)

        # Attempt deletion without a CSRF token.
        response = csrf_client.post(
            reverse(
                "catalog_management:category_delete",
                args=[category.pk]
            )
        )

        # Django must reject the request.
        self.assertEqual(
            response.status_code,
            403
        )

        # The category must remain in the database.
        self.assertTrue(
            Category.objects.filter(pk=category.pk).exists()
        )
    
    def test_unauthenticated_user_redirected_to_login(self):
        """
        Verify that anonymous visitors are redirected
        to login when accessing category management.
        """

        category = Category.objects.create(
            name="Protected Category",
            slug="protected-category"
        )

        # Ensure the test client is unauthenticated.
        self.client.logout()

        protected_urls = [
            reverse("catalog_management:category_list"),
            reverse("catalog_management:category_create"),
            reverse(
                "catalog_management:category_edit",
                args=[category.pk]
            ),
            reverse(
                "catalog_management:category_delete",
                args=[category.pk]
            ),
        ]

        login_url = resolve_url(settings.LOGIN_URL)

        for url in protected_urls:
            with self.subTest(url=url):

                response = self.client.get(url)

                # Anonymous visitors must be redirected
                # to login rather than accessing the page.
                self.assertRedirects(
                    response,
                    f"{login_url}?next={url}",
                    fetch_redirect_response=False
                )

        # Verify that the category remains unchanged.
        self.assertTrue(
            Category.objects.filter(
                pk=category.pk
            ).exists()
        )

    def test_unauthenticated_user_cannot_modify_categories(self):
        """
        Verify that anonymous visitors cannot create,
        edit, or delete categories through POST requests.
        """

        category = Category.objects.create(
            name="Protected Category",
            slug="protected-category",
            description="Original description"
        )

        # Ensure the client is not authenticated.
        self.client.logout()

        attempts = [
            (
                reverse("catalog_management:category_create"),
                {
                    "name": "Unauthorized Category",
                    "description": "Should not be created",
                    "parent": "",
                    "is_active": "on",
                }
            ),
            (
                reverse(
                    "catalog_management:category_edit",
                    args=[category.pk]
                ),
                {
                    "name": "Unauthorized Update",
                    "description": "Should not be saved",
                    "parent": "",
                    "is_active": "on",
                }
            ),
            (
                reverse(
                    "catalog_management:category_delete",
                    args=[category.pk]
                ),
                {}
            ),
        ]

        login_url = resolve_url(settings.LOGIN_URL)

        # Attempt each operation without authentication.
        for url, data in attempts:
            with self.subTest(url=url):
                response = self.client.post(url, data=data)

                self.assertRedirects(
                    response,
                    f"{login_url}?next={url}",
                    fetch_redirect_response=False
                )

        # Verify the original category is unchanged.
        category.refresh_from_db()

        self.assertEqual(
            category.name,
            "Protected Category"
        )

        self.assertEqual(
            category.description,
            "Original description"
        )

        # No unauthorized categories were created.
        self.assertEqual(
            Category.objects.count(),
            1
        )