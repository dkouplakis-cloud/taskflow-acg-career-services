from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.conf import settings
from django.shortcuts import resolve_url
from .forms import CategoryForm
from .models import Category, CatalogItem
from core.models import UserProfile
from decimal import Decimal
from io import BytesIO
from tempfile import TemporaryDirectory

from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings


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

class CatalogItemManagementViewTests(TestCase):
    """
    Test Catalogue Item Management operations
    and administrator access permissions.
    """

    def setUp(self):
        """
        Create an administrator in Django's
        isolated test database.
        """

        self.admin_user = get_user_model().objects.create_user(
            username="catalog_item_admin_test",
            password="TestPassword123!"
        )

        profile = self.admin_user.profile
        profile.role = UserProfile.Role.ADMIN
        profile.save()

        self.client.force_login(self.admin_user)

    def test_administrator_can_access_item_directory(self):
        """
        Administrators must be able to access
        the Catalogue Items Directory.
        """

        response = self.client.get(
            reverse("catalog_management:item_list")
        )

        self.assertEqual(
            response.status_code,
            200
        )

        self.assertTemplateUsed(
            response,
            "catalog/management/item_list.html"
        )

        self.assertContains(
            response,
            "Catalogue Directory"
        )

    def test_regular_user_cannot_access_item_directory(self):
        """
        Regular users must not access the
        administrator's Catalogue Items Directory.
        """

        # Create a regular user in the test database.
        regular_user = get_user_model().objects.create_user(
            username="catalog_item_regular_test",
            password="TestPassword123!"
        )

        # Confirm the default role.
        self.assertEqual(
            regular_user.profile.role,
            UserProfile.Role.REGULAR
        )

        # Authenticate as the regular user.
        self.client.force_login(regular_user)

        # Attempt to access the administrator directory.
        response = self.client.get(
            reverse("catalog_management:item_list")
        )

        # Access must be forbidden.
        self.assertEqual(
            response.status_code,
            403
        )

    def test_regular_user_cannot_access_item_creation(self):
        """
        Regular users must not be able to access
        the administrator-only item creation form.
        """

        regular_user = get_user_model().objects.create_user(
            username="catalog_item_create_regular_test",
            password="TestPassword123!"
        )

        self.client.force_login(regular_user)

        response = self.client.get(
            reverse("catalog_management:item_create")
        )

        self.assertEqual(
            response.status_code,
            403
        )


    def test_regular_user_cannot_create_item_via_post(self):
        """
        Regular users must not create catalogue
        items through direct POST requests.
        """

        # Create a regular user.
        regular_user = get_user_model().objects.create_user(
            username="catalog_item_post_regular_test",
            password="TestPassword123!"
        )

        # Create a category in the isolated test database.
        category = Category.objects.create(
            name="Test Workshops",
            slug="test-workshops"
        )

        self.client.force_login(regular_user)

        # Attempt to bypass the creation interface.
        response = self.client.post(
            reverse("catalog_management:item_create"),
            data={
                "name": "Unauthorized Workshop",
                "description": "Unauthorized creation attempt.",
                "category": str(category.pk),
                "price": "0.00",
                "delivery_format": "in_person",
                "duration_minutes": "30",
                "is_active": "on",
                "is_available": "on",
            }
        )

        # The server must reject the request.
        self.assertEqual(response.status_code, 403)

        # No unauthorized item may be created.
        self.assertFalse(
            CatalogItem.objects.filter(
                name="Unauthorized Workshop"
            ).exists()
        )

    def test_regular_user_cannot_edit_item_via_post(self):
        """
        Regular users must not modify existing
        catalogue items through direct POST requests.
        """

        category = Category.objects.create(
            name="Protected Workshops",
            slug="protected-workshops"
        )

        item = CatalogItem.objects.create(
            name="Protected Workshop",
            slug="protected-workshop",
            description="Original description",
            category=category,
            image="catalog/items/test-protected.png",
            price="0.00",
            delivery_format="in_person",
            duration_minutes=90
        )

        regular_user = get_user_model().objects.create_user(
            username="catalog_item_edit_regular_test",
            password="TestPassword123!"
        )

        self.client.force_login(regular_user)

        response = self.client.post(
            reverse(
                "catalog_management:item_edit",
                args=[item.pk]
            ),
            data={
                "name": "Unauthorized Modification",
                "description": "Modified without permission.",
                "category": str(category.pk),
                "price": "0.00",
                "delivery_format": "online",
                "duration_minutes": "30",
            }
        )

        # The request must be rejected.
        self.assertEqual(response.status_code, 403)

        # The original database record must remain unchanged.
        item.refresh_from_db()

        self.assertEqual(item.name, "Protected Workshop")
        self.assertEqual(item.description, "Original description")
        self.assertEqual(item.duration_minutes, 90)

    def test_regular_user_cannot_delete_item_via_post(self):
        """
        Regular users must not delete catalogue
        items through direct POST requests.
        """

        category = Category.objects.create(
            name="Protected Workshops",
            slug="protected-workshops"
        )

        item = CatalogItem.objects.create(
            name="Protected Workshop",
            slug="protected-workshop",
            description="This item must not be deleted.",
            category=category,
            image="catalog/items/test-protected.png",
            price="0.00",
            delivery_format="in_person",
            duration_minutes=90
        )

        regular_user = get_user_model().objects.create_user(
            username="catalog_item_delete_regular_test",
            password="TestPassword123!"
        )

        self.client.force_login(regular_user)

        response = self.client.post(
            reverse(
                "catalog_management:item_delete",
                args=[item.pk]
            )
        )

        # Unauthorized deletion must be rejected.
        self.assertEqual(response.status_code, 403)

        # Verify the original item still exists.
        self.assertTrue(
            CatalogItem.objects.filter(
                pk=item.pk,
                name="Protected Workshop"
            ).exists()
        )

    def test_get_request_does_not_delete_catalog_item(self):
        """
        Opening the deletion confirmation page
        must not remove the catalogue item.
        """

        category = Category.objects.create(
            name="Deletion Safety Workshops",
            slug="deletion-safety-workshops"
        )

        item = CatalogItem.objects.create(
            name="Deletion Safety Test Item",
            slug="deletion-safety-test-item",
            description="Must survive a GET request.",
            category=category,
            image="catalog/items/test-safety.png",
            price="0.00",
            delivery_format="in_person",
            duration_minutes=30
        )

        response = self.client.get(
            reverse(
                "catalog_management:item_delete",
                args=[item.pk]
            )
        )

        # The confirmation page should load.
        self.assertEqual(response.status_code, 200)

        self.assertTemplateUsed(
            response,
            "catalog/management/item_confirm_delete.html"
        )

        # GET must not delete the database record.
        self.assertTrue(
            CatalogItem.objects.filter(pk=item.pk).exists()
        )

    def test_catalog_item_delete_requires_csrf_token(self):
        """
        Deleting a catalogue item through POST
        must require a valid CSRF token.
        """

        # Create a category in the isolated test database.
        category = Category.objects.create(
            name="CSRF Test Workshops",
            slug="csrf-test-workshops"
        )

        # Create a temporary catalogue item.
        item = CatalogItem.objects.create(
            name="CSRF Protected Workshop",
            slug="csrf-protected-workshop",
            description="This item must survive an invalid request.",
            category=category,
            image="catalog/items/csrf-test.png",
            price="0.00",
            delivery_format="in_person",
            duration_minutes=30
        )

        # Enable actual CSRF enforcement.
        csrf_client = Client(
            enforce_csrf_checks=True
        )

        # Authenticate as an administrator.
        csrf_client.force_login(self.admin_user)

        # Submit deletion without a CSRF token.
        response = csrf_client.post(
            reverse(
                "catalog_management:item_delete",
                args=[item.pk]
            )
        )

        # Django must reject the request.
        self.assertEqual(
            response.status_code,
            403
        )

        # The catalogue item must remain intact.
        self.assertTrue(
            CatalogItem.objects.filter(
                pk=item.pk
            ).exists()
        )

    def test_administrator_can_delete_catalog_item(self):
        """
        Administrators can delete catalogue items
        through a confirmed POST request.
        """

        category = Category.objects.create(
            name="Deletion Test Workshops",
            slug="deletion-test-workshops"
        )

        item = CatalogItem.objects.create(
            name="Temporary Deletion Workshop",
            slug="temporary-deletion-workshop",
            description="Temporary test record.",
            category=category,
            image="catalog/items/deletion-test.png",
            price="0.00",
            delivery_format="in_person",
            duration_minutes=30
        )

        # Submit the deletion request as an administrator.
        response = self.client.post(
            reverse(
                "catalog_management:item_delete",
                args=[item.pk]
            )
        )

        # Administrator returns to the directory.
        self.assertRedirects(
            response,
            reverse("catalog_management:item_list")
        )

        # The selected item must no longer exist.
        self.assertFalse(
            CatalogItem.objects.filter(pk=item.pk).exists()
        )

    def test_administrator_can_create_catalog_item(self):
        """
        Verify that an administrator can create
        a catalogue item with a valid uploaded image.
        """

        category = Category.objects.create(
            name="Creation Test Workshops",
            slug="creation-test-workshops"
        )

        # Generate a genuine PNG image in memory.
        image_buffer = BytesIO()

        Image.new(
            "RGB",
            (10, 10),
            color="white"
        ).save(image_buffer, format="PNG")

        uploaded_image = SimpleUploadedFile(
            "test-workshop.png",
            image_buffer.getvalue(),
            content_type="image/png"
        )

        # Keep uploaded test files separate from real media.
        with TemporaryDirectory() as media_directory:
            with override_settings(MEDIA_ROOT=media_directory):

                response = self.client.post(
                    reverse("catalog_management:item_create"),
                    data={
                        "name": "Automated Test Workshop",
                        "description": "Created by an automated test.",
                        "category": str(category.pk),
                        "image": uploaded_image,
                        "price": "0.00",
                        "delivery_format": "in_person",
                        "target_audience": "Students",
                        "duration_minutes": "60",
                        "is_active": "on",
                        "is_available": "on",
                    }
                )

                self.assertRedirects(
                    response,
                    reverse("catalog_management:dashboard")
                )

                item = CatalogItem.objects.get(
                    name="Automated Test Workshop"
                )

                self.assertEqual(item.category, category)
                self.assertEqual(item.duration_minutes, 60)
                self.assertTrue(item.is_active)
                self.assertTrue(item.is_available)
                self.assertTrue(item.image.storage.exists(item.image.name))

    def test_administrator_can_edit_catalog_item(self):
        """
        Administrators can update an existing
        catalogue item without creating a duplicate
        or losing its uploaded image.
        """

        category = Category.objects.create(
            name="Editing Test Workshops",
            slug="editing-test-workshops"
        )

        # Generate a genuine PNG image.
        image_buffer = BytesIO()

        Image.new(
            "RGB",
            (10, 10),
            color="white"
        ).save(image_buffer, format="PNG")

        uploaded_image = SimpleUploadedFile(
            "edit-test.png",
            image_buffer.getvalue(),
            content_type="image/png"
        )

        # Isolate uploaded files from real media.
        with TemporaryDirectory() as media_directory:
            with override_settings(MEDIA_ROOT=media_directory):

                # Create an existing catalogue item.
                item = CatalogItem.objects.create(
                    name="Edit Test Workshop",
                    slug="edit-test-workshop",
                    description="Original description",
                    category=category,
                    image=uploaded_image,
                    price="0.00",
                    delivery_format="in_person",
                    target_audience="Students",
                    duration_minutes=90,
                    is_active=True,
                    is_available=True
                )

                original_id = item.pk
                original_image = item.image.name

                # Submit updated information without
                # uploading a replacement image.
                response = self.client.post(
                    reverse(
                        "catalog_management:item_edit",
                        args=[item.pk]
                    ),
                    data={
                        "name": "Updated Edit Test Workshop",
                        "description": "Updated description",
                        "category": str(category.pk),
                        "price": "12.50",
                        "delivery_format": "online",
                        "target_audience": "ACG students",
                        "duration_minutes": "95",
                        "is_active": "on",
                        "is_available": "on",
                    }
                )

                # Verify the expected redirect.
                self.assertRedirects(
                    response,
                    reverse("catalog_management:item_list")
                )

                # Retrieve the updated database record.
                item.refresh_from_db()

                # Confirm that the existing record changed.
                self.assertEqual(item.pk, original_id)
                self.assertEqual(
                    item.name,
                    "Updated Edit Test Workshop"
                )
                self.assertEqual(
                    item.description,
                    "Updated description"
                )
                self.assertEqual(item.duration_minutes, 95)
                self.assertEqual(item.delivery_format, "online")
                self.assertEqual(str(item.price), "12.50")

                # Existing slug and image are preserved.
                self.assertEqual(
                    item.slug,
                    "edit-test-workshop"
                )
                self.assertEqual(item.image.name, original_image)
                self.assertTrue(
                    item.image.storage.exists(item.image.name)
                )

                # Editing must not create a duplicate.
                self.assertEqual(
                    CatalogItem.objects.count(),
                    1
                )

