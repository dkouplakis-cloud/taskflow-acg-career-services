from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import resolve_url
from django.test import RequestFactory
from datetime import timedelta

from django.utils import timezone
from projects.models import Project, ProjectAccess
from tasks.models import Task
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

    def test_regular_user_redirects_to_catalog(self):
        """
        A regular user without explicit Career Services
        workspace authorization must enter the public
        catalogue rather than the internal Projects area.
        """

        # The test user has a Regular profile role
        # and no authorized workspace group membership.
        response = self.login()

        # Regular users enter the public student portal.
        self.assertRedirects(
            response,
            reverse("catalog:list"),
            fetch_redirect_response=False,
        )

        # Authentication must succeed.
        self.assertEqual(
            self.client.session.get("_auth_user_id"),
            str(self.user.pk),
        )

        # Internal Career Services projects remain protected.
        workspace_response = self.client.get(
            reverse("projects:project_list")
        )

        self.assertEqual(
            workspace_response.status_code,
            403,
        )

    def test_power_user_without_workspace_access_redirects_to_catalog(self):
        """
        A Power User profile role alone must not grant
        access to the Career Services workspace.

        Explicit group authorization is required.
        """

        # Assign the Power User profile role without
        # granting any workspace group membership.
        self.set_role(UserProfile.Role.POWER)

        response = self.login()

        # Users without workspace authorization
        # must enter the public catalogue.
        self.assertRedirects(
            response,
            reverse("catalog:list"),
            fetch_redirect_response=False,
        )

        # Confirm successful authentication.
        self.assertEqual(
            self.client.session.get("_auth_user_id"),
            str(self.user.pk),
        )

        # The profile role alone cannot authorize
        # access to internal Career Services projects.
        workspace_response = self.client.get(
            reverse("projects:project_list")
        )

        self.assertEqual(
            workspace_response.status_code,
            403,
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

    def test_authorized_staff_redirects_to_projects(self):
        """
        Explicitly authorized Career Services staff
        must retain access to the internal workspace.
        """
        from django.contrib.auth.models import Group

        # Grant the existing test user explicit
        # Career Services staff authorization.
        staff_group, _ = Group.objects.get_or_create(
            name="Career Services Staff"
        )

        self.user.groups.add(staff_group)

        # The user's profile role remains REGULAR.
        # Workspace access depends on group membership.
        self.assertEqual(
            self.user.profile.role,
            UserProfile.Role.REGULAR,
        )

        response = self.login()

        # Authorized staff should enter the workspace.
        self.assertRedirects(
            response,
            reverse("projects:project_list"),
            fetch_redirect_response=False,
        )

        # The internal Projects page must be accessible.
        workspace_response = self.client.get(
            reverse("projects:project_list")
        )

        self.assertEqual(
            workspace_response.status_code,
            200,
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

class StudentRegistrationTests(TestCase):
    """
    Verify public student registration and ensure
    new accounts receive no internal workspace privileges.
    """

    def test_registration_requires_approval_before_account_creation(self):
        """
        Public registration must create a pending application.

        No Django user account may exist, and the applicant
        must remain unauthenticated until administrator approval.
        """
        from django.contrib.auth.hashers import check_password

        from .models import StudentRegistrationRequest

        password = "StrongDemoPassword847!"

        registration_data = {
            "username": "student_registration_test",
            "first_name": "Alex",
            "last_name": "Student",
            "email": "student.registration@example.com",
            "password1": password,
            "password2": password,
        }

        # Submit the public registration application.
        response = self.client.post(
            reverse("student_register"),
            registration_data,
        )

        # Submission returns to the registration page,
        # not the authenticated student catalogue.
        self.assertRedirects(
            response,
            reverse("student_register"),
            fetch_redirect_response=False,
        )

        # Verify the pending application was created.
        application = StudentRegistrationRequest.objects.get(
            username="student_registration_test"
        )

        self.assertEqual(
            application.status,
            StudentRegistrationRequest.Status.PENDING,
        )

        self.assertEqual(application.first_name, "Alex")
        self.assertEqual(application.last_name, "Student")
        self.assertEqual(
            application.email,
            "student.registration@example.com",
        )

        # The submitted password must never be stored
        # in plaintext.
        self.assertNotEqual(
            application.password_hash,
            password,
        )

        self.assertTrue(
            check_password(password, application.password_hash)
        )

        # No Django user exists before approval.
        self.assertFalse(
            get_user_model().objects.filter(
                username="student_registration_test"
            ).exists()
        )

        # The applicant must remain unauthenticated.
        self.assertNotIn(
            "_auth_user_id",
            self.client.session,
        )

        # Unauthenticated applicants cannot access
        # the internal Career Services workspace.
        workspace_response = self.client.get(
            reverse("projects:project_list")
        )

        self.assertRedirects(
            workspace_response,
            f'{reverse("login")}?next={reverse("projects:project_list")}',
            fetch_redirect_response=False,
        )

    def test_registration_cannot_self_assign_privileges(self):
        """
        Public registration must never grant administrative
        roles or internal workspace permissions.

        Unauthorized fields must be ignored during
        application submission and account approval.
        """
        from django.contrib.auth.models import Group

        from .models import (
            StudentRegistrationRequest,
            UserProfile,
        )
        from .registration_services import (
            approve_student_registration,
        )

        User = get_user_model()

        # Create a privileged group for the security test.
        staff_group, _ = Group.objects.get_or_create(
            name="Career Services Staff"
        )

        # Attempt to submit unauthorized privilege fields.
        registration_data = {
            "username": "privilege_escalation_test",
            "first_name": "Test",
            "last_name": "Student",
            "email": "privilege.test@example.com",
            "password1": "StrongDemoPassword847!",
            "password2": "StrongDemoPassword847!",
            "is_staff": "on",
            "is_superuser": "on",
            "role": "admin",
            "groups": str(staff_group.pk),
        }

        response = self.client.post(
            reverse("student_register"),
            registration_data,
        )

        # Registration creates only a pending application.
        self.assertRedirects(
            response,
            reverse("student_register"),
            fetch_redirect_response=False,
        )

        application = StudentRegistrationRequest.objects.get(
            username="privilege_escalation_test"
        )

        self.assertEqual(
            application.status,
            StudentRegistrationRequest.Status.PENDING,
        )

        # No account or authenticated session exists yet.
        self.assertFalse(
            User.objects.filter(
                username="privilege_escalation_test"
            ).exists()
        )

        self.assertNotIn(
            "_auth_user_id",
            self.client.session,
        )

        # Create an authorized reviewing administrator.
        administrator = User.objects.create_user(
            username="privilege_review_admin",
            password="SecureAdminPassword847!",
        )

        UserProfile.objects.filter(
            user=administrator
        ).update(role=UserProfile.Role.ADMIN)

        # Approval must ignore all submitted privilege fields.
        student = approve_student_registration(
            application_id=application.pk,
            reviewer=administrator,
        )

        # The approved student receives ordinary privileges.
        self.assertFalse(student.is_staff)
        self.assertFalse(student.is_superuser)
        self.assertFalse(student.groups.exists())

        self.assertEqual(
            student.profile.role,
            UserProfile.Role.REGULAR,
        )

        # The student must not access the internal workspace.
        self.client.force_login(student)

        workspace_response = self.client.get(
            reverse("projects:project_list")
        )

        self.assertEqual(
            workspace_response.status_code,
            403,
        )
    
    def test_registration_rejects_duplicate_email(self):
        """
        Registration must reject email addresses already
        associated with another account, regardless of case.
        """

        User = get_user_model()

        # Create an existing account with a mixed-case email.
        existing_user = User.objects.create_user(
            username="existing_email_test",
            email="Student@Example.com",
            password="ExistingPassword847!"
        )

        # Attempt registration using the same email
        # with different capitalization.
        registration_data = {
            "username": "duplicate_email_test",
            "first_name": "Alex",
            "last_name": "Student",
            "email": "student@example.com",
            "password1": "StrongDemoPassword847!",
            "password2": "StrongDemoPassword847!",
        }

        response = self.client.post(
            reverse("student_register"),
            registration_data
        )

        # Invalid registration must redisplay the form.
        self.assertEqual(response.status_code, 200)

        # Verify that the appropriate error is displayed.
        self.assertContains(
            response,
            "An account with this email address already exists."
        )

        # No new student account should be created.
        self.assertFalse(
            User.objects.filter(
                username="duplicate_email_test"
            ).exists()
        )

        # The existing account must remain unchanged.
        existing_user.refresh_from_db()

        # Django normalizes the email domain to lowercase.
        # The existing account must remain unchanged.
        self.assertEqual(
            existing_user.email,
            "Student@example.com"
        )

        # Failed registration must not authenticate the user.
        self.assertNotIn(
            "_auth_user_id",
            self.client.session
        )
    
    def test_registration_rejects_mismatched_passwords(self):
        """
        Registration must reject mismatched passwords
        without creating or authenticating a user.
        """

        User = get_user_model()

        registration_data = {
            "username": "password_mismatch_test",
            "first_name": "Alex",
            "last_name": "Student",
            "email": "password.test@example.com",
            "password1": "StrongDemoPassword847!",
            "password2": "DifferentPassword963!",
        }

        # Submit the registration form with two
        # different passwords.
        response = self.client.post(
            reverse("student_register"),
            registration_data
        )

        # Invalid submissions must redisplay the form.
        self.assertEqual(response.status_code, 200)

        # Django must report the password mismatch.
        self.assertFormError(
            response.context["form"],
            "password2",
            "The two password fields didn’t match."
        )

        # No account may be created.
        self.assertFalse(
            User.objects.filter(
                username="password_mismatch_test"
            ).exists()
        )

        # Failed registration must not authenticate anyone.
        self.assertNotIn(
            "_auth_user_id",
            self.client.session
        )

    def test_registration_creates_pending_request_only(self):
        """
        Public registration must create a pending application,
        not an active Django user account.

        Passwords must be hashed and applicants must remain
        unauthenticated until administrator approval.
        """
        from django.contrib.auth.hashers import check_password

        from .models import StudentRegistrationRequest

        password = "StrongDemoPassword847!"

        registration_data = {
            "username": "pending_student_test",
            "first_name": "Alex",
            "last_name": "Student",
            "email": "pending.student@example.com",
            "password1": password,
            "password2": password,
        }

        # Submit a valid public registration request.
        response = self.client.post(
            reverse("student_register"),
            registration_data
        )

        self.assertRedirects(
            response,
            reverse("student_register"),
            fetch_redirect_response=False
        )

        # A pending application must be recorded.
        application = StudentRegistrationRequest.objects.get(
            username="pending_student_test"
        )

        self.assertEqual(
            application.status,
            StudentRegistrationRequest.Status.PENDING
        )

        self.assertEqual(
            application.email,
            "pending.student@example.com"
        )

        # Never store the submitted password in plaintext.
        self.assertNotEqual(
            application.password_hash,
            password
        )

        self.assertTrue(
            check_password(password, application.password_hash)
        )

        # Administrator approval is required before
        # creating an actual Django user account.
        self.assertFalse(
            get_user_model().objects.filter(
                username="pending_student_test"
            ).exists()
        )

        # Pending applicants must not be signed in.
        self.assertNotIn(
            "_auth_user_id",
            self.client.session
        )

    def test_duplicate_pending_registrations_are_rejected(self):
        """
        Prevent duplicate pending applications by username
        or email address, including case variations.
        """
        from .models import StudentRegistrationRequest

        registration_data = {
            "username": "pending_duplicate_user",
            "first_name": "Alex",
            "last_name": "Student",
            "email": "pending.student@example.com",
            "password1": "StrongDemoPassword847!",
            "password2": "StrongDemoPassword847!",
        }

        # First application should be accepted.
        response = self.client.post(
            reverse("student_register"),
            registration_data
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            StudentRegistrationRequest.objects.count(),
            1
        )

        # A second application with the same username
        # must be rejected, even with a different email.
        duplicate_username_data = {
            **registration_data,
            "email": "different.student@example.com",
        }

        response = self.client.post(
            reverse("student_register"),
            duplicate_username_data
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "username",
            response.context["form"].errors
        )

        # A second application with the same email must
        # be rejected, regardless of capitalization.
        duplicate_email_data = {
            **registration_data,
            "username": "another_pending_student",
            "email": "PENDING.STUDENT@EXAMPLE.COM",
        }

        response = self.client.post(
            reverse("student_register"),
            duplicate_email_data
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "email",
            response.context["form"].errors
        )

        # Only the original pending application exists.
        self.assertEqual(
            StudentRegistrationRequest.objects.count(),
            1
        )

        # No Django user account has been created.
        self.assertFalse(
            get_user_model().objects.filter(
                username="pending_duplicate_user"
            ).exists()
        )

    def test_database_prevents_duplicate_pending_usernames(self):
        """
        Database constraints must reject pending applications
        with case-insensitive duplicate usernames, even when
        form validation is bypassed.
        """
        from django.contrib.auth.hashers import make_password
        from django.db import IntegrityError, transaction

        from .models import StudentRegistrationRequest

        password_hash = make_password("StrongDatabaseTest847!")

        # Create the first pending application directly
        # through the ORM, bypassing form validation.
        StudentRegistrationRequest.objects.create(
            username="Pending_DB_Student",
            first_name="Alex",
            last_name="Student",
            email="first.database.student@example.com",
            password_hash=password_hash,
        )

        # A second pending application with the same
        # username in different capitalization must fail.
        # The nested atomic block isolates the rollback
        # so the test database remains usable.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StudentRegistrationRequest.objects.create(
                    username="pending_db_student",
                    first_name="Taylor",
                    last_name="Student",
                    email="second.database.student@example.com",
                    password_hash=password_hash,
                )

        # The rejected insertion must not create
        # an additional pending application.
        self.assertEqual(
            StudentRegistrationRequest.objects.count(),
            1,
        )

    def test_database_prevents_duplicate_pending_emails(self):
        """
        Database constraints must reject pending applications
        with case-insensitive duplicate email addresses,
        even when form validation is bypassed.
        """
        from django.contrib.auth.hashers import make_password
        from django.db import IntegrityError, transaction

        from .models import StudentRegistrationRequest

        password_hash = make_password("StrongDatabaseTest847!")

        # Create the original pending application.
        StudentRegistrationRequest.objects.create(
            username="first_email_student",
            first_name="Alex",
            last_name="Student",
            email="Pending.Database@Example.com",
            password_hash=password_hash,
        )

        # A different username must not bypass the email
        # uniqueness constraint using different capitalization.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StudentRegistrationRequest.objects.create(
                    username="second_email_student",
                    first_name="Taylor",
                    last_name="Student",
                    email="pending.database@example.com",
                    password_hash=password_hash,
                )

        # The database must retain only the original request.
        self.assertEqual(
            StudentRegistrationRequest.objects.count(),
            1,
        )

    def test_registration_handles_database_integrity_conflict(self):
        """
        A database conflict during registration must produce
        a form validation error instead of HTTP 500.

        No user account or registration request is created.
        """
        from unittest.mock import patch

        from django.db import IntegrityError

        from .models import StudentRegistrationRequest

        password = "StrongDatabaseTest847!"

        registration_data = {
            "username": "conflict_test_student",
            "first_name": "Alex",
            "last_name": "Student",
            "email": "conflict.student@example.com",
            "password1": password,
            "password2": password,
        }

        # Simulate a database constraint failure occurring
        # after the form has successfully validated.
        with patch(
            "core.auth_views.StudentRegistrationRequest.objects.create",
            side_effect=IntegrityError("Simulated uniqueness conflict"),
        ):
            response = self.client.post(
                reverse("student_register"),
                registration_data,
            )

        # The request must render the registration form
        # rather than returning an internal server error.
        self.assertEqual(response.status_code, 200)

        self.assertIn(
            "This registration request could not be submitted",
            str(response.context["form"].non_field_errors()),
        )

        # A failed submission must not create an application.
        self.assertFalse(
            StudentRegistrationRequest.objects.filter(
                username="conflict_test_student"
            ).exists()
        )

        # No Django user account may be created.
        self.assertFalse(
            get_user_model().objects.filter(
                username="conflict_test_student"
            ).exists()
        )

        # The applicant must remain unauthenticated.
        self.assertNotIn(
            "_auth_user_id",
            self.client.session,
        )

    def test_registration_management_requires_admin_role(self):
        """
        Only users with the Administrator profile role
        may access student registration management.

        Career Services staff membership alone must
        not grant registration approval privileges.
        """
        from django.contrib.auth.models import Group

        from .models import UserProfile

        url = reverse("registration_management:request_list")
        User = get_user_model()

        # Anonymous visitors must authenticate.
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

        # A regular student must be denied.
        student = User.objects.create_user(
            username="regular_registration_test",
            password="SecurePassword847!"
        )

        self.client.force_login(student)

        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

        # Career Services staff membership alone
        # must not grant administrator privileges.
        staff = User.objects.create_user(
            username="staff_registration_test",
            password="SecurePassword847!"
        )

        staff.groups.add(
            Group.objects.get(name="Career Services Staff")
        )

        self.client.force_login(staff)

        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

        # An authorized Administrator may view requests.
        administrator = User.objects.create_user(
            username="admin_registration_test",
            password="SecurePassword847!"
        )

        UserProfile.objects.filter(
            user=administrator
        ).update(role=UserProfile.Role.ADMIN)

        self.client.force_login(administrator)

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

        self.assertTemplateUsed(
            response,
            "registration_management/request_list.html"
        )

    def test_administrator_can_review_pending_registration(self):
        """
        Active administrators may inspect pending applications
        without changing their status or creating user accounts.
        """
        from django.contrib.auth.hashers import make_password

        from .models import StudentRegistrationRequest, UserProfile

        User = get_user_model()

        # Create an authorized administrator.
        administrator = User.objects.create_user(
            username="review_page_admin_test",
            password="SecureAdminPassword847!",
        )

        UserProfile.objects.filter(
            user=administrator
        ).update(role=UserProfile.Role.ADMIN)

        # Create an application awaiting review.
        application = StudentRegistrationRequest.objects.create(
            username="review_page_student",
            first_name="Alex",
            last_name="Student",
            email="review.page.student@example.com",
            password_hash=make_password("StrongStudentPassword847!"),
        )

        review_url = reverse(
            "registration_management:request_detail",
            args=[application.pk],
        )

        self.client.force_login(administrator)

        # The administrator can access the review page.
        response = self.client.get(review_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "registration_management/request_detail.html",
        )

        # Applicant information is displayed.
        self.assertContains(response, "Alex")
        self.assertContains(response, application.email)

        # Password hashes must never appear in the page.
        self.assertNotContains(
            response,
            application.password_hash,
        )

        # Opening the review page does not alter the request.
        application.refresh_from_db()

        self.assertEqual(
            application.status,
            StudentRegistrationRequest.Status.PENDING,
        )
        self.assertIsNone(application.reviewed_at)

        # No student account exists before approval.
        self.assertFalse(
            User.objects.filter(
                username=application.username
            ).exists()
        )

        # The review page itself must not accept POST.
        response = self.client.post(review_url)
        self.assertEqual(response.status_code, 405)

    def test_registration_review_page_requires_admin_role(self):
        """
        Individual registration applications must remain
        inaccessible to anonymous users, regular students,
        and staff without administrator privileges.
        """
        from django.contrib.auth.hashers import make_password
        from django.contrib.auth.models import Group

        from .models import StudentRegistrationRequest

        User = get_user_model()

        # Create an application containing student details.
        application = StudentRegistrationRequest.objects.create(
            username="private_review_student",
            first_name="Alex",
            last_name="Student",
            email="private.review@example.com",
            password_hash=make_password("StrongStudentPassword847!"),
        )

        review_url = reverse(
            "registration_management:request_detail",
            args=[application.pk],
        )

        # Anonymous visitors must authenticate.
        response = self.client.get(review_url)
        self.assertEqual(response.status_code, 302)

        # A regular student must receive HTTP 403.
        student = User.objects.create_user(
            username="unauthorized_review_student",
            password="SecurePassword847!",
        )

        self.client.force_login(student)

        response = self.client.get(review_url)
        self.assertEqual(response.status_code, 403)

        # Workspace membership alone does not grant
        # administrator access to registration records.
        staff = User.objects.create_user(
            username="unauthorized_review_staff",
            password="SecurePassword847!",
        )

        staff.groups.add(
            Group.objects.get(name="Career Services Staff")
        )

        self.client.force_login(staff)

        response = self.client.get(review_url)
        self.assertEqual(response.status_code, 403)

        # Unauthorized access must not modify the request.
        application.refresh_from_db()

        self.assertEqual(
            application.status,
            StudentRegistrationRequest.Status.PENDING,
        )
        self.assertIsNone(application.reviewed_at)

    def test_reviewed_registration_cannot_be_reopened(self):
        """
        Approved and rejected registration applications
        must not be accessible through the pending review page.
        """
        from .models import StudentRegistrationRequest, UserProfile

        User = get_user_model()

        # Create an authorized administrator.
        administrator = User.objects.create_user(
            username="reviewed_application_admin",
            password="SecureAdminPassword847!",
        )

        UserProfile.objects.filter(
            user=administrator
        ).update(role=UserProfile.Role.ADMIN)

        self.client.force_login(administrator)

        # Both final decisions must prevent reopening
        # an application for another review.
        reviewed_statuses = (
            StudentRegistrationRequest.Status.APPROVED,
            StudentRegistrationRequest.Status.REJECTED,
        )

        for status in reviewed_statuses:
            with self.subTest(status=status):
                application = StudentRegistrationRequest.objects.create(
                    username=f"reviewed_{status}_student",
                    first_name="Alex",
                    last_name="Student",
                    email=f"reviewed.{status}@example.com",
                    password_hash="",
                    status=status,
                    reviewed_by=administrator,
                )

                review_url = reverse(
                    "registration_management:request_detail",
                    args=[application.pk],
                )

                # Already-reviewed applications must
                # return HTTP 404 from the review page.
                response = self.client.get(review_url)

                self.assertEqual(response.status_code, 404)

                # Viewing the URL must not change
                # the administrator's original decision.
                application.refresh_from_db()

                self.assertEqual(application.status, status)
                self.assertEqual(
                    application.reviewed_by,
                    administrator,
                )

    def test_administrator_approval_creates_student_account(self):
        """
        Administrator approval must create a regular
        student account and record the review securely.
        """
        from django.contrib.auth.hashers import make_password

        from .models import (
            StudentRegistrationRequest,
            UserProfile,
        )
        from .registration_services import (
            approve_student_registration,
        )

        User = get_user_model()
        password = "StrongStudentPassword847!"

        # Create an authorized administrator.
        administrator = User.objects.create_user(
            username="approval_admin_test",
            password="SecureAdminPassword847!"
        )

        UserProfile.objects.filter(
            user=administrator
        ).update(role=UserProfile.Role.ADMIN)

        # Create a pending application without a user account.
        application = StudentRegistrationRequest.objects.create(
            username="approved_student_test",
            first_name="Alex",
            last_name="Student",
            email="approved.student@example.com",
            password_hash=make_password(password),
        )

        self.assertFalse(
            User.objects.filter(
                username="approved_student_test"
            ).exists()
        )

        # The administrator approves the application.
        student = approve_student_registration(
            application_id=application.pk,
            reviewer=administrator,
        )

        # Verify the student's account and credentials.
        self.assertEqual(
            student.username,
            "approved_student_test"
        )
        self.assertTrue(student.check_password(password))
        self.assertTrue(student.is_active)
        self.assertFalse(student.is_staff)
        self.assertFalse(student.is_superuser)

        # The student must have no privileged groups.
        self.assertEqual(student.groups.count(), 0)

        # The profile must retain the regular student role.
        self.assertEqual(
            student.profile.role,
            UserProfile.Role.REGULAR
        )

        # Verify the administrator's review record.
        application.refresh_from_db()

        self.assertEqual(
            application.status,
            StudentRegistrationRequest.Status.APPROVED
        )
        self.assertEqual(
            application.reviewed_by,
            administrator
        )
        self.assertIsNotNone(application.reviewed_at)

        # Remove the sensitive hash after approval.
        self.assertEqual(application.password_hash, "")

        # Exactly one account was created for the applicant.
        self.assertEqual(
            User.objects.filter(
                username="approved_student_test"
            ).count(),
            1
        )

    def test_regular_student_cannot_approve_registration(self):
        """
        A regular student must not approve applications,
        even by calling the approval service directly.
        """
        from django.contrib.auth.hashers import make_password
        from django.core.exceptions import PermissionDenied

        from .models import StudentRegistrationRequest
        from .registration_services import (
            approve_student_registration,
        )

        User = get_user_model()

        # Create an ordinary student without administrator rights.
        reviewer = User.objects.create_user(
            username="unauthorized_reviewer_test",
            password="SecurePassword847!"
        )

        # Create an application awaiting administrator approval.
        application = StudentRegistrationRequest.objects.create(
            username="protected_applicant_test",
            first_name="Alex",
            last_name="Student",
            email="protected.applicant@example.com",
            password_hash=make_password("StudentPassword847!"),
        )

        # The service must reject unauthorized approval.
        with self.assertRaises(PermissionDenied):
            approve_student_registration(
                application_id=application.pk,
                reviewer=reviewer,
            )

        # The application must remain pending.
        application.refresh_from_db()

        self.assertEqual(
            application.status,
            StudentRegistrationRequest.Status.PENDING
        )

        self.assertIsNone(application.reviewed_by)
        self.assertIsNone(application.reviewed_at)

        # No account may be created after denial.
        self.assertFalse(
            User.objects.filter(
                username="protected_applicant_test"
            ).exists()
        )

    def test_registration_cannot_be_approved_twice(self):
        """
        Prevent repeated approval of the same application
        and ensure only one student account is created.
        """
        from django.contrib.auth.hashers import make_password

        from .models import (
            StudentRegistrationRequest,
            UserProfile,
        )
        from .registration_services import (
            RegistrationApprovalError,
            approve_student_registration,
        )

        User = get_user_model()

        # Create an authorized administrator.
        administrator = User.objects.create_user(
            username="repeat_approval_admin",
            password="SecureAdminPassword847!"
        )

        UserProfile.objects.filter(
            user=administrator
        ).update(role=UserProfile.Role.ADMIN)

        # Create an application awaiting review.
        application = StudentRegistrationRequest.objects.create(
            username="repeat_approval_student",
            first_name="Alex",
            last_name="Student",
            email="repeat.student@example.com",
            password_hash=make_password("StudentPassword847!"),
        )

        # The first approval should succeed.
        student = approve_student_registration(
            application_id=application.pk,
            reviewer=administrator,
        )

        self.assertIsNotNone(student.pk)

        # The second approval must be rejected.
        with self.assertRaises(RegistrationApprovalError):
            approve_student_registration(
                application_id=application.pk,
                reviewer=administrator,
            )

        # Exactly one student account must exist.
        self.assertEqual(
            User.objects.filter(
                username="repeat_approval_student"
            ).count(),
            1
        )

        # The original approval record must be preserved.
        application.refresh_from_db()

        self.assertEqual(
            application.status,
            StudentRegistrationRequest.Status.APPROVED
        )

        self.assertEqual(
            application.reviewed_by,
            administrator
        )

        self.assertIsNotNone(application.reviewed_at)

        # The application must no longer retain
        # the student's password hash.
        self.assertEqual(application.password_hash, "")

    def test_administrator_rejection_does_not_create_account(self):
        """
        Rejection must record the administrator's decision,
        clear the password hash, and never create a user.
        """
        from django.contrib.auth.hashers import make_password

        from .models import (
            StudentRegistrationRequest,
            UserProfile,
        )
        from .registration_services import (
            reject_student_registration,
        )

        User = get_user_model()

        # Create an authorized administrator.
        administrator = User.objects.create_user(
            username="rejection_admin_test",
            password="SecureAdminPassword847!"
        )

        UserProfile.objects.filter(
            user=administrator
        ).update(role=UserProfile.Role.ADMIN)

        # Create an application awaiting review.
        application = StudentRegistrationRequest.objects.create(
            username="rejected_student_test",
            first_name="Alex",
            last_name="Student",
            email="rejected.student@example.com",
            password_hash=make_password("StudentPassword847!"),
        )

        # Reject the pending application.
        rejected_application = reject_student_registration(
            application_id=application.pk,
            reviewer=administrator,
        )

        self.assertEqual(
            rejected_application.pk,
            application.pk
        )

        # Verify the recorded decision.
        application.refresh_from_db()

        self.assertEqual(
            application.status,
            StudentRegistrationRequest.Status.REJECTED
        )
        self.assertEqual(
            application.reviewed_by,
            administrator
        )
        self.assertIsNotNone(application.reviewed_at)

        # Sensitive password material must be discarded.
        self.assertEqual(application.password_hash, "")

        # Rejection must never create a Django account.
        self.assertFalse(
            User.objects.filter(
                username="rejected_student_test"
            ).exists()
        )

    def test_regular_student_cannot_reject_registration(self):
        """
        A regular student must not reject registration
        applications, even through the service layer.
        """
        from django.contrib.auth.hashers import make_password
        from django.core.exceptions import PermissionDenied

        from .models import StudentRegistrationRequest
        from .registration_services import (
            reject_student_registration,
        )

        User = get_user_model()

        # Create an ordinary user without administrator rights.
        reviewer = User.objects.create_user(
            username="unauthorized_rejection_reviewer",
            password="SecurePassword847!"
        )

        # Create a pending student registration request.
        application = StudentRegistrationRequest.objects.create(
            username="protected_rejection_applicant",
            first_name="Alex",
            last_name="Student",
            email="protected.rejection@example.com",
            password_hash=make_password("StudentPassword847!"),
        )

        original_password_hash = application.password_hash

        # Unauthorized users must not reject applications.
        with self.assertRaises(PermissionDenied):
            reject_student_registration(
                application_id=application.pk,
                reviewer=reviewer,
            )

        application.refresh_from_db()

        # The registration must remain unchanged.
        self.assertEqual(
            application.status,
            StudentRegistrationRequest.Status.PENDING
        )

        self.assertIsNone(application.reviewed_by)
        self.assertIsNone(application.reviewed_at)

        # An unauthorized attempt must not erase the hash.
        self.assertEqual(
            application.password_hash,
            original_password_hash
        )

        # No Django user account should exist.
        self.assertFalse(
            User.objects.filter(
                username="protected_rejection_applicant"
            ).exists()
        )

    def test_registration_cannot_be_rejected_twice(self):
        """
        Prevent repeated rejection of an application
        and preserve the original review decision.
        """
        from django.contrib.auth.hashers import make_password

        from .models import (
            StudentRegistrationRequest,
            UserProfile,
        )
        from .registration_services import (
            RegistrationRejectionError,
            reject_student_registration,
        )

        User = get_user_model()

        # Create an authorized administrator.
        administrator = User.objects.create_user(
            username="repeat_rejection_admin",
            password="SecureAdminPassword847!"
        )

        UserProfile.objects.filter(
            user=administrator
        ).update(role=UserProfile.Role.ADMIN)

        # Create a pending registration application.
        application = StudentRegistrationRequest.objects.create(
            username="repeat_rejection_student",
            first_name="Alex",
            last_name="Student",
            email="repeat.rejection@example.com",
            password_hash=make_password("StudentPassword847!"),
        )

        # The first rejection should succeed.
        reject_student_registration(
            application_id=application.pk,
            reviewer=administrator,
        )

        application.refresh_from_db()
        original_reviewed_at = application.reviewed_at

        # A second rejection must be prevented.
        with self.assertRaises(RegistrationRejectionError):
            reject_student_registration(
                application_id=application.pk,
                reviewer=administrator,
            )

        application.refresh_from_db()

        # Preserve the original decision and reviewer.
        self.assertEqual(
            application.status,
            StudentRegistrationRequest.Status.REJECTED
        )

        self.assertEqual(
            application.reviewed_by,
            administrator
        )

        self.assertEqual(
            application.reviewed_at,
            original_reviewed_at
        )

        # The password hash must remain cleared.
        self.assertEqual(application.password_hash, "")

        # Rejection must never create a student account.
        self.assertFalse(
            User.objects.filter(
                username="repeat_rejection_student"
            ).exists()
        )

    def test_registration_approval_endpoint_requires_admin_and_post(self):
        """
        Only administrators may approve registrations,
        and approval must require an HTTP POST request.
        """
        from django.contrib.auth.hashers import make_password

        from .models import (
            StudentRegistrationRequest,
            UserProfile,
        )

        User = get_user_model()

        # Create a pending registration application.
        application = StudentRegistrationRequest.objects.create(
            username="endpoint_student_test",
            first_name="Alex",
            last_name="Student",
            email="endpoint.student@example.com",
            password_hash=make_password("StudentPassword847!"),
        )

        url = reverse(
            "registration_management:request_approve",
            args=[application.pk],
        )

        # Anonymous visitors must authenticate.
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

        # Ordinary students cannot approve applications.
        regular_user = User.objects.create_user(
            username="endpoint_regular_user",
            password="SecurePassword847!",
        )

        self.client.force_login(regular_user)

        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)

        # Create an authorized administrator.
        administrator = User.objects.create_user(
            username="endpoint_admin_test",
            password="SecureAdminPassword847!",
        )

        UserProfile.objects.filter(
            user=administrator
        ).update(role=UserProfile.Role.ADMIN)

        self.client.force_login(administrator)

        # Even administrators cannot approve using GET.
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

        # An authorized POST request should succeed.
        response = self.client.post(url)

        self.assertRedirects(
            response,
            reverse("registration_management:request_list"),
            fetch_redirect_response=False,
        )

        # Approval creates the student account.
        self.assertTrue(
            User.objects.filter(
                username="endpoint_student_test"
            ).exists()
        )

        application.refresh_from_db()

        self.assertEqual(
            application.status,
            StudentRegistrationRequest.Status.APPROVED,
        )

        self.assertEqual(
            application.reviewed_by,
            administrator,
        )

    def test_registration_rejection_endpoint_requires_admin_and_post(self):
        """
        Only administrators may reject registrations,
        and rejection must require an HTTP POST request.
        """
        from django.contrib.auth.hashers import make_password

        from .models import (
            StudentRegistrationRequest,
            UserProfile,
        )

        User = get_user_model()

        # Create an application awaiting review.
        application = StudentRegistrationRequest.objects.create(
            username="rejection_endpoint_student",
            first_name="Alex",
            last_name="Student",
            email="rejection.endpoint@example.com",
            password_hash=make_password("StudentPassword847!"),
        )

        url = reverse(
            "registration_management:request_reject",
            args=[application.pk],
        )

        # Anonymous visitors must authenticate.
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

        # Regular students cannot reject applications.
        regular_user = User.objects.create_user(
            username="rejection_endpoint_regular",
            password="SecurePassword847!",
        )

        self.client.force_login(regular_user)

        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)

        # Create an authorized administrator.
        administrator = User.objects.create_user(
            username="rejection_endpoint_admin",
            password="SecureAdminPassword847!",
        )

        UserProfile.objects.filter(
            user=administrator
        ).update(role=UserProfile.Role.ADMIN)

        self.client.force_login(administrator)

        # GET must not modify registration records.
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

        application.refresh_from_db()

        self.assertEqual(
            application.status,
            StudentRegistrationRequest.Status.PENDING,
        )

        # An authorized POST should reject the application.
        response = self.client.post(url)

        self.assertRedirects(
            response,
            reverse("registration_management:request_list"),
            fetch_redirect_response=False,
        )

        application.refresh_from_db()

        # Verify the rejection decision and audit record.
        self.assertEqual(
            application.status,
            StudentRegistrationRequest.Status.REJECTED,
        )

        self.assertEqual(
            application.reviewed_by,
            administrator,
        )

        self.assertIsNotNone(application.reviewed_at)

        # Sensitive password material must be discarded.
        self.assertEqual(application.password_hash, "")

        # Rejection must never create a student account.
        self.assertFalse(
            User.objects.filter(
                username="rejection_endpoint_student"
            ).exists()
        )

    def test_registration_review_endpoints_require_csrf(self):
        """
        Approval and rejection must reject POST requests
        without valid CSRF tokens, even from administrators.
        """
        from django.contrib.auth.hashers import make_password
        from django.test import Client

        from .models import (
            StudentRegistrationRequest,
            UserProfile,
        )

        User = get_user_model()

        # Create an authorized administrator.
        administrator = User.objects.create_user(
            username="csrf_review_admin",
            password="SecureAdminPassword847!",
        )

        UserProfile.objects.filter(
            user=administrator
        ).update(role=UserProfile.Role.ADMIN)

        # Create separate pending applications.
        approval_request = StudentRegistrationRequest.objects.create(
            username="csrf_approval_student",
            email="csrf.approval@example.com",
            password_hash=make_password("StudentPassword847!"),
        )

        rejection_request = StudentRegistrationRequest.objects.create(
            username="csrf_rejection_student",
            email="csrf.rejection@example.com",
            password_hash=make_password("StudentPassword847!"),
        )

        # Unlike Django's default test client,
        # this client enforces CSRF validation.
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(administrator)

        review_urls = [
            reverse(
                "registration_management:request_approve",
                args=[approval_request.pk],
            ),
            reverse(
                "registration_management:request_reject",
                args=[rejection_request.pk],
            ),
        ]

        # Neither action may proceed without a CSRF token.
        for url in review_urls:
            with self.subTest(url=url):
                response = csrf_client.post(url)

                self.assertEqual(response.status_code, 403)

        # Both applications must remain pending.
        approval_request.refresh_from_db()
        rejection_request.refresh_from_db()

        self.assertEqual(
            approval_request.status,
            StudentRegistrationRequest.Status.PENDING,
        )

        self.assertEqual(
            rejection_request.status,
            StudentRegistrationRequest.Status.PENDING,
        )

        # No account must be created.
        self.assertFalse(
            User.objects.filter(
                username="csrf_approval_student"
            ).exists()
        )

        # An unauthorized request must not erase
        # either application's stored password hash.
        self.assertTrue(approval_request.password_hash)
        self.assertTrue(rejection_request.password_hash)

    def test_registration_requires_first_and_last_name(self):
        """
        Registration must reject missing or whitespace-only
        first and last names without creating applications.
        """
        from .models import StudentRegistrationRequest

        registration_data = {
            "username": "required_name_student",
            "first_name": "Alex",
            "last_name": "Student",
            "email": "required.name@example.com",
            "password1": "StrongDemoPassword847!",
            "password2": "StrongDemoPassword847!",
        }

        # Each name field must reject empty and whitespace values.
        for field in ("first_name", "last_name"):
            for invalid_value in ("", "   "):
                with self.subTest(
                    field=field,
                    value=repr(invalid_value),
                ):
                    data = {
                        **registration_data,
                        field: invalid_value,
                    }

                    response = self.client.post(
                        reverse("student_register"),
                        data,
                    )

                    self.assertEqual(response.status_code, 200)

                    self.assertIn(
                        field,
                        response.context["form"].errors,
                    )

                    # Invalid applications must not be stored.
                    self.assertEqual(
                        StudentRegistrationRequest.objects.count(),
                        0,
                    )

                    # No Django user account may be created.
                    self.assertFalse(
                        get_user_model().objects.filter(
                            username="required_name_student",
                        ).exists()
                    )

    def test_regular_student_login_redirects_to_catalog(self):
        """
        Regular students must enter the public catalogue
        after login and remain excluded from the workspace.
        """
        User = get_user_model()

        # Create a regular student account.
        student = User.objects.create_user(
            username="student_portal_redirect_test",
            password="SecureStudentPassword847!",
            first_name="Alex",
            last_name="Student",
            email="portal.redirect@example.com",
        )

        # A normal login must redirect to the public portal.
        response = self.client.post(
            reverse("login"),
            {
                "username": student.username,
                "password": "SecureStudentPassword847!",
            },
        )

        self.assertRedirects(
            response,
            reverse("catalog:list"),
            fetch_redirect_response=False,
        )

        # Confirm that the student was authenticated.
        self.assertEqual(
            self.client.session.get("_auth_user_id"),
            str(student.pk),
        )

        # Public catalogue access must remain available.
        response = self.client.get(
            reverse("catalog:list")
        )
        self.assertEqual(response.status_code, 200)

        # Internal workspace access must remain forbidden.
        response = self.client.get("/projects/")
        self.assertEqual(response.status_code, 403)

