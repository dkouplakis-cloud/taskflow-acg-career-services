from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import resolve_url
from django.test import RequestFactory

from django.urls import reverse
from .permissions import role_required
from django.contrib.auth import get_user_model
from django.test import TestCase
from .models import UserProfile


class UserProfileSignalTests(TestCase):
    """
    Verify automatic profile creation and
    protection of existing user roles.
    """

    def test_new_user_receives_regular_profile(self):
        user = get_user_model().objects.create_user(
            username="profile_test_user",
            password="TestPassword123!"
        )

        profile = UserProfile.objects.get(user=user)

        self.assertEqual(
            profile.role,
            UserProfile.Role.REGULAR
        )

    def test_saving_user_does_not_duplicate_profile(self):
        user = get_user_model().objects.create_user(
            username="duplicate_test_user",
            password="TestPassword123!"
        )

        user.first_name = "Updated"
        user.save()

        self.assertEqual(
            UserProfile.objects.filter(user=user).count(),
            1
        )

    def test_saving_user_preserves_existing_role(self):
        user = get_user_model().objects.create_user(
            username="role_test_user",
            password="TestPassword123!"
        )

        profile = user.profile
        profile.role = UserProfile.Role.POWER
        profile.save()

        user.first_name = "Updated"
        user.save()

        profile.refresh_from_db()

        self.assertEqual(
            profile.role,
            UserProfile.Role.POWER
        )

class RolePermissionTests(TestCase):
    """
    Verify server-side role-based authorization.
    """

    def setUp(self):
        self.factory = RequestFactory()

        self.user = get_user_model().objects.create_user(
            username="permission_test_user",
            password="TestPassword123!"
        )

    def make_request(self, user):
        request = self.factory.get("/protected-test/")
        request.user = user
        return request

    def protected_view(self, *allowed_roles):
        @role_required(*allowed_roles)
        def view(request):
            return HttpResponse("Access granted")

        return view

    def test_anonymous_user_redirected_to_login(self):
        view = self.protected_view(
            UserProfile.Role.ADMIN
        )

        request = self.make_request(AnonymousUser())
        response = view(request)

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            resolve_url(settings.LOGIN_URL),
            response["Location"]
        )

    def test_regular_user_cannot_access_admin_view(self):
        view = self.protected_view(
            UserProfile.Role.ADMIN
        )

        request = self.make_request(self.user)

        with self.assertRaises(PermissionDenied):
            view(request)

    def test_power_user_can_access_power_view(self):
        profile = self.user.profile
        profile.role = UserProfile.Role.POWER
        profile.save()

        view = self.protected_view(
            UserProfile.Role.POWER,
            UserProfile.Role.ADMIN
        )

        request = self.make_request(self.user)
        response = view(request)

        self.assertEqual(response.status_code, 200)

    def test_power_user_cannot_access_admin_view(self):
        profile = self.user.profile
        profile.role = UserProfile.Role.POWER
        profile.save()

        view = self.protected_view(
            UserProfile.Role.ADMIN
        )

        request = self.make_request(self.user)

        with self.assertRaises(PermissionDenied):
            view(request)

    def test_admin_user_can_access_admin_view(self):
        profile = self.user.profile
        profile.role = UserProfile.Role.ADMIN
        profile.save()

        view = self.protected_view(
            UserProfile.Role.ADMIN
        )

        request = self.make_request(self.user)
        response = view(request)

        self.assertEqual(response.status_code, 200)

class RoleAwareLoginTests(TestCase):
    """
    Verify role-aware login redirection
    through TaskFlow's actual login URL.
    """

    def setUp(self):
        self.password = "TestPassword123!"

        self.user = get_user_model().objects.create_user(
            username="login_redirect_test",
            password=self.password
        )

    def set_role(self, role):
        profile = self.user.profile
        profile.role = role
        profile.save()

    def login(self, url=None):
        return self.client.post(
            url or reverse("login"),
            {
                "username": self.user.username,
                "password": self.password
            }
        )

    def test_admin_redirects_to_management_dashboard(self):
        self.set_role(UserProfile.Role.ADMIN)

        response = self.login()

        self.assertRedirects(
            response,
            reverse("catalog_management:dashboard"),
            fetch_redirect_response=False
        )

    def test_regular_user_redirects_to_projects(self):
        response = self.login()

        self.assertRedirects(
            response,
            reverse("projects:project_list"),
            fetch_redirect_response=False
        )

    def test_power_user_redirects_to_projects(self):
        self.set_role(UserProfile.Role.POWER)

        response = self.login()

        self.assertRedirects(
            response,
            reverse("projects:project_list"),
            fetch_redirect_response=False
        )

    def test_safe_next_destination_is_respected(self):
        self.set_role(UserProfile.Role.ADMIN)

        destination = reverse("core:about")

        response = self.login(
            reverse("login") + "?next=" + destination
        )

        self.assertRedirects(
            response,
            destination,
            fetch_redirect_response=False
        )

    def test_external_next_destination_is_rejected(self):
        self.set_role(UserProfile.Role.ADMIN)

        response = self.login(
            reverse("login") +
            "?next=https://untrusted.example/path"
        )

        self.assertRedirects(
            response,
            reverse("catalog_management:dashboard"),
            fetch_redirect_response=False
        )

# ==========================================================
# CAREER SERVICES WORKSPACE AUTHORIZATION TESTS
# ==========================================================

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from .permissions import workspace_required