class PublicCatalogViewTests(TestCase):
    """
    Test the user-facing Career Services Catalogue,
    including filtering, pagination, and visibility.
    """

    def test_pagination_preserves_search_and_category(self):
        """
        Pagination links must preserve both the
        search query and selected category.
        """

        # Create a regular user.
        user = get_user_model().objects.create_user(
            username="public_catalog_test",
            password="TestPassword123!"
        )

        self.client.force_login(user)

        # Create an active category.
        category = Category.objects.create(
            name="Career Workshops",
            slug="career-workshops",
            is_active=True
        )

        # Create ten temporary catalogue items.
        for index in range(10):
            CatalogItem.objects.create(
                name=f"CV Workshop {index}",
                slug=f"cv-workshop-{index}",
                description="CV preparation workshop.",
                category=category,
                image=f"catalog/items/test-{index}.png",
                price="0.00",
                delivery_format="in_person",
                is_active=True,
                is_available=True
            )

        # Request the Catalogue with both filters.
        response = self.client.get(
            reverse("catalog:list"),
            data={
                "q": "CV",
                "category": "career-workshops"
            }
        )

        self.assertEqual(response.status_code, 200)

        # Ten results should require a second page.
        self.assertEqual(
            response.context["total_items"],
            10
        )

        self.assertTrue(
            response.context["page_obj"].has_next()
        )

        # The Next link must retain both filters.
        self.assertContains(
            response,
            "?page=2&amp;q=CV&amp;category=career-workshops"
        )

    def test_second_page_preserves_filters(self):
        """
        The second Catalogue page must display
        the remaining item and preserve filters
        in the Previous pagination link.
        """

        user = get_user_model().objects.create_user(
            username="catalog_second_page_test",
            password="TestPassword123!"
        )

        self.client.force_login(user)

        category = Category.objects.create(
            name="Career Workshops",
            slug="career-workshops",
            is_active=True
        )

        # Create ten matching catalogue items.
        for index in range(10):
            CatalogItem.objects.create(
                name=f"CV Workshop {index}",
                slug=f"cv-workshop-{index}",
                description="CV preparation workshop.",
                category=category,
                image=f"catalog/items/page-test-{index}.png",
                price="0.00",
                delivery_format="in_person",
                is_active=True,
                is_available=True
            )

        # Request the second page with both filters.
        response = self.client.get(
            reverse("catalog:list"),
            data={
                "page": "2",
                "q": "CV",
                "category": "career-workshops"
            }
        )

        self.assertEqual(response.status_code, 200)

        page_obj = response.context["page_obj"]

        self.assertEqual(page_obj.number, 2)
        self.assertEqual(len(page_obj.object_list), 1)

        # The tenth item must appear.
        self.assertContains(response, "CV Workshop 9")

        # Previous must preserve search and category.
        self.assertContains(
            response,
            "?page=1&amp;q=CV&amp;category=career-workshops"
        )

    def test_catalogue_excludes_inactive_and_unavailable_items(self):
        """
        The public Catalogue must display only
        active and available items belonging
        to active categories.
        """

        user = get_user_model().objects.create_user(
            username="catalog_visibility_test",
            password="TestPassword123!"
        )

        self.client.force_login(user)

        active_category = Category.objects.create(
            name="Active Workshops",
            slug="active-workshops",
            is_active=True
        )

        inactive_category = Category.objects.create(
            name="Hidden Workshops",
            slug="hidden-workshops",
            is_active=False
        )

        # An item that should be visible.
        CatalogItem.objects.create(
            name="Visible Career Workshop",
            slug="visible-career-workshop",
            category=active_category,
            image="catalog/items/visible-test.png",
            is_active=True,
            is_available=True
        )

        # An inactive item.
        CatalogItem.objects.create(
            name="Inactive Career Workshop",
            slug="inactive-career-workshop",
            category=active_category,
            image="catalog/items/inactive-test.png",
            is_active=False,
            is_available=True
        )

        # An unavailable item.
        CatalogItem.objects.create(
            name="Unavailable Career Workshop",
            slug="unavailable-career-workshop",
            category=active_category,
            image="catalog/items/unavailable-test.png",
            is_active=True,
            is_available=False
        )

        # An item belonging to an inactive category.
        CatalogItem.objects.create(
            name="Hidden Category Workshop",
            slug="hidden-category-workshop",
            category=inactive_category,
            image="catalog/items/hidden-category-test.png",
            is_active=True,
            is_available=True
        )

        response = self.client.get(
            reverse("catalog:list")
        )

        self.assertEqual(response.status_code, 200)

        # Only one item should be visible.
        self.assertEqual(
            response.context["total_items"],
            1
        )

        self.assertContains(
            response,
            "Visible Career Workshop"
        )

        self.assertNotContains(
            response,
            "Inactive Career Workshop"
        )

        self.assertNotContains(
            response,
            "Unavailable Career Workshop"
        )

        self.assertNotContains(
            response,
            "Hidden Category Workshop"
        )

    def test_catalogue_search_matches_name_and_description(self):
        """
        Search must match service names and descriptions,
        regardless of capitalization.
        """

        user = get_user_model().objects.create_user(
            username="catalog_search_test",
            password="TestPassword123!"
        )

        self.client.force_login(user)

        category = Category.objects.create(
            name="Career Workshops",
            slug="career-workshops",
            is_active=True
        )

        # Matches by name.
        CatalogItem.objects.create(
            name="CV Coaching Session",
            slug="cv-coaching-session",
            description="Individual career coaching.",
            category=category,
            image="catalog/items/cv-coaching-test.png",
            is_active=True,
            is_available=True
        )

        # Matches by description.
        CatalogItem.objects.create(
            name="Career Preparation Clinic",
            slug="career-preparation-clinic",
            description="Improve your CV before applying.",
            category=category,
            image="catalog/items/career-clinic-test.png",
            is_active=True,
            is_available=True
        )

        # Should not match.
        CatalogItem.objects.create(
            name="Networking Event",
            slug="networking-event",
            description="Meet employers and graduates.",
            category=category,
            image="catalog/items/networking-test.png",
            is_active=True,
            is_available=True
        )

        response = self.client.get(
            reverse("catalog:list"),
            data={"q": "  cv  "}
        )

        self.assertEqual(response.status_code, 200)

        # Search input should be trimmed.
        self.assertEqual(
            response.context["search_query"],
            "cv"
        )

        # Both matching services should be returned.
        self.assertEqual(
            response.context["total_items"],
            2
        )

        result_names = {
            item.name
            for item in response.context["items"]
        }

        self.assertEqual(
            result_names,
            {
                "CV Coaching Session",
                "Career Preparation Clinic"
            }
        )

    def test_catalogue_filters_by_category_and_search(self):
        """
        Category filtering must return only items in
        the selected category and work alongside search.
        """

        user = get_user_model().objects.create_user(
            username="catalog_category_test",
            password="TestPassword123!"
        )

        self.client.force_login(user)

        workshops = Category.objects.create(
            name="Career Workshops",
            slug="career-workshops",
            is_active=True
        )

        events = Category.objects.create(
            name="Career Events",
            slug="career-events",
            is_active=True
        )

        CatalogItem.objects.create(
            name="CV Writing Workshop",
            slug="cv-writing-workshop",
            description="Learn to prepare a professional CV.",
            category=workshops,
            is_active=True,
            is_available=True
        )

        CatalogItem.objects.create(
            name="Interview Preparation Workshop",
            slug="interview-preparation-workshop",
            description="Develop your interview skills.",
            category=workshops,
            is_active=True,
            is_available=True
        )

        CatalogItem.objects.create(
            name="CV Networking Event",
            slug="cv-networking-event",
            description="Meet career professionals.",
            category=events,
            is_active=True,
            is_available=True
        )

        # Test 1: Category filtering without search.
        response = self.client.get(
            reverse("catalog:list"),
            data={"category": "career-workshops"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_items"], 2)

        category_results = {
            item.name for item in response.context["items"]
        }

        self.assertEqual(
            category_results,
            {
                "CV Writing Workshop",
                "Interview Preparation Workshop"
            }
        )

        # Test 2: Category filtering combined with search.
        response = self.client.get(
            reverse("catalog:list"),
            data={
                "q": "CV",
                "category": "career-workshops"
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_items"], 1)

        self.assertEqual(
            response.context["search_query"],
            "CV"
        )

        self.assertEqual(
            response.context["selected_category"],
            "career-workshops"
        )

        combined_results = [
            item.name for item in response.context["items"]
        ]

        self.assertEqual(
            combined_results,
            ["CV Writing Workshop"]
        )

    def test_catalogue_item_detail_page_and_link(self):
        """
        Available catalogue items must have a working
        detail page linked from the public Catalogue.
        """

        user = get_user_model().objects.create_user(
            username="catalog_detail_test",
            password="TestPassword123!"
        )

        self.client.force_login(user)

        category = Category.objects.create(
            name="Career Workshops",
            slug="career-workshops",
            is_active=True
        )

        item = CatalogItem.objects.create(
            name="CV Writing Workshop",
            slug="cv-writing-workshop",
            description="Learn how to create a professional CV.",
            category=category,
            image="catalog/items/test-detail.png",
            duration_minutes=90,
            delivery_format="in_person",
            is_active=True,
            is_available=True
        )

        detail_url = reverse(
            "catalog:detail",
            kwargs={"slug": item.slug}
        )

        # The Catalogue must link to the detail page.
        catalogue_response = self.client.get(
            reverse("catalog:list")
        )

        self.assertEqual(
            catalogue_response.status_code,
            200
        )

        self.assertContains(
            catalogue_response,
            f'href="{detail_url}"'
        )

        # The detail page must load successfully.
        detail_response = self.client.get(detail_url)

        self.assertEqual(
            detail_response.status_code,
            200
        )

        self.assertEqual(
            detail_response.context["item"],
            item
        )

        self.assertContains(
            detail_response,
            "CV Writing Workshop"
        )

        self.assertContains(
            detail_response,
            "Career Workshops"
        )

        self.assertContains(
            detail_response,
            "90 minutes"
        )

        self.assertContains(
            detail_response,
            "In Person"
        )

    def test_catalogue_detail_rejects_hidden_and_missing_items(self):
        """
        Restricted and nonexistent catalogue items
        must not be accessible through detail URLs.
        """

        user = get_user_model().objects.create_user(
            username="catalog_detail_security_test",
            password="TestPassword123!"
        )

        self.client.force_login(user)

        active_category = Category.objects.create(
            name="Active Workshops",
            slug="active-workshops",
            is_active=True
        )

        inactive_category = Category.objects.create(
            name="Hidden Workshops",
            slug="hidden-workshops",
            is_active=False
        )

        # Inactive service.
        CatalogItem.objects.create(
            name="Inactive Workshop",
            slug="inactive-workshop",
            description="This service is inactive.",
            category=active_category,
            image="catalog/items/inactive-detail.png",
            is_active=False,
            is_available=True
        )

        # Unavailable service.
        CatalogItem.objects.create(
            name="Unavailable Workshop",
            slug="unavailable-workshop",
            description="This service is unavailable.",
            category=active_category,
            image="catalog/items/unavailable-detail.png",
            is_active=True,
            is_available=False
        )

        # Service belonging to an inactive category.
        CatalogItem.objects.create(
            name="Hidden Category Workshop",
            slug="hidden-category-workshop",
            description="This category is inactive.",
            category=inactive_category,
            image="catalog/items/hidden-detail.png",
            is_active=True,
            is_available=True
        )

        restricted_slugs = [
            "inactive-workshop",
            "unavailable-workshop",
            "hidden-category-workshop",
            "nonexistent-workshop"
        ]

        # Every restricted URL must return HTTP 404.
        for slug in restricted_slugs:
            with self.subTest(slug=slug):
                response = self.client.get(
                    reverse(
                        "catalog:detail",
                        kwargs={"slug": slug}
                    )
                )

                self.assertEqual(
                    response.status_code,
                    404
                )

    def test_add_to_cart_and_display_cart(self):
        """
        Adding a service must update the session and
        display the correct quantity and total.
        """

        user = get_user_model().objects.create_user(
            username="cart_integration_test",
            password="TestPassword123!"
        )

        self.client.force_login(user)

        category = Category.objects.create(
            name="Career Workshops",
            slug="career-workshops",
            is_active=True
        )

        item = CatalogItem.objects.create(
            name="Professional CV Workshop",
            slug="professional-cv-workshop",
            description="Develop professional CV skills.",
            category=category,
            image="catalog/items/test-cart.png",
            price="12.50",
            is_active=True,
            is_available=True
        )

        # Add the service using an HTTP POST request.
        response = self.client.post(
            reverse(
                "catalog:add_to_cart",
                kwargs={"slug": item.slug}
            )
        )

        self.assertEqual(response.status_code, 302)

        # Verify the service is stored in the session.
        cart = self.client.session.get("catalog_cart")

        self.assertEqual(
            cart,
            {str(item.pk): 1}
        )

        # Open the shopping-cart page.
        response = self.client.get(
            reverse("catalog:cart")
        )

        self.assertEqual(response.status_code, 200)

        # Verify the selected service is displayed.
        self.assertContains(
            response,
            "Professional CV Workshop"
        )

        # Verify quantity and calculated total.
        self.assertEqual(
            response.context["total_quantity"],
            1
        )

        self.assertEqual(
            response.context["total_amount"],
            Decimal("12.50")
        )

    def test_add_to_cart_rejects_get_requests(self):
        """
        A GET request must not modify
        the authenticated user's shopping cart.
        """

        user = get_user_model().objects.create_user(
            username="cart_get_test",
            password="TestPassword123!"
        )

        self.client.force_login(user)

        category = Category.objects.create(
            name="Career Workshops",
            slug="career-workshops",
            is_active=True
        )

        item = CatalogItem.objects.create(
            name="CV Preparation Workshop",
            slug="cv-preparation-workshop",
            description="Learn professional CV writing.",
            category=category,
            image="catalog/items/test-get.png",
            is_active=True,
            is_available=True
        )

        url = reverse(
            "catalog:add_to_cart",
            kwargs={"slug": item.slug}
        )

        # GET must be rejected.
        response = self.client.get(url)

        self.assertEqual(response.status_code, 405)

        # The session cart must remain empty.
        self.assertEqual(
            self.client.session.get("catalog_cart", {}),
            {}
        )

    def test_update_cart_quantity_recalculates_total(self):
        """
        Updating a cart item's quantity must persist
        in the session and recalculate the cart total.
        """

        user = get_user_model().objects.create_user(
            username="cart_quantity_test",
            password="TestPassword123!"
        )

        self.client.force_login(user)

        category = Category.objects.create(
            name="Career Workshops",
            slug="career-workshops",
            is_active=True
        )

        item = CatalogItem.objects.create(
            name="Professional CV Workshop",
            slug="quantity-test-workshop",
            description="Professional CV preparation.",
            category=category,
            image="catalog/items/quantity-test.png",
            price="12.50",
            is_active=True,
            is_available=True
        )

        # Add the workshop to the cart.
        self.client.post(
            reverse(
                "catalog:add_to_cart",
                kwargs={"slug": item.slug}
            )
        )

        # Update the quantity from 1 to 2.
        response = self.client.post(
            reverse(
                "catalog:update_cart_quantity",
                kwargs={"slug": item.slug}
            ),
            data={"quantity": "2"}
        )

        self.assertEqual(response.status_code, 302)

        # The session must contain quantity 2.
        self.assertEqual(
            self.client.session["catalog_cart"],
            {str(item.pk): 2}
        )

        # The cart must reflect the new quantity.
        response = self.client.get(
            reverse("catalog:cart")
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.context["total_quantity"],
            2
        )

        # Two services costing €12.50 each = €25.00.
        self.assertEqual(
            response.context["total_amount"],
            Decimal("25.00")
        )

    def test_update_cart_quantity_rejects_invalid_values(self):
        """
        Invalid quantities must be rejected without
        modifying the existing shopping cart.
        """

        user = get_user_model().objects.create_user(
            username="cart_invalid_quantity_test",
            password="TestPassword123!"
        )

        self.client.force_login(user)

        category = Category.objects.create(
            name="Career Workshops",
            slug="career-workshops",
            is_active=True
        )

        item = CatalogItem.objects.create(
            name="CV Skills Workshop",
            slug="invalid-quantity-workshop",
            description="Develop professional CV skills.",
            category=category,
            image="catalog/items/invalid-quantity-test.png",
            is_active=True,
            is_available=True
        )

        # Add one service to the shopping cart.
        self.client.post(
            reverse(
                "catalog:add_to_cart",
                kwargs={"slug": item.slug}
            )
        )

        update_url = reverse(
            "catalog:update_cart_quantity",
            kwargs={"slug": item.slug}
        )

        invalid_quantities = [
            "0",
            "-1",
            "11",
            "100",
            "abc",
            "1.5",
            "01",
            ""
        ]

        for invalid_quantity in invalid_quantities:

            with self.subTest(quantity=invalid_quantity):

                response = self.client.post(
                    update_url,
                    data={"quantity": invalid_quantity}
                )

                # Invalid requests redirect to My Cart.
                self.assertRedirects(
                    response,
                    reverse("catalog:cart")
                )

                # The original quantity must remain 1.
                self.assertEqual(
                    self.client.session["catalog_cart"],
                    {str(item.pk): 1}
                )

    def test_remove_from_cart_clears_item_and_shows_empty_state(self):
        """
        Removing an item must delete it from the session
        and display the empty-cart state.
        """

        user = get_user_model().objects.create_user(
            username="cart_removal_test",
            password="TestPassword123!"
        )

        self.client.force_login(user)

        category = Category.objects.create(
            name="Career Workshops",
            slug="career-workshops",
            is_active=True
        )

        item = CatalogItem.objects.create(
            name="CV Writing Workshop",
            slug="cv-removal-test",
            description="Professional CV preparation.",
            category=category,
            image="catalog/items/removal-test.png",
            is_active=True,
            is_available=True
        )

        # Add the workshop to the cart.
        self.client.post(
            reverse(
                "catalog:add_to_cart",
                kwargs={"slug": item.slug}
            )
        )

        # Set the quantity to 2.
        self.client.post(
            reverse(
                "catalog:update_cart_quantity",
                kwargs={"slug": item.slug}
            ),
            data={"quantity": "2"}
        )

        self.assertEqual(
            self.client.session["catalog_cart"],
            {str(item.pk): 2}
        )

        # Remove the workshop.
        response = self.client.post(
            reverse(
                "catalog:remove_from_cart",
                kwargs={"slug": item.slug}
            )
        )

        self.assertRedirects(
            response,
            reverse("catalog:cart")
        )

        # The session cart must now be empty.
        self.assertEqual(
            self.client.session["catalog_cart"],
            {}
        )

        # Verify the empty-cart page.
        response = self.client.get(
            reverse("catalog:cart")
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.context["total_quantity"],
            0
        )

        self.assertEqual(
            response.context["cart_lines"],
            []
        )

        self.assertContains(
            response,
            "Your cart is empty"
        )

    def test_repeated_cart_removal_is_safe(self):
        """
        Removing an item twice must not cause errors
        or modify other shopping-cart data.
        """

        user = get_user_model().objects.create_user(
            username="cart_repeated_removal_test",
            password="TestPassword123!"
        )

        self.client.force_login(user)

        category = Category.objects.create(
            name="Career Workshops",
            slug="career-workshops",
            is_active=True
        )

        item = CatalogItem.objects.create(
            name="CV Preparation Workshop",
            slug="repeated-removal-test",
            description="Professional CV preparation.",
            category=category,
            image="catalog/items/repeated-removal.png",
            is_active=True,
            is_available=True
        )

        # Add the service to the cart.
        self.client.post(
            reverse(
                "catalog:add_to_cart",
                kwargs={"slug": item.slug}
            )
        )

        remove_url = reverse(
            "catalog:remove_from_cart",
            kwargs={"slug": item.slug}
        )

        # First removal should empty the cart.
        first_response = self.client.post(remove_url)

        self.assertRedirects(
            first_response,
            reverse("catalog:cart")
        )

        self.assertEqual(
            self.client.session["catalog_cart"],
            {}
        )

        # Attempt to remove the same item again.
        second_response = self.client.post(remove_url)

        self.assertRedirects(
            second_response,
            reverse("catalog:cart")
        )

        # The cart must remain empty.
        self.assertEqual(
            self.client.session["catalog_cart"],
            {}
        )

    def test_remove_from_cart_rejects_get_requests(self):
        """
        GET requests must not remove items
        from the authenticated user's cart.
        """

        user = get_user_model().objects.create_user(
            username="cart_removal_get_test",
            password="TestPassword123!"
        )

        self.client.force_login(user)

        category = Category.objects.create(
            name="Career Workshops",
            slug="career-workshops",
            is_active=True
        )

        item = CatalogItem.objects.create(
            name="CV Writing Workshop",
            slug="removal-get-test",
            description="Professional CV preparation.",
            category=category,
            image="catalog/items/removal-get-test.png",
            is_active=True,
            is_available=True
        )

        # Add the service to the cart.
        self.client.post(
            reverse(
                "catalog:add_to_cart",
                kwargs={"slug": item.slug}
            )
        )

        # Verify the cart initially contains the item.
        expected_cart = {str(item.pk): 1}

        self.assertEqual(
            self.client.session["catalog_cart"],
            expected_cart
        )

        remove_url = reverse(
            "catalog:remove_from_cart",
            kwargs={"slug": item.slug}
        )

        # A GET request must be rejected.
        response = self.client.get(remove_url)

        self.assertEqual(
            response.status_code,
            405
        )

        # The service must remain in the cart.
        self.assertEqual(
            self.client.session["catalog_cart"],
            expected_cart
        )

class CheckoutServiceTests(TestCase):
    """
    Test simulated order creation and checkout
    business logic.
    """

    def test_checkout_creates_order_with_correct_totals(self):
        """
        Checkout must create an order with the correct
        user, items, quantities, prices, and total.
        """

        from decimal import Decimal

        from .checkout_service import create_order_from_cart
        from .models import Order, OrderItem

        # Create a test user.
        user = get_user_model().objects.create_user(
            username="checkout_test_user",
            password="TestPassword123!"
        )

        # Create an active category.
        category = Category.objects.create(
            name="Career Workshops",
            slug="career-workshops",
            is_active=True
        )

        # First catalogue service.
        workshop = CatalogItem.objects.create(
            name="CV Writing Workshop",
            slug="checkout-cv-workshop",
            description="Professional CV preparation.",
            category=category,
            image="catalog/items/checkout-cv.png",
            price=Decimal("12.50"),
            is_active=True,
            is_available=True
        )

        # Second catalogue service.
        seminar = CatalogItem.objects.create(
            name="Career Development Seminar",
            slug="checkout-career-seminar",
            description="Career development guidance.",
            category=category,
            image="catalog/items/checkout-seminar.png",
            price=Decimal("5.25"),
            is_active=True,
            is_available=True
        )

        # Simulate a cart containing three units.
        cart = {
            str(workshop.pk): 2,
            str(seminar.pk): 1
        }

        # Create the simulated order.
        order = create_order_from_cart(user, cart)

        # Verify that exactly one order was created.
        self.assertEqual(Order.objects.count(), 1)

        self.assertEqual(order.user, user)

        self.assertEqual(
            order.status,
            Order.OrderStatus.PLACED
        )

        # 2 × €12.50 + 1 × €5.25 = €30.25
        self.assertEqual(
            order.total_amount,
            Decimal("30.25")
        )

        # Verify both order items were saved.
        self.assertEqual(
            OrderItem.objects.filter(order=order).count(),
            2
        )

        order_lines = {
            line.catalog_item_id: line
            for line in order.items.all()
        }

        # Verify the first item's historical snapshot.
        cv_line = order_lines[workshop.pk]

        self.assertEqual(
            cv_line.item_name,
            "CV Writing Workshop"
        )

        self.assertEqual(cv_line.quantity, 2)

        self.assertEqual(
            cv_line.unit_price,
            Decimal("12.50")
        )

        self.assertEqual(
            cv_line.subtotal,
            Decimal("25.00")
        )

        # Verify the second item.
        seminar_line = order_lines[seminar.pk]

        self.assertEqual(seminar_line.quantity, 1)

        self.assertEqual(
            seminar_line.unit_price,
            Decimal("5.25")
        )

        self.assertEqual(
            seminar_line.subtotal,
            Decimal("5.25")
        )

    def test_checkout_rejects_empty_cart(self):
        """
        Checkout must reject an empty cart without
        creating any order or order-item records.
        """

        from .checkout_service import (
            CheckoutError,
            create_order_from_cart,
        )
        from .models import Order, OrderItem

        user = get_user_model().objects.create_user(
            username="checkout_empty_cart_test",
            password="TestPassword123!"
        )

        # Attempt checkout with an empty cart.
        with self.assertRaises(CheckoutError) as context:
            create_order_from_cart(user, {})

        # Verify the expected error message.
        self.assertEqual(
            str(context.exception),
            "Your cart is empty."
        )

        # No orders or order items must be created.
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(OrderItem.objects.count(), 0)

    def test_checkout_rejects_unavailable_service(self):
        """
        Checkout must reject the entire cart if
        any selected service becomes unavailable.
        """

        from .checkout_service import (
            CheckoutError,
            create_order_from_cart,
        )
        from .models import Order, OrderItem

        user = get_user_model().objects.create_user(
            username="checkout_unavailable_test",
            password="TestPassword123!"
        )

        category = Category.objects.create(
            name="Career Workshops",
            slug="career-workshops",
            is_active=True
        )

        # First workshop remains available.
        available_item = CatalogItem.objects.create(
            name="CV Writing Workshop",
            slug="checkout-available-cv",
            description="Professional CV preparation.",
            category=category,
            image="catalog/items/available-test.png",
            price=Decimal("10.00"),
            is_active=True,
            is_available=True
        )

        # Second workshop has become unavailable.
        unavailable_item = CatalogItem.objects.create(
            name="Interview Preparation Workshop",
            slug="checkout-unavailable-interview",
            description="Improve interview skills.",
            category=category,
            image="catalog/items/unavailable-test.png",
            price=Decimal("15.00"),
            is_active=True,
            is_available=False
        )

        cart = {
            str(available_item.pk): 1,
            str(unavailable_item.pk): 1
        }

        # Checkout must reject the entire cart.
        with self.assertRaises(CheckoutError) as context:
            create_order_from_cart(user, cart)

        self.assertIn(
            "no longer available",
            str(context.exception)
        )

        # Neither service should be ordered.
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(OrderItem.objects.count(), 0)

    def test_checkout_rolls_back_on_order_item_failure(self):
        """
        If saving order items fails, the entire
        checkout transaction must be rolled back.
        """

        from decimal import Decimal
        from unittest.mock import patch

        from .checkout_service import create_order_from_cart
        from .models import Order, OrderItem

        user = get_user_model().objects.create_user(
            username="checkout_rollback_test",
            password="TestPassword123!"
        )

        category = Category.objects.create(
            name="Career Workshops",
            slug="career-workshops",
            is_active=True
        )

        item = CatalogItem.objects.create(
            name="CV Writing Workshop",
            slug="checkout-rollback-workshop",
            description="Professional CV preparation.",
            category=category,
            image="catalog/items/rollback-test.png",
            price=Decimal("12.50"),
            is_active=True,
            is_available=True
        )

        cart = {
            str(item.pk): 1
        }

        # Simulate a failure when saving order items.
        with patch(
            "catalog.checkout_service.OrderItem.objects.bulk_create",
            side_effect=RuntimeError(
                "Simulated order-item failure"
            )
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "Simulated order-item failure"
            ):
                create_order_from_cart(user, cart)

        # The order created before the failure
        # must have been rolled back.
        self.assertEqual(
            Order.objects.count(),
            0
        )

        # No order items should remain.
        self.assertEqual(
            OrderItem.objects.count(),
            0
        )

class CheckoutViewTests(TestCase):
    """
    Test the simulated checkout HTTP workflow,
    including session handling and redirects.
    """

    def test_successful_checkout_clears_cart(self):
        """
        Successful checkout must create an order,
        clear the session cart, and redirect to
        the correct confirmation page.
        """

        from decimal import Decimal

        from .models import Order, OrderItem

        user = get_user_model().objects.create_user(
            username="checkout_view_test",
            password="TestPassword123!"
        )

        self.client.force_login(user)

        category = Category.objects.create(
            name="Career Workshops",
            slug="career-workshops",
            is_active=True
        )

        item = CatalogItem.objects.create(
            name="CV Writing Workshop",
            slug="checkout-view-workshop",
            description="Professional CV preparation.",
            category=category,
            image="catalog/items/checkout-view-test.png",
            price=Decimal("12.50"),
            is_active=True,
            is_available=True
        )

        # Add the service through the actual endpoint.
        add_response = self.client.post(
            reverse(
                "catalog:add_to_cart",
                kwargs={"slug": item.slug}
            )
        )

        self.assertEqual(add_response.status_code, 302)

        # Verify that the cart contains one item.
        self.assertEqual(
            self.client.session["catalog_cart"],
            {str(item.pk): 1}
        )

        # Submit the simulated checkout.
        response = self.client.post(
            reverse("catalog:place_order")
        )

        self.assertEqual(response.status_code, 302)

        # Exactly one order must be created.
        self.assertEqual(Order.objects.count(), 1)

        order = Order.objects.get()

        self.assertEqual(order.user, user)

        self.assertEqual(
            order.total_amount,
            Decimal("12.50")
        )

        self.assertEqual(
            order.status,
            Order.OrderStatus.PLACED
        )

        # Verify the historical order item.
        self.assertEqual(
            OrderItem.objects.filter(order=order).count(),
            1
        )

        order_item = order.items.get()

        self.assertEqual(
            order_item.item_name,
            "CV Writing Workshop"
        )

        self.assertEqual(order_item.quantity, 1)

        self.assertEqual(
            order_item.unit_price,
            Decimal("12.50")
        )

        # The cart must be cleared after checkout.
        self.assertEqual(
            self.client.session.get("catalog_cart", {}),
            {}
        )

        # The user must reach the correct confirmation.
        confirmation_url = reverse(
            "catalog:order_confirmation",
            kwargs={"order_id": order.pk}
        )

        self.assertRedirects(
            response,
            confirmation_url
        )

    def test_order_confirmation_enforces_ownership(self):
        """
        Users may view their own orders, but
        another user's order must return HTTP 404.
        """

        from decimal import Decimal

        from .models import Order

        # Create two separate users.
        owner = get_user_model().objects.create_user(
            username="order_owner_test",
            password="TestPassword123!"
        )

        other_user = get_user_model().objects.create_user(
            username="other_order_user_test",
            password="TestPassword123!"
        )

        # Create an order belonging to the first user.
        order = Order.objects.create(
            user=owner,
            total_amount=Decimal("12.50"),
            status=Order.OrderStatus.PLACED
        )

        confirmation_url = reverse(
            "catalog:order_confirmation",
            kwargs={"order_id": order.pk}
        )

        # The owner must be able to view their order.
        self.client.force_login(owner)

        response = self.client.get(confirmation_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["order"], order)

        # Another authenticated user must be denied.
        self.client.force_login(other_user)

        response = self.client.get(confirmation_url)

        self.assertEqual(response.status_code, 404)

        # Nonexistent orders must also return HTTP 404.
        nonexistent_url = reverse(
            "catalog:order_confirmation",
            kwargs={"order_id": order.pk + 1000}
        )

        response = self.client.get(nonexistent_url)

        self.assertEqual(response.status_code, 404)

    def test_failed_checkout_preserves_cart(self):
        """
        If a selected service becomes unavailable,
        checkout must fail without clearing the cart
        or creating an order.
        """

        from .models import Order, OrderItem

        user = get_user_model().objects.create_user(
            username="checkout_failure_test",
            password="TestPassword123!"
        )

        self.client.force_login(user)

        category = Category.objects.create(
            name="Career Workshops",
            slug="career-workshops",
            is_active=True
        )

        item = CatalogItem.objects.create(
            name="CV Writing Workshop",
            slug="checkout-failure-workshop",
            description="Professional CV preparation.",
            category=category,
            image="catalog/items/checkout-failure.png",
            price=Decimal("12.50"),
            is_active=True,
            is_available=True
        )

        # Add the available service to the cart.
        response = self.client.post(
            reverse(
                "catalog:add_to_cart",
                kwargs={"slug": item.slug}
            )
        )

        self.assertEqual(response.status_code, 302)

        expected_cart = {str(item.pk): 1}

        self.assertEqual(
            self.client.session["catalog_cart"],
            expected_cart
        )

        # Simulate an administrator disabling the service.
        item.is_available = False
        item.save(update_fields=["is_available"])

        # Attempt checkout.
        response = self.client.post(
            reverse("catalog:place_order")
        )

        # Checkout should redirect to My Cart.
        self.assertRedirects(
            response,
            reverse("catalog:cart")
        )

        # The cart must not be cleared.
        self.assertEqual(
            self.client.session["catalog_cart"],
            expected_cart
        )

        # No partial orders should exist.
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(OrderItem.objects.count(), 0)

    def test_deleted_service_can_be_removed_from_cart(self):
        """
        A deleted catalogue service must remain visible
        and removable without affecting other cart items.
        """

        from django.contrib.auth import get_user_model
        from django.urls import reverse

        user = get_user_model().objects.create_user(
            username="deleted_cart_item_test",
            password="TestPassword123!"
        )

        self.client.force_login(user)

        # Simulate two services that were deleted
        # after being added to the shopping cart.
        session = self.client.session
        session["catalog_cart"] = {
            "999999991": 2,
            "999999992": 1,
        }
        session.save()

        cart_url = reverse("catalog:cart")

        # Both missing services must remain visible.
        response = self.client.get(cart_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Deleted Service #999999991"
        )
        self.assertContains(
            response,
            "Deleted Service #999999992"
        )

        # Checkout must be blocked.
        self.assertContains(
            response,
            "Checkout Unavailable"
        )

        # Remove only the first deleted service.
        removal_url = reverse(
            "catalog:remove_missing_cart_item",
            kwargs={"item_id": 999999991}
        )

        response = self.client.post(
            removal_url,
            follow=True
        )

        self.assertEqual(response.status_code, 200)

        # The other selection must be preserved.
        self.assertEqual(
            self.client.session["catalog_cart"],
            {"999999992": 1}
        )

        # The removed service must disappear.
        self.assertNotContains(
            response,
            "Deleted Service #999999991"
        )

        # The remaining service must still be visible.
        self.assertContains(
            response,
            "Deleted Service #999999992"
        )

    def test_checkout_rejects_get_requests(self):
        """
        Checkout must not create orders through GET requests.
        """

        from .models import Order, OrderItem

        user = get_user_model().objects.create_user(
            username="checkout_get_test",
            password="TestPassword123!"
        )

        self.client.force_login(user)

        checkout_url = reverse("catalog:place_order")

        # Attempt to place an order using HTTP GET.
        response = self.client.get(checkout_url)

        # Checkout must accept POST requests only.
        self.assertEqual(response.status_code, 405)

        # No order records should be created.
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(OrderItem.objects.count(), 0)

    def test_order_history_requires_authentication(self):
        """
        Anonymous visitors must be redirected to sign in
        before accessing their order history.
        """

        # Request order history without authenticating.
        response = self.client.get(
            reverse("catalog:order_history")
        )

        # Django must redirect anonymous visitors.
        self.assertEqual(response.status_code, 302)

        # Preserve the requested destination after login.
        self.assertIn(
            "next=",
            response["Location"]
        )
    
    def test_order_history_only_displays_own_orders(self):
        """
        Authenticated students must see only their own
        orders, never another student's order history.
        """
        from .models import Order

        User = get_user_model()

        # Create two independent student accounts.
        student_a = User.objects.create_user(
            username="order_history_student_a"
        )

        student_b = User.objects.create_user(
            username="order_history_student_b"
        )

        # Create one simulated order for each student.
        own_order = Order.objects.create(
            user=student_a
        )

        other_order = Order.objects.create(
            user=student_b
        )

        # Authenticate as the first student.
        self.client.force_login(student_a)

        response = self.client.get(
            reverse("catalog:order_history")
        )

        self.assertEqual(response.status_code, 200)

        # Verify ownership filtering in the queryset.
        visible_orders = list(response.context["orders"])

        self.assertIn(own_order, visible_orders)
        self.assertNotIn(other_order, visible_orders)
        self.assertEqual(len(visible_orders), 1)

        # Verify that the HTML does not expose another order.
        self.assertContains(
            response,
            f"Order #{own_order.pk}"
        )

        self.assertNotContains(
            response,
            f"Order #{other_order.pk}"
        )
    
    def test_order_history_displays_empty_state(self):
        """
        A student without previous orders should see
        a helpful empty state and catalogue navigation.
        """
        user = get_user_model().objects.create_user(
            username="empty_order_history_student"
        )

        self.client.force_login(user)

        response = self.client.get(
            reverse("catalog:order_history")
        )

        # The page must load successfully.
        self.assertEqual(response.status_code, 200)

        # The correct template must be rendered.
        self.assertTemplateUsed(
            response,
            "catalog/order_history.html"
        )

        # No orders should appear in the queryset.
        self.assertEqual(
            list(response.context["orders"]),
            []
        )

        # Verify the empty-state content.
        self.assertContains(response, "No orders yet")
        self.assertContains(
            response,
            "Explore Career Services"
        )

        # Verify navigation back to the catalogue.
        self.assertContains(
            response,
            reverse("catalog:list")
        )

class AnonymousCatalogAccessTests(TestCase):
    """
    Verify public catalogue access while preserving
    authentication requirements for protected areas.
    """

    @classmethod
    def setUpTestData(cls):
        # Create an available service for anonymous access tests.
        category = Category.objects.create(
            name="Career Workshops",
            slug="career-workshops",
            is_active=True
        )

        cls.item = CatalogItem.objects.create(
            name="Career Preparation Workshop",
            slug="career-preparation-workshop",
            description="Professional interview preparation.",
            category=category,
            image="catalog/items/test-workshop.png",
            price=Decimal("0.00"),
            delivery_format="in_person",
            is_active=True,
            is_available=True
        )

    def test_anonymous_user_can_browse_catalogue(self):
        # Public browsing must not require authentication.
        response = self.client.get(
            reverse("catalog:list")
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.item.name)

    def test_anonymous_user_can_view_item_details(self):
        # Available service details must remain publicly accessible.
        response = self.client.get(
            reverse(
                "catalog:detail",
                kwargs={"slug": self.item.slug}
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.item.name)

    def test_anonymous_user_can_search_catalogue(self):
        # Anonymous visitors must be able to search services.
        response = self.client.get(
            reverse("catalog:list"),
            data={"q": "Career"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.item.name)
        self.assertEqual(response.context["total_items"], 1)

    def test_anonymous_user_cannot_access_cart(self):
        # Shopping cart access must still require authentication.
        url = reverse("catalog:cart")

        response = self.client.get(url)

        self.assertRedirects(
            response,
            f"{resolve_url(settings.LOGIN_URL)}?next={url}"
        )

    def test_anonymous_user_cannot_access_workspace(self):
        # Confidential projects must not be publicly accessible.
        url = reverse("projects:project_list")

        response = self.client.get(url)

        self.assertRedirects(
            response,
            f"{resolve_url(settings.LOGIN_URL)}?next={url}"
        )

    def test_anonymous_user_cannot_access_administration(self):
        # Custom administration must remain protected.
        url = reverse("catalog_management:dashboard")

        response = self.client.get(url)

        self.assertRedirects(
            response,
            f"{resolve_url(settings.LOGIN_URL)}?next={url}"
        )

    def test_anonymous_navigation_shows_public_links(self):
        # Guests must have access to public navigation.
        response = self.client.get(reverse("catalog:list"))

        self.assertEqual(response.status_code, 200)

        public_routes = (
            "catalog:list",
            "login",
            "student_register",
        )

        for route in public_routes:
            with self.subTest(route=route):
                self.assertContains(
                    response,
                    f'href="{reverse(route)}"'
                )

    def test_anonymous_navigation_hides_protected_links(self):
        # Confidential workspace and administration links
        # must not appear in the anonymous interface.
        response = self.client.get(reverse("catalog:list"))

        self.assertEqual(response.status_code, 200)

        protected_routes = (
            "core:home",
            "core:about",
            "core:contact",
            "projects:project_list",
            "projects:project_create",
            "projects:analytics",
            "projects:schedule",
            "catalog_management:dashboard",
        )

        for route in protected_routes:
            with self.subTest(route=route):
                self.assertNotContains(
                    response,
                    f'href="{reverse(route)}"'
                )

class CategoryHierarchyVisibilityTests(TestCase):
    """
    Verify that inactive category ancestors prevent
    public access and purchasing of descendant services.
    """

    @classmethod
    def setUpTestData(cls):
        # Create a regular user for cart and checkout tests.
        cls.user = get_user_model().objects.create_user(
            username="hierarchy_visibility_test",
            password="TestPassword123!"
        )

        # Create a three-level active category hierarchy.
        cls.root = Category.objects.create(
            name="Career Development",
            slug="career-development",
            is_active=True
        )

        cls.parent = Category.objects.create(
            name="Professional Preparation",
            slug="professional-preparation",
            parent=cls.root,
            is_active=True
        )

        cls.child = Category.objects.create(
            name="Interview Preparation",
            slug="interview-preparation",
            parent=cls.parent,
            is_active=True
        )

        cls.item = CatalogItem.objects.create(
            name="Mock Interview Workshop",
            slug="mock-interview-workshop",
            description="Professional interview coaching.",
            category=cls.child,
            image="catalog/items/hierarchy-test.png",
            price=Decimal("15.00"),
            delivery_format="in_person",
            is_active=True,
            is_available=True
        )

    def deactivate_category(self, category):
        """Simulate an administrator deactivating a category."""

        category.is_active = False
        category.save(update_fields=["is_active"])

    def add_item_to_cart(self):
        """Add the available service through the real endpoint."""

        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                "catalog:add_to_cart",
                kwargs={"slug": self.item.slug}
            )
        )

        self.assertEqual(response.status_code, 302)

        self.assertEqual(
            self.client.session.get("catalog_cart"),
            {str(self.item.pk): 1}
        )

    def test_active_hierarchy_is_publicly_visible(self):
        # Services in completely active hierarchies remain visible.
        response = self.client.get(reverse("catalog:list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.item.name)

        self.assertEqual(
            response.context["total_items"],
            1
        )

        detail_response = self.client.get(
            reverse(
                "catalog:detail",
                kwargs={"slug": self.item.slug}
            )
        )

        self.assertEqual(detail_response.status_code, 200)

    def test_inactive_parent_hides_descendant_service(self):
        # An inactive immediate parent must hide its descendants.
        self.deactivate_category(self.parent)

        response = self.client.get(reverse("catalog:list"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.item.name)
        self.assertEqual(response.context["total_items"], 0)

        self.assertNotIn(
            self.child.pk,
            response.context["categories"].values_list(
                "pk",
                flat=True
            )
        )

    def test_inactive_grandparent_hides_descendant_service(self):
        # Visibility restrictions must apply beyond one level.
        self.deactivate_category(self.root)

        response = self.client.get(reverse("catalog:list"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.item.name)
        self.assertEqual(response.context["total_items"], 0)

        visible_ids = set(
            response.context["categories"].values_list(
                "pk",
                flat=True
            )
        )

        self.assertNotIn(self.root.pk, visible_ids)
        self.assertNotIn(self.parent.pk, visible_ids)
        self.assertNotIn(self.child.pk, visible_ids)

    def test_search_cannot_expose_hidden_service(self):
        # Search and direct category filters cannot bypass visibility.
        self.deactivate_category(self.root)

        response = self.client.get(
            reverse("catalog:list"),
            data={
                "q": "Mock Interview",
                "category": self.child.slug
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.item.name)
        self.assertEqual(response.context["total_items"], 0)

    def test_direct_detail_access_rejects_hidden_service(self):
        # Knowing the item's URL must not bypass visibility rules.
        self.deactivate_category(self.root)

        url = reverse(
            "catalog:detail",
            kwargs={"slug": self.item.slug}
        )

        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

        self.client.force_login(self.user)

        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_hidden_service_cannot_be_added_to_cart(self):
        # Direct POST requests must not add hidden services.
        self.client.force_login(self.user)
        self.deactivate_category(self.root)

        response = self.client.post(
            reverse(
                "catalog:add_to_cart",
                kwargs={"slug": self.item.slug}
            )
        )

        self.assertEqual(response.status_code, 404)

        self.assertEqual(
            self.client.session.get("catalog_cart", {}),
            {}
        )

    def test_existing_cart_marks_hidden_service_unavailable(self):
        # Previously added services remain removable but unavailable.
        self.add_item_to_cart()
        self.deactivate_category(self.root)

        response = self.client.get(reverse("catalog:cart"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["has_unavailable_items"])
        self.assertEqual(len(response.context["cart_lines"]), 1)

        self.assertFalse(
            response.context["cart_lines"][0]["can_checkout"]
        )

    def test_hidden_service_quantity_cannot_be_updated(self):
        # Quantity modifications must respect category visibility.
        self.add_item_to_cart()
        self.deactivate_category(self.root)

        response = self.client.post(
            reverse(
                "catalog:update_cart_quantity",
                kwargs={"slug": self.item.slug}
            ),
            data={"quantity": "3"}
        )

        self.assertEqual(response.status_code, 404)

        self.assertEqual(
            self.client.session.get("catalog_cart"),
            {str(self.item.pk): 1}
        )

    def test_hidden_service_can_still_be_removed_from_cart(self):
        # Users must be able to remove services that become hidden.
        self.add_item_to_cart()
        self.deactivate_category(self.root)

        response = self.client.post(
            reverse(
                "catalog:remove_from_cart",
                kwargs={"slug": self.item.slug}
            )
        )

        self.assertRedirects(
            response,
            reverse("catalog:cart")
        )

        self.assertEqual(
            self.client.session.get("catalog_cart", {}),
            {}
        )

    def test_checkout_rejects_hidden_service_and_preserves_cart(self):
        # Direct checkout must fail without creating an order.
        from .models import Order, OrderItem

        self.add_item_to_cart()
        self.deactivate_category(self.root)

        response = self.client.post(
            reverse("catalog:place_order")
        )

        self.assertRedirects(
            response,
            reverse("catalog:cart")
        )

        self.assertFalse(Order.objects.exists())
        self.assertFalse(OrderItem.objects.exists())

        self.assertEqual(
            self.client.session.get("catalog_cart"),
            {str(self.item.pk): 1}
        )

    def test_reactivated_hierarchy_restores_service_visibility(self):
        # Restoring the complete hierarchy restores public access.
        self.deactivate_category(self.root)

        response = self.client.get(reverse("catalog:list"))
        self.assertEqual(response.context["total_items"], 0)

        self.root.is_active = True
        self.root.save(update_fields=["is_active"])

        response = self.client.get(reverse("catalog:list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_items"], 1)
        self.assertContains(response, self.item.name)

class AdvancedCatalogFilteringTests(TestCase):
    """
    Verify advanced catalogue filtering, hierarchical
    browsing, validation, and pagination.
    """

    @classmethod
    def setUpTestData(cls):
        # Create parent, child and unrelated categories.
        cls.parent = Category.objects.create(
            name="Career Development",
            slug="career-development"
        )

        cls.child = Category.objects.create(
            name="CV Preparation",
            slug="cv-preparation",
            parent=cls.parent
        )

        cls.other = Category.objects.create(
            name="Networking Events",
            slug="networking-events"
        )

        # Create services with different prices and formats.
        cls.free_item = CatalogItem.objects.create(
            name="CV Writing Workshop",
            slug="cv-writing-workshop",
            description="Professional CV preparation.",
            category=cls.child,
            image="catalog/items/free-test.png",
            price=Decimal("0.00"),
            delivery_format="in_person"
        )

        cls.online_item = CatalogItem.objects.create(
            name="Online CV Review",
            slug="online-cv-review",
            description="Personalized CV feedback.",
            category=cls.child,
            image="catalog/items/online-test.png",
            price=Decimal("20.00"),
            delivery_format="online"
        )

        cls.hybrid_item = CatalogItem.objects.create(
            name="Career Coaching Programme",
            slug="career-coaching-programme",
            description="Professional career guidance.",
            category=cls.parent,
            image="catalog/items/hybrid-test.png",
            price=Decimal("50.00"),
            delivery_format="hybrid"
        )

        cls.other_item = CatalogItem.objects.create(
            name="Employer Networking Event",
            slug="employer-networking-event",
            description="Meet prospective employers.",
            category=cls.other,
            image="catalog/items/networking-test.png",
            price=Decimal("20.00"),
            delivery_format="online"
        )

    def assert_filtered_items(self, filters, expected_items):
        """Verify the exact services returned by a filter."""

        response = self.client.get(
            reverse("catalog:list"),
            data=filters
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.context["total_items"],
            len(expected_items)
        )

        actual_ids = {
            item.pk for item in response.context["items"]
        }

        expected_ids = {
            item.pk for item in expected_items
        }

        self.assertEqual(actual_ids, expected_ids)

        return response

    def test_minimum_price_filter_is_inclusive(self):
        # Services matching the minimum boundary are included.
        self.assert_filtered_items(
            {"min_price": "20.00"},
            [
                self.online_item,
                self.hybrid_item,
                self.other_item
            ]
        )

    def test_maximum_price_filter_is_inclusive(self):
        # Services matching the maximum boundary are included.
        self.assert_filtered_items(
            {"max_price": "20.00"},
            [
                self.free_item,
                self.online_item,
                self.other_item
            ]
        )

    def test_zero_price_range_returns_free_services(self):
        # Zero must not be interpreted as an empty filter.
        self.assert_filtered_items(
            {
                "min_price": "0",
                "max_price": "0"
            },
            [self.free_item]
        )

    def test_delivery_format_filtering(self):
        # Every supported delivery format must work.
        scenarios = (
            ("in_person", [self.free_item]),
            ("online", [self.online_item, self.other_item]),
            ("hybrid", [self.hybrid_item]),
        )

        for delivery_format, expected in scenarios:
            with self.subTest(delivery_format=delivery_format):
                self.assert_filtered_items(
                    {"delivery_format": delivery_format},
                    expected
                )

    def test_parent_category_includes_descendants(self):
        # Parent filtering includes its visible subcategories.
        self.assert_filtered_items(
            {"category": self.parent.slug},
            [
                self.free_item,
                self.online_item,
                self.hybrid_item
            ]
        )

    def test_subcategory_excludes_unrelated_services(self):
        # A child category must not include parent or sibling items.
        self.assert_filtered_items(
            {"category": self.child.slug},
            [self.free_item, self.online_item]
        )

    def test_all_advanced_filters_can_be_combined(self):
        # Every submitted filter must constrain the results.
        self.assert_filtered_items(
            {
                "q": "CV",
                "category": self.parent.slug,
                "min_price": "10.00",
                "max_price": "30.00",
                "delivery_format": "online"
            },
            [self.online_item]
        )

    def test_invalid_price_range_displays_validation_error(self):
        # Reversed price boundaries must be rejected.
        response = self.assert_filtered_items(
            {
                "min_price": "100",
                "max_price": "20"
            },
            []
        )

        self.assertIn(
            "max_price",
            response.context["filter_form"].errors
        )

        self.assertContains(
            response,
            "Check your search filters"
        )

        self.assertContains(
            response,
            "Maximum price must be greater than "
            "or equal to minimum price."
        )

    def test_invalid_filter_values_are_rejected(self):
        # Invalid GET parameters must never broaden results.
        scenarios = (
            {"min_price": "-10"},
            {"max_price": "abc"},
            {"max_price": "10.999"},
            {"min_price": "1000000"},
            {"delivery_format": "unsupported"},
            {"min_price": "NaN"},
            {"max_price": "Infinity"},
        )

        for filters in scenarios:
            with self.subTest(filters=filters):
                response = self.assert_filtered_items(
                    filters,
                    []
                )

                self.assertFalse(
                    response.context["filter_form"].is_valid()
                )

                self.assertContains(
                    response,
                    "Check your search filters"
                )

    def test_valid_filters_without_matches_show_correct_state(self):
        # A filtered empty state differs from an empty catalogue.
        response = self.assert_filtered_items(
            {"min_price": "100"},
            []
        )

        self.assertContains(
            response,
            "No matching opportunities"
        )

        self.assertContains(
            response,
            "Clear All Filters"
        )

        self.assertNotContains(
            response,
            "New opportunities are on the way"
        )

    def test_empty_catalogue_shows_general_empty_state(self):
        # No available services should display the general message.
        CatalogItem.objects.update(is_available=False)

        response = self.assert_filtered_items({}, [])

        self.assertContains(
            response,
            "New opportunities are on the way"
        )

        self.assertNotContains(
            response,
            "No matching opportunities"
        )

    def test_pagination_preserves_all_advanced_filters(self):
        # Create enough matching services for multiple pages.
        for index in range(10):
            CatalogItem.objects.create(
                name=f"CV & career workshop {index:02d}",
                slug=f"pagination-workshop-{index}",
                description="Career preparation.",
                category=self.child,
                image="catalog/items/pagination-test.png",
                price=Decimal("0.00"),
                delivery_format="online"
            )

        filters = {
            "q": "CV & career",
            "category": self.parent.slug,
            "min_price": "0.00",
            "max_price": "0.00",
            "delivery_format": "online"
        }

        expected_query = (
            "q=CV+%26+career"
            "&amp;category=career-development"
            "&amp;min_price=0.00"
            "&amp;max_price=0.00"
            "&amp;delivery_format=online"
        )

        # Verify the first page and its Next link.
        response = self.client.get(
            reverse("catalog:list"),
            data=filters
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_items"], 10)
        self.assertEqual(len(response.context["items"]), 9)

        self.assertContains(
            response,
            f"?page=2&amp;{expected_query}"
        )

        # Verify the second page and its Previous link.
        response = self.client.get(
            reverse("catalog:list"),
            data={**filters, "page": "2"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_items"], 10)
        self.assertEqual(response.context["page_obj"].number, 2)
        self.assertEqual(len(response.context["items"]), 1)

        self.assertContains(
            response,
            "CV &amp; career workshop 09"
        )

        self.assertContains(
            response,
            f"?page=1&amp;{expected_query}"
        )