class HomeWorkspaceAuthorizationTests(TestCase):
    """
    Verify that the Home dashboard respects workspace
    membership and project-level authorization.
    """

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        # Create the authorized workspace groups.
        cls.staff_group, _ = Group.objects.get_or_create(
            name="Career Services Staff"
        )

        cls.faculty_group, _ = Group.objects.get_or_create(
            name="Authorized Faculty"
        )

        cls.assistant_group, _ = Group.objects.get_or_create(
            name="Career Services Student Assistants"
        )

        # Create accounts representing different access levels.
        cls.staff = User.objects.create_user(
            username="home_staff_test"
        )

        cls.faculty = User.objects.create_user(
            username="home_faculty_test"
        )

        cls.assistant = User.objects.create_user(
            username="home_assistant_test"
        )

        cls.student = User.objects.create_user(
            username="home_student_test"
        )

        cls.admin = User.objects.create_user(
            username="home_admin_test"
        )

        # Assign explicit workspace membership.
        cls.staff.groups.add(cls.staff_group)
        cls.faculty.groups.add(cls.faculty_group)
        cls.assistant.groups.add(cls.assistant_group)

        # Administrator status alone must not grant
        # access to confidential workspace information.
        cls.admin.profile.role = UserProfile.Role.ADMIN
        cls.admin.profile.save(update_fields=["role"])

        today = timezone.localdate()

        # Create a project accessible to scoped members.
        cls.visible_project = Project.objects.create(
            owner=cls.staff,
            name="Authorized Career Project",
            status=Project.Status.ACTIVE,
            deadline=today + timedelta(days=4)
        )

        # Previous ownership must not replace an explicit grant.
        cls.hidden_project = Project.objects.create(
            owner=cls.assistant,
            name="Confidential Internal Project",
            status=Project.Status.ACTIVE,
            deadline=today - timedelta(days=1)
        )

        # Grant access to only the authorized project.
        ProjectAccess.objects.create(
            project=cls.visible_project,
            user=cls.faculty,
            access_level=ProjectAccess.AccessLevel.VIEWER
        )

        ProjectAccess.objects.create(
            project=cls.visible_project,
            user=cls.assistant,
            access_level=ProjectAccess.AccessLevel.CONTRIBUTOR
        )

        # Create tasks across both projects.
        cls.visible_task = Task.objects.create(
            project=cls.visible_project,
            name="Authorized Career Task",
            due_date=today + timedelta(days=1)
        )

        cls.visible_overdue_task = Task.objects.create(
            project=cls.visible_project,
            name="Authorized Overdue Task",
            due_date=today - timedelta(days=1)
        )

        cls.hidden_task = Task.objects.create(
            project=cls.hidden_project,
            name="Confidential Internal Task",
            due_date=today
        )

        cls.hidden_overdue_task = Task.objects.create(
            project=cls.hidden_project,
            name="Confidential Overdue Task",
            due_date=today - timedelta(days=2)
        )

    def test_anonymous_user_cannot_access_home(self):
        # Home must remain protected by authentication.
        url = reverse("core:home")

        response = self.client.get(url)

        self.assertRedirects(
            response,
            f"{resolve_url(settings.LOGIN_URL)}?next={url}",
            fetch_redirect_response=False
        )

    def test_regular_student_cannot_access_home_even_if_owner(self):
        # Simulate ownership remaining after authorization changes.
        self.hidden_project.owner = self.student
        self.hidden_project.save(update_fields=["owner"])

        self.client.force_login(self.student)

        response = self.client.get(reverse("core:home"))

        self.assertRedirects(
            response,
            reverse("catalog:list"),
            fetch_redirect_response=False
        )

    def test_administrator_without_membership_cannot_access_home(self):
        # Administrative roles and workspace membership are separate.
        self.client.force_login(self.admin)

        response = self.client.get(reverse("core:home"))

        self.assertRedirects(
            response,
            reverse("catalog:list"),
            fetch_redirect_response=False
        )

    def test_staff_can_view_all_workspace_projects(self):
        # Career Services staff have office-wide visibility.
        self.client.force_login(self.staff)

        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_projects"], 2)
        self.assertEqual(response.context["active_projects"], 2)
        self.assertEqual(response.context["total_tasks"], 4)

        self.assertContains(response, self.visible_task.name)
        self.assertContains(response, self.hidden_task.name)

    def test_scoped_members_only_see_explicitly_granted_projects(self):
        # Faculty and assistants must receive only assigned data.
        for user in (self.faculty, self.assistant):
            with self.subTest(username=user.username):
                self.client.force_login(user)

                response = self.client.get(reverse("core:home"))

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["total_projects"], 1)
                self.assertEqual(response.context["active_projects"], 1)
                self.assertEqual(response.context["total_tasks"], 2)

                self.assertEqual(
                    response.context["featured_project"],
                    self.visible_project
                )

                self.assertEqual(
                    response.context["featured_project_task_count"],
                    2
                )

                self.assertEqual(
                    {
                        task.pk
                        for task in response.context["recent_tasks"]
                    },
                    {
                        self.visible_task.pk,
                        self.visible_overdue_task.pk
                    }
                )

                self.assertEqual(
                    list(response.context["upcoming_task_deadlines"]),
                    [self.visible_task]
                )

                self.assertEqual(
                    list(response.context["overdue_tasks"]),
                    [self.visible_overdue_task]
                )

                self.assertEqual(
                    list(response.context["upcoming_project_deadlines"]),
                    [self.visible_project]
                )

                self.assertEqual(
                    list(response.context["overdue_projects"]),
                    []
                )

                self.assertEqual(
                    response.context["next_deadline"]["project"],
                    self.visible_project
                )

                self.assertContains(
                    response,
                    self.visible_project.name
                )

                self.assertNotContains(
                    response,
                    self.hidden_project.name
                )

                self.assertNotContains(
                    response,
                    self.hidden_task.name
                )

                self.assertNotContains(
                    response,
                    self.hidden_overdue_task.name
                )

    def test_revoked_membership_blocks_home_immediately(self):
        # A previous project grant must not override revoked
        # workspace membership during an authenticated session.
        self.client.force_login(self.assistant)

        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)

        self.assistant.groups.remove(self.assistant_group)

        response = self.client.get(reverse("core:home"))

        self.assertRedirects(
            response,
            reverse("catalog:list"),
            fetch_redirect_response=False
        )

    def test_revoked_project_grant_removes_dashboard_data(self):
        # Workspace membership alone does not grant project access.
        self.client.force_login(self.assistant)

        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.context["total_projects"], 1)

        ProjectAccess.objects.filter(
            project=self.visible_project,
            user=self.assistant
        ).delete()

        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_projects"], 0)
        self.assertEqual(response.context["total_tasks"], 0)
        self.assertIsNone(response.context["featured_project"])
        self.assertIsNone(response.context["next_deadline"])

        self.assertEqual(
            list(response.context["recent_tasks"]),
            []
        )

        self.assertNotContains(
            response,
            self.visible_project.name
        )

        self.assertNotContains(
            response,
            self.hidden_project.name
        )

    def test_navigation_respects_workspace_membership(self):
        # Home and Schedule links must reflect authorization.
        scenarios = (
            (self.staff, True),
            (self.faculty, True),
            (self.assistant, True),
            (self.student, False),
            (self.admin, False),
        )

        routes = (
            "core:home",
            "projects:project_list",
            "projects:schedule",
            "projects:analytics",
        )

        for user, authorized in scenarios:
            with self.subTest(username=user.username):
                self.client.force_login(user)

                response = self.client.get(
                    reverse("catalog:list")
                )

                self.assertEqual(response.status_code, 200)

                for route in routes:
                    link = f'href="{reverse(route)}"'

                    if authorized:
                        self.assertContains(response, link)
                    else:
                        self.assertNotContains(response, link)

    def test_staff_empty_state_allows_project_creation(self):
        # Remove projects from the isolated test database.
        Project.objects.all().delete()

        self.client.force_login(self.staff)

        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_projects"], 0)
        self.assertEqual(response.context["total_tasks"], 0)

        self.assertContains(
            response,
            "Your next project starts here."
        )

        self.assertContains(
            response,
            "Create a project"
        )

        self.assertContains(
            response,
            f'href="{reverse("projects:project_create")}"'
        )

        self.assertNotContains(
            response,
            "No assigned projects yet."
        )

    def test_scoped_empty_state_hides_project_creation(self):
        # Remove explicit project grants while preserving
        # faculty and student assistant workspace membership.
        ProjectAccess.objects.filter(
            user__in=[self.faculty, self.assistant]
        ).delete()

        for user in (self.faculty, self.assistant):
            with self.subTest(username=user.username):
                self.client.force_login(user)

                response = self.client.get(
                    reverse("core:home")
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.context["total_projects"], 0
                )
                self.assertEqual(
                    response.context["total_tasks"], 0
                )

                self.assertContains(
                    response,
                    "No assigned projects yet."
                )

                self.assertContains(
                    response,
                    "View My Projects"
                )

                self.assertContains(
                    response,
                    f'href="{reverse("projects:project_list")}"'
                )

                self.assertNotContains(
                    response,
                    f'href="{reverse("projects:project_create")}"'
                )

                self.assertNotContains(
                    response,
                    "Create a project"
                )

                self.assertNotContains(
                    response,
                    self.hidden_project.name
                )

class UserManagementAccessTests(TestCase):
    """
    Verify administrator-only access to the custom
    user management directory.
    """

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        # Create an administrator without workspace membership.
        cls.admin = User.objects.create_user(
            username="directory_admin",
            email="directory.admin@example.com"
        )

        cls.admin.profile.role = UserProfile.Role.ADMIN
        cls.admin.profile.save(update_fields=["role"])

        # Create a regular student account.
        cls.student = User.objects.create_user(
            username="directory_student",
            first_name="Directory",
            last_name="Student",
            email="directory.student@example.com"
        )

        # Create a privileged application user.
        cls.power_user = User.objects.create_user(
            username="directory_power_user"
        )

        cls.power_user.profile.role = UserProfile.Role.POWER
        cls.power_user.profile.save(update_fields=["role"])

        # Workspace membership must not grant administration.
        cls.staff_group, _ = Group.objects.get_or_create(
            name="Career Services Staff"
        )

        cls.power_user.groups.add(cls.staff_group)

    def test_anonymous_user_redirected_to_login(self):
        # Anonymous visitors cannot view account information.
        url = reverse("user_management:user_list")

        response = self.client.get(url)

        self.assertRedirects(
            response,
            f"{resolve_url(settings.LOGIN_URL)}?next={url}",
            fetch_redirect_response=False
        )

    def test_regular_user_cannot_access_directory(self):
        # Regular accounts must receive HTTP 403.
        self.client.force_login(self.student)

        response = self.client.get(
            reverse("user_management:user_list")
        )

        self.assertEqual(response.status_code, 403)

    def test_power_user_cannot_access_directory(self):
        # Privileged users and workspace staff are not
        # automatically entitled to administrative access.
        self.client.force_login(self.power_user)

        response = self.client.get(
            reverse("user_management:user_list")
        )

        self.assertEqual(response.status_code, 403)

    def test_administrator_can_view_registered_accounts(self):
        # Administration does not require workspace membership.
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("user_management:user_list")
        )

        self.assertEqual(response.status_code, 200)

        self.assertTemplateUsed(
            response,
            "user_management/user_list.html"
        )

        self.assertEqual(
            response.context["total_users"],
            3
        )

        self.assertContains(
            response,
            self.student.username
        )

        self.assertContains(
            response,
            self.student.email
        )

    def test_directory_rejects_post_requests(self):
        # The read-only directory accepts safe HTTP methods only.
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("user_management:user_list")
        )

        self.assertEqual(response.status_code, 405)

    def test_revoked_admin_role_blocks_existing_session(self):
        # Role revocation must apply to authenticated sessions.
        self.client.force_login(self.admin)

        url = reverse("user_management:user_list")

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.admin.profile.role = UserProfile.Role.REGULAR
        self.admin.profile.save(update_fields=["role"])

        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

    def test_missing_profile_denies_administrative_access(self):
        # Missing profiles must never grant administrative access.
        self.client.force_login(self.admin)

        self.admin.profile.delete()

        response = self.client.get(
            reverse("user_management:user_list")
        )

        self.assertEqual(response.status_code, 403)

    def test_deactivated_administrator_loses_access(self):
        # Deactivation must invalidate access through an
        # existing authenticated session.
        self.client.force_login(self.admin)

        url = reverse("user_management:user_list")

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.admin.is_active = False
        self.admin.save(update_fields=["is_active"])

        response = self.client.get(url)

        self.assertRedirects(
            response,
            f"{resolve_url(settings.LOGIN_URL)}?next={url}",
            fetch_redirect_response=False
        )

    def assert_directory_results(self, filters, expected_users):
        """
        Verify the exact accounts returned by
        the user directory's filtering functionality.
        """

        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("user_management:user_list"),
            data=filters
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.context["total_users"],
            len(expected_users)
        )

        actual_ids = {
            account.pk
            for account in response.context["users"]
        }

        expected_ids = {
            account.pk
            for account in expected_users
        }

        self.assertEqual(actual_ids, expected_ids)

        return response

    def test_directory_search_by_account_identity(self):
        # Search must support usernames, names and email addresses.
        search_queries = (
            "directory_student",
            "Directory Student",
            "DIRECTORY STUDENT",
            "Student",
            "directory.student@example.com",
        )

        for query in search_queries:
            with self.subTest(query=query):
                self.assert_directory_results(
                    {"q": query},
                    [self.student]
                )

    def test_directory_filters_by_application_role(self):
        # Every supported application role must be filterable.
        scenarios = (
            ("admin", [self.admin]),
            ("power", [self.power_user]),
            ("regular", [self.student]),
        )

        for role, expected_users in scenarios:
            with self.subTest(role=role):
                self.assert_directory_results(
                    {"role": role},
                    expected_users
                )

    def test_directory_filters_by_account_status(self):
        # Active and inactive accounts must be distinguishable.
        self.student.is_active = False
        self.student.save(update_fields=["is_active"])

        self.assert_directory_results(
            {"status": "active"},
            [self.admin, self.power_user]
        )

        self.assert_directory_results(
            {"status": "inactive"},
            [self.student]
        )

    def test_directory_combines_search_role_and_status(self):
        # All submitted filters must constrain the results.
        self.assert_directory_results(
            {
                "q": "directory",
                "role": "regular",
                "status": "active"
            },
            [self.student]
        )

        self.assert_directory_results(
            {
                "q": "directory",
                "role": "regular",
                "status": "inactive"
            },
            []
        )

    def test_directory_rejects_invalid_filter_parameters(self):
        # Invalid parameters must not broaden directory results.
        scenarios = (
            {"role": "unsupported"},
            {"status": "unsupported"},
            {"q": "a" * 151},
        )

        for filters in scenarios:
            with self.subTest(filters=filters):
                response = self.assert_directory_results(
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

    def test_directory_displays_matching_empty_state(self):
        # Valid searches without results require clear feedback.
        response = self.assert_directory_results(
            {"q": "nonexistent-account"},
            []
        )

        self.assertContains(
            response,
            "No matching accounts"
        )

        self.assertContains(
            response,
            "Clear All Filters"
        )

        self.assertNotContains(
            response,
            "No registered users found"
        )

    def test_directory_preserves_registered_account_count(self):
        # Filtered results must not alter the total account count.
        response = self.assert_directory_results(
            {"role": "admin"},
            [self.admin]
        )

        self.assertEqual(
            response.context["registered_users_count"],
            3
        )

        self.assertEqual(
            response.context["total_users"],
            1
        )

        # Clearing filters restores all registered accounts.
        response = self.assert_directory_results(
            {},
            [self.admin, self.student, self.power_user]
        )

        self.assertEqual(
            response.context["registered_users_count"],
            3
        )

    def test_directory_pagination_preserves_all_filters(self):
        # Create enough matching accounts for multiple pages.
        User = get_user_model()

        for index in range(12):
            account = User.objects.create_user(
                username=f"directory_batch_{index:02d}",
                first_name="Batch & Review",
                last_name=f"Student {index:02d}",
                email=f"batch{index:02d}@example.com"
            )

            account.profile.role = UserProfile.Role.REGULAR
            account.profile.save(update_fields=["role"])

        self.client.force_login(self.admin)

        filters = {
            "q": "Batch & Review",
            "role": "regular",
            "status": "active"
        }

        expected_query = (
            "q=Batch+%26+Review"
            "&amp;role=regular"
            "&amp;status=active"
        )

        # Verify the first page and its Next link.
        response = self.client.get(
            reverse("user_management:user_list"),
            data=filters
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_users"], 12)
        self.assertEqual(
            response.context["registered_users_count"], 15
        )
        self.assertEqual(len(response.context["users"]), 10)

        self.assertContains(
            response,
            f"?page=2&amp;{expected_query}"
        )

        # Verify the second page and its Previous link.
        response = self.client.get(
            reverse("user_management:user_list"),
            data={**filters, "page": "2"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_users"], 12)
        self.assertEqual(
            response.context["page_obj"].number, 2
        )
        self.assertEqual(len(response.context["users"]), 2)

        self.assertContains(
            response,
            "directory_batch_10"
        )

        self.assertContains(
            response,
            "directory_batch_11"
        )

        self.assertContains(
            response,
            f"?page=1&amp;{expected_query}"
        )

    def test_administrator_can_view_user_details(self):
        # Administrators may inspect registered accounts.
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse(
                "user_management:user_detail",
                kwargs={"pk": self.student.pk}
            )
        )

        self.assertEqual(response.status_code, 200)

        self.assertTemplateUsed(
            response,
            "user_management/user_detail.html"
        )

        self.assertEqual(
            response.context["account"],
            self.student
        )

        self.assertContains(response, self.student.username)
        self.assertContains(response, self.student.email)
        self.assertContains(response, "Personal Information")
        self.assertContains(response, "Access &amp; Permissions")
        self.assertContains(response, "Account History")

    def test_administrator_can_view_own_account(self):
        # Identify the administrator's own account correctly.
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse(
                "user_management:user_detail",
                kwargs={"pk": self.admin.pk}
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_current_account"])
        self.assertContains(response, "Your Account")

    def test_other_account_is_not_marked_as_current(self):
        # Other accounts must not display the current-user indicator.
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse(
                "user_management:user_detail",
                kwargs={"pk": self.student.pk}
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["is_current_account"])

    def test_anonymous_user_cannot_access_user_details(self):
        # Personal account information requires authentication.
        url = reverse(
            "user_management:user_detail",
            kwargs={"pk": self.student.pk}
        )

        response = self.client.get(url)

        self.assertRedirects(
            response,
            f"{resolve_url(settings.LOGIN_URL)}?next={url}",
            fetch_redirect_response=False
        )

    def test_regular_user_cannot_access_user_details(self):
        # Changing the requested primary key must not
        # bypass administrator-only authorization.
        self.client.force_login(self.student)

        for account in (self.student, self.admin, self.power_user):

            with self.subTest(account=account.username):

                response = self.client.get(
                    reverse(
                        "user_management:user_detail",
                        kwargs={"pk": account.pk}
                    )
                )

                self.assertEqual(response.status_code, 403)

    def test_power_user_cannot_access_user_details(self):
        # Workspace membership does not grant account administration.
        self.client.force_login(self.power_user)

        response = self.client.get(
            reverse(
                "user_management:user_detail",
                kwargs={"pk": self.student.pk}
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_nonexistent_account_returns_404(self):
        # Requests for nonexistent accounts must fail safely.
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse(
                "user_management:user_detail",
                kwargs={"pk": 999999}
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_user_details_rejects_post_requests(self):
        # The account details endpoint is strictly read-only.
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse(
                "user_management:user_detail",
                kwargs={"pk": self.student.pk}
            ),
            data={"role": "admin"}
        )

        self.assertEqual(response.status_code, 405)

        self.student.profile.refresh_from_db()

        self.assertEqual(
            self.student.profile.role,
            UserProfile.Role.REGULAR
        )

    def test_user_details_never_exposes_password(self):
        # Neither raw passwords nor password hashes may
        # appear in the rendered administrative interface.
        raw_password = "PrivateTestPassword123!"

        self.student.set_password(raw_password)
        self.student.save(update_fields=["password"])

        self.client.force_login(self.admin)

        response = self.client.get(
            reverse(
                "user_management:user_detail",
                kwargs={"pk": self.student.pk}
            )
        )

        self.assertEqual(response.status_code, 200)

        self.assertNotContains(response, raw_password)

        self.assertNotContains(
            response,
            self.student.password
        )

    def test_revoked_administrator_cannot_view_user_details(self):
        # Administrative role revocation must apply immediately.
        self.client.force_login(self.admin)

        url = reverse(
            "user_management:user_detail",
            kwargs={"pk": self.student.pk}
        )

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.admin.profile.role = UserProfile.Role.REGULAR
        self.admin.profile.save(update_fields=["role"])

        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

    def get_valid_creation_data(self, **overrides):
        """
        Return valid account creation data that individual
        tests can override to exercise specific scenarios.
        """

        data = {
            "username": "managed_new_user",
            "first_name": "Managed",
            "last_name": "Account",
            "email": "managed.new@example.com",
            "password1": "River!Copper72Mountain",
            "password2": "River!Copper72Mountain",
        }

        data.update(overrides)

        return data

    def assert_creation_rejected(self, data, error_field):
        """
        Verify that invalid account creation attempts
        return validation errors without creating accounts.
        """

        User = get_user_model()

        self.client.force_login(self.admin)

        original_count = User.objects.count()

        response = self.client.post(
            reverse("user_management:user_create"),
            data=data
        )

        self.assertEqual(response.status_code, 200)

        self.assertIn(
            error_field,
            response.context["form"].errors
        )

        self.assertEqual(
            User.objects.count(),
            original_count
        )

        return response

    def test_administrator_can_access_creation_form(self):
        # Authorized administrators may open the creation form.
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("user_management:user_create")
        )

        self.assertEqual(response.status_code, 200)

        self.assertTemplateUsed(
            response,
            "user_management/user_form.html"
        )

        self.assertEqual(
            list(response.context["form"].fields),
            [
                "username",
                "first_name",
                "last_name",
                "email",
                "password1",
                "password2",
            ]
        )

        self.assertContains(
            response,
            "csrfmiddlewaretoken"
        )

    def test_administrator_can_create_valid_account(self):
        # Valid submissions must create an active,
        # securely authenticated regular account.
        User = get_user_model()

        self.client.force_login(self.admin)

        data = self.get_valid_creation_data(
            email="MANAGED.NEW@EXAMPLE.COM"
        )

        original_count = User.objects.count()

        response = self.client.post(
            reverse("user_management:user_create"),
            data=data
        )

        self.assertEqual(response.status_code, 302)

        account = User.objects.get(
            username=data["username"]
        )

        self.assertEqual(
            User.objects.count(),
            original_count + 1
        )

        self.assertEqual(account.first_name, "Managed")
        self.assertEqual(account.last_name, "Account")

        self.assertEqual(
            account.email,
            "managed.new@example.com"
        )

        # Verify password hashing and authentication.
        self.assertNotEqual(
            account.password,
            data["password1"]
        )

        self.assertTrue(
            account.check_password(data["password1"])
        )

        self.assertTrue(account.is_active)
        self.assertFalse(account.is_staff)
        self.assertFalse(account.is_superuser)

        self.assertEqual(
            account.profile.role,
            UserProfile.Role.REGULAR
        )

        self.assertFalse(account.groups.exists())
        self.assertFalse(account.user_permissions.exists())

        self.assertRedirects(
            response,
            reverse(
                "user_management:user_detail",
                kwargs={"pk": account.pk}
            )
        )

    def test_creation_prevents_privilege_escalation(self):
        # Manipulated POST parameters must never grant
        # additional application or Django privileges.
        User = get_user_model()

        workspace_group = self.power_user.groups.first()

        self.assertIsNotNone(workspace_group)

        self.client.force_login(self.admin)

        data = self.get_valid_creation_data(
            role="admin",
            is_staff="true",
            is_superuser="true",
            groups=[workspace_group.pk],
            is_active="false",
        )

        response = self.client.post(
            reverse("user_management:user_create"),
            data=data
        )

        self.assertEqual(response.status_code, 302)

        account = User.objects.get(
            username=data["username"]
        )

        self.assertEqual(
            account.profile.role,
            UserProfile.Role.REGULAR
        )

        self.assertFalse(account.is_staff)
        self.assertFalse(account.is_superuser)
        self.assertFalse(account.groups.exists())
        self.assertFalse(account.user_permissions.exists())

        # Account activation follows the server-side policy.
        self.assertTrue(account.is_active)

    def test_anonymous_user_cannot_create_accounts(self):
        # Guests must not access the form or create accounts.
        User = get_user_model()

        url = reverse("user_management:user_create")

        original_count = User.objects.count()

        responses = (
            self.client.get(url),
            self.client.post(
                url,
                data=self.get_valid_creation_data()
            ),
        )

        for response in responses:
            self.assertRedirects(
                response,
                f"{resolve_url(settings.LOGIN_URL)}?next={url}",
                fetch_redirect_response=False
            )

        self.assertEqual(
            User.objects.count(),
            original_count
        )

    def test_non_administrators_cannot_create_accounts(self):
        # Neither regular nor privileged workspace users
        # may access the custom administration endpoint.
        User = get_user_model()

        url = reverse("user_management:user_create")

        original_count = User.objects.count()

        for account in (self.student, self.power_user):

            with self.subTest(account=account.username):

                self.client.force_login(account)

                response = self.client.get(url)

                self.assertEqual(response.status_code, 403)

                response = self.client.post(
                    url,
                    data=self.get_valid_creation_data()
                )

                self.assertEqual(response.status_code, 403)

        self.assertEqual(
            User.objects.count(),
            original_count
        )

    def test_creation_rejects_unsupported_http_methods(self):
        # Only GET, HEAD and POST are supported.
        self.client.force_login(self.admin)

        url = reverse("user_management:user_create")

        for method in ("put", "patch", "delete"):

            with self.subTest(method=method):

                response = getattr(self.client, method)(url)

                self.assertEqual(response.status_code, 405)

    def test_creation_requires_all_account_fields(self):
        # Required fields must be validated server-side.
        required_fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "password1",
            "password2",
        )

        for field in required_fields:

            with self.subTest(field=field):

                data = self.get_valid_creation_data()

                data.pop(field)

                self.assert_creation_rejected(
                    data,
                    field
                )

    def test_creation_rejects_invalid_email(self):
        # Invalid email formats must not create accounts.
        self.assert_creation_rejected(
            self.get_valid_creation_data(
                email="invalid-email-address"
            ),
            "email"
        )

    def test_creation_rejects_duplicate_username(self):
        # An existing username cannot be registered again.
        self.assert_creation_rejected(
            self.get_valid_creation_data(
                username=self.student.username
            ),
            "username"
        )

    def test_creation_rejects_duplicate_email(self):
        # Email uniqueness validation is case-insensitive.
        self.assert_creation_rejected(
            self.get_valid_creation_data(
                email=self.student.email.upper()
            ),
            "email"
        )

    def test_creation_rejects_weak_passwords(self):
        # Django's configured password validators
        # must reject insecure credentials.
        weak_passwords = (
            "123",
            "password",
            "1234567890123456",
        )

        for password in weak_passwords:

            with self.subTest(password=password):

                data = self.get_valid_creation_data(
                    password1=password,
                    password2=password
                )

                self.assert_creation_rejected(
                    data,
                    "password2"
                )

    def test_creation_rejects_mismatched_passwords(self):
        # Password confirmation must match exactly.
        data = self.get_valid_creation_data(
            password2="Different!Password83"
        )

        response = self.assert_creation_rejected(
            data,
            "password2"
        )

        # Invalid submissions must not redisplay passwords.
        self.assertNotContains(
            response,
            data["password1"]
        )

        self.assertNotContains(
            response,
            data["password2"]
        )

    def test_creation_requires_csrf_token(self):
        # Explicitly enable CSRF enforcement because
        # Django's ordinary test client disables it.
        from django.test import Client

        User = get_user_model()

        csrf_client = Client(enforce_csrf_checks=True)

        csrf_client.force_login(self.admin)

        original_count = User.objects.count()

        response = csrf_client.post(
            reverse("user_management:user_create"),
            data=self.get_valid_creation_data()
        )

        self.assertEqual(response.status_code, 403)

        self.assertEqual(
            User.objects.count(),
            original_count
        )

    def create_registration_request(self, **overrides):
        """
        Create an isolated student registration request
        for account administration compatibility testing.
        """

        from django.contrib.auth.hashers import make_password
        from .models import StudentRegistrationRequest

        data = {
            "username": "pending_student",
            "first_name": "Pending",
            "last_name": "Student",
            "email": "pending.student@example.com",
            "password_hash": make_password(
                "Forest!Silver84Ocean"
            ),
            "status": StudentRegistrationRequest.Status.PENDING,
        }

        data.update(overrides)

        return StudentRegistrationRequest.objects.create(
            **data
        )

    def test_creation_rejects_pending_registration_username(self):
        # Pending applications reserve their requested usernames.
        registration = self.create_registration_request()

        self.assert_creation_rejected(
            self.get_valid_creation_data(
                username=registration.username
            ),
            "username"
        )

        registration.refresh_from_db()

        self.assertEqual(registration.status, "pending")

    def test_creation_rejects_pending_registration_email(self):
        # Pending applications reserve their email addresses.
        registration = self.create_registration_request()

        self.assert_creation_rejected(
            self.get_valid_creation_data(
                email=registration.email
            ),
            "email"
        )

        registration.refresh_from_db()

        self.assertEqual(registration.status, "pending")

    def test_pending_registration_username_is_case_insensitive(self):
        # Changing username casing must not bypass validation.
        registration = self.create_registration_request()

        self.assert_creation_rejected(
            self.get_valid_creation_data(
                username=registration.username.upper()
            ),
            "username"
        )

    def test_pending_registration_email_is_case_insensitive(self):
        # Changing email casing must not bypass validation.
        registration = self.create_registration_request()

        self.assert_creation_rejected(
            self.get_valid_creation_data(
                email=registration.email.upper()
            ),
            "email"
        )

    def test_creation_rejects_multiple_registration_conflicts(self):
        # Both conflicting fields must report validation errors.
        registration = self.create_registration_request()

        response = self.assert_creation_rejected(
            self.get_valid_creation_data(
                username=registration.username,
                email=registration.email
            ),
            "username"
        )

        self.assertIn(
            "email",
            response.context["form"].errors
        )

    def test_rejected_registration_does_not_block_creation(self):
        # Reviewed and rejected applications no longer
        # reserve their requested usernames or emails.
        from django.utils import timezone
        from .models import StudentRegistrationRequest

        User = get_user_model()

        registration = self.create_registration_request(
            status=StudentRegistrationRequest.Status.REJECTED,
            password_hash="",
            reviewed_by=self.admin,
            reviewed_at=timezone.now()
        )

        self.client.force_login(self.admin)

        original_count = User.objects.count()

        response = self.client.post(
            reverse("user_management:user_create"),
            data=self.get_valid_creation_data(
                username=registration.username,
                email=registration.email
            )
        )

        self.assertEqual(response.status_code, 302)

        self.assertEqual(
            User.objects.count(),
            original_count + 1
        )

        account = User.objects.get(
            username=registration.username
        )

        self.assertEqual(
            account.email,
            registration.email
        )

        # Preserve the reviewed registration history.
        registration.refresh_from_db()

        self.assertEqual(
            registration.status,
            StudentRegistrationRequest.Status.REJECTED
        )

        self.assertEqual(
            registration.reviewed_by,
            self.admin
        )

        self.assertEqual(registration.password_hash, "")

    def test_approved_registration_history_does_not_block_creation(self):
        # Historical approved applications do not reserve
        # identifiers when no corresponding account exists.
        from django.utils import timezone
        from .models import StudentRegistrationRequest

        User = get_user_model()

        registration = self.create_registration_request(
            status=StudentRegistrationRequest.Status.APPROVED,
            password_hash="",
            reviewed_by=self.admin,
            reviewed_at=timezone.now()
        )

        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("user_management:user_create"),
            data=self.get_valid_creation_data(
                username=registration.username,
                email=registration.email
            )
        )

        self.assertEqual(response.status_code, 302)

        self.assertTrue(
            User.objects.filter(
                username=registration.username,
                email=registration.email
            ).exists()
        )

        # Historical approval records must remain unchanged.
        registration.refresh_from_db()

        self.assertEqual(
            registration.status,
            StudentRegistrationRequest.Status.APPROVED
        )

    def test_unrelated_pending_registration_allows_creation(self):
        # Unrelated pending applications must not prevent
        # legitimate administrative account creation.
        from .models import StudentRegistrationRequest

        User = get_user_model()

        registration = self.create_registration_request()

        original_password_hash = registration.password_hash

        self.client.force_login(self.admin)

        data = self.get_valid_creation_data()

        original_count = User.objects.count()

        response = self.client.post(
            reverse("user_management:user_create"),
            data=data
        )

        self.assertEqual(response.status_code, 302)

        self.assertEqual(
            User.objects.count(),
            original_count + 1
        )

        self.assertTrue(
            User.objects.filter(
                username=data["username"]
            ).exists()
        )

        # Direct account creation must not modify
        # unrelated registration requests.
        registration.refresh_from_db()

        self.assertEqual(
            registration.status,
            StudentRegistrationRequest.Status.PENDING
        )

        self.assertEqual(
            registration.password_hash,
            original_password_hash
        )

        self.assertIsNone(registration.reviewed_by)
        self.assertIsNone(registration.reviewed_at)

class AccountIdentityTransactionTests(TestCase):
    """
    Verify the shared account identity transaction
    mechanism independently of administrative views.
    """

    def setUp(self):
        # Ensure a synchronization record is available
        # regardless of previous test database resets.
        from .models import AccountIdentityLock

        AccountIdentityLock.objects.get_or_create(
            pk=1,
            defaults={"revision": 0}
        )

    def test_identity_transaction_increments_revision(self):
        # Every protected operation must update the
        # shared synchronization record.
        from .account_identity import account_identity_transaction
        from .models import AccountIdentityLock

        original_revision = (
            AccountIdentityLock.objects.get(pk=1).revision
        )

        with account_identity_transaction():

            current_revision = (
                AccountIdentityLock.objects.get(pk=1).revision
            )

            self.assertEqual(
                current_revision,
                original_revision + 1
            )

        self.assertEqual(
            AccountIdentityLock.objects.get(pk=1).revision,
            original_revision + 1
        )

    def test_identity_transaction_reuses_singleton(self):
        # Consecutive operations must reuse the same row.
        from .account_identity import account_identity_transaction
        from .models import AccountIdentityLock

        original_revision = (
            AccountIdentityLock.objects.get(pk=1).revision
        )

        for _ in range(3):

            with account_identity_transaction():
                pass

        self.assertEqual(
            AccountIdentityLock.objects.count(),
            1
        )

        self.assertEqual(
            AccountIdentityLock.objects.get(pk=1).revision,
            original_revision + 3
        )

    def test_identity_transaction_restores_missing_record(self):
        # Recover safely after a database reset removes
        # the synchronization record.
        from .account_identity import account_identity_transaction
        from .models import AccountIdentityLock

        AccountIdentityLock.objects.all().delete()

        self.assertFalse(
            AccountIdentityLock.objects.exists()
        )

        with account_identity_transaction():

            self.assertEqual(
                AccountIdentityLock.objects.count(),
                1
            )

        lock = AccountIdentityLock.objects.get(pk=1)

        self.assertEqual(lock.revision, 1)

    def test_identity_transaction_rolls_back_on_failure(self):
        # Failed operations must roll back both account
        # creation and the synchronization revision.
        from .account_identity import account_identity_transaction
        from .models import AccountIdentityLock

        User = get_user_model()

        original_revision = (
            AccountIdentityLock.objects.get(pk=1).revision
        )

        original_user_count = User.objects.count()

        with self.assertRaises(RuntimeError):

            with account_identity_transaction():

                User.objects.create_user(
                    username="rollback_identity_test",
                    email="rollback@example.com",
                    password="Forest!Silver84Ocean"
                )

                # Simulate a failure after account creation.
                raise RuntimeError(
                    "Simulated account transaction failure."
                )

        self.assertEqual(
            User.objects.count(),
            original_user_count
        )

        self.assertFalse(
            User.objects.filter(
                username="rollback_identity_test"
            ).exists()
        )

        self.assertEqual(
            AccountIdentityLock.objects.get(pk=1).revision,
            original_revision
        )