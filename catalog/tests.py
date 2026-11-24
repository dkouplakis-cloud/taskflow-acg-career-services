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