from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.conf import settings
from django.shortcuts import resolve_url
from .forms import CategoryForm
from .models import Category, CatalogItem
from core.models import UserProfile

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