class WorkspaceAuthorizationTests(TestCase):
    """
    Verify that internal workspace access is restricted
    to explicitly authorized Career Services personnel.
    """

    def setUp(self):
        self.factory = RequestFactory()

        # A simple protected view used only for testing.
        @workspace_required
        def protected_view(request):
            return HttpResponse("Workspace access granted.")

        self.protected_view = protected_view

    def test_regular_student_cannot_access_workspace(self):
        """
        An authenticated student without workspace
        authorization must receive HTTP 403.
        """

        student = get_user_model().objects.create_user(
            username="regular_student_access_test",
            password="TestPassword123!"
        )

        request = self.factory.get("/projects/")
        request.user = student

        with self.assertRaises(PermissionDenied):
            self.protected_view(request)

    def test_authorized_personnel_can_access_workspace(self):
        """
        Explicitly authorized staff, faculty and student
        assistants must pass the workspace permission check.
        """

        group_names = (
            "Career Services Staff",
            "Authorized Faculty",
            "Career Services Student Assistants",
        )

        for index, group_name in enumerate(group_names):

            with self.subTest(group=group_name):

                group, _ = Group.objects.get_or_create(
                    name=group_name
                )

                user = get_user_model().objects.create_user(
                    username=f"workspace_user_{index}",
                    password="TestPassword123!"
                )

                user.groups.add(group)

                request = self.factory.get("/projects/")
                request.user = user

                response = self.protected_view(request)

                self.assertEqual(
                    response.status_code,
                    200
                )

    def test_revoked_student_assistant_access(self):
        """
        Removing workspace group membership must
        immediately revoke internal access.
        """

        group, _ = Group.objects.get_or_create(
            name="Career Services Student Assistants"
        )

        user = get_user_model().objects.create_user(
            username="revoked_assistant_test",
            password="TestPassword123!"
        )

        user.groups.add(group)

        request = self.factory.get("/projects/")
        request.user = user

        # The authorized assistant initially has access.
        response = self.protected_view(request)

        self.assertEqual(response.status_code, 200)

        # Simulate the assistant leaving Career Services.
        user.groups.remove(group)

        # Access must now be denied.
        with self.assertRaises(PermissionDenied):
            self.protected_view(request)

    def test_inactive_staff_account_cannot_access_workspace(self):
        """
        An inactive user must not access the workspace
        even if their authorized group membership remains.
        """

        group, _ = Group.objects.get_or_create(
            name="Career Services Staff"
        )

        user = get_user_model().objects.create_user(
            username="inactive_staff_access_test",
            password="TestPassword123!"
        )

        user.groups.add(group)

        request = self.factory.get("/projects/")
        request.user = user

        # Verify that the active staff member has access.
        response = self.protected_view(request)
        self.assertEqual(response.status_code, 200)

        # Deactivate the staff member's account.
        user.is_active = False
        user.save(update_fields=["is_active"])

        # Group membership must not override deactivation.
        with self.assertRaises(PermissionDenied):
            self.protected_view(request)

    def test_regular_student_navigation_hides_workspace_links(self):
        """
        Ordinary students must not see internal workspace
        navigation links, even when authenticated.
        """
        from django.urls import reverse

        # Create an ordinary student without workspace access.
        student = get_user_model().objects.create_user(
            username="student_navigation_test",
            password="TestPassword123!"
        )

        self.client.force_login(student)

        # Render a public page using the shared layout.
        response = self.client.get(
            reverse("core:contact")
        )

        self.assertEqual(response.status_code, 200)

        # Internal workspace links must remain hidden.
        restricted_routes = (
            "projects:project_list",
            "projects:analytics",
            "projects:project_create",
        )

        for route in restricted_routes:
            with self.subTest(route=route):
                restricted_url = reverse(route)

                self.assertNotContains(
                    response,
                    f'href="{restricted_url}"'
                )

    def test_staff_navigation_shows_workspace_and_management_links(self):
        """
        Authorized Career Services staff must see
        workspace and project management navigation.
        """
        from django.urls import reverse

        # Create an explicitly authorized staff account.
        staff_group, _ = Group.objects.get_or_create(
            name="Career Services Staff"
        )

        staff = get_user_model().objects.create_user(
            username="staff_navigation_test",
            password="TestPassword123!"
        )
        staff.groups.add(staff_group)

        self.client.force_login(staff)

        # Render the shared layout through a public page.
        response = self.client.get(
            reverse("core:contact")
        )

        self.assertEqual(response.status_code, 200)

        # Staff must see workspace and management links.
        expected_routes = (
            "projects:project_list",
            "projects:analytics",
            "projects:project_create",
        )

        for route in expected_routes:
            with self.subTest(route=route):
                expected_url = reverse(route)

                self.assertContains(
                    response,
                    f'href="{expected_url}"'
                )

    def test_scoped_members_navigation_hides_project_creation(self):
        """
        Authorized faculty and student assistants can
        see workspace links, but not staff-only actions.
        """
        from django.urls import reverse

        group_names = (
            "Authorized Faculty",
            "Career Services Student Assistants",
        )

        for index, group_name in enumerate(group_names):
            with self.subTest(group=group_name):
                group, _ = Group.objects.get_or_create(
                    name=group_name
                )

                user = get_user_model().objects.create_user(
                    username=f"scoped_navigation_user_{index}",
                    password="TestPassword123!"
                )
                user.groups.add(group)

                self.client.force_login(user)

                response = self.client.get(
                    reverse("core:contact")
                )

                self.assertEqual(response.status_code, 200)

                # Both roles can access internal navigation.
                for route in (
                    "projects:project_list",
                    "projects:analytics",
                ):
                    self.assertContains(
                        response,
                        f'href="{reverse(route)}"'
                    )

                # Project creation is reserved for staff.
                self.assertNotContains(
                    response,
                    f'href="{reverse("projects:project_create")}"'
                )