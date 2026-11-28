from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import resolve_url
from django.test import RequestFactory
from datetime import timedelta
from django.test import TransactionTestCase
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

    def assert_identity_contention_handled(
        self,
        *,
        url,
        data,
        redirect_url,
        expected_message
    ):
        """
        Simulate database lock acquisition failure
        and verify controlled application feedback.

        No account or registration information may
        change when the transaction cannot proceed.
        """

        from unittest.mock import patch

        from django.contrib.messages import get_messages
        from django.db import OperationalError

        from .models import (
            AccountIdentityLock,
            StudentRegistrationRequest,
        )

        User = get_user_model()

        # Capture the database state before submission.
        original_user_count = User.objects.count()

        original_registrations = list(
            StudentRegistrationRequest.objects
            .order_by("pk")
            .values()
        )

        original_revision = (
            AccountIdentityLock.objects.get(pk=1).revision
        )

        # Simulate contention during acquisition of
        # the shared account identity lock.
        with patch(
            "core.account_identity."
            "AccountIdentityLock.objects.filter",
            side_effect=OperationalError(
                "database is locked"
            )
        ) as lock_query:

            response = self.client.post(
                url,
                data=data
            )

        lock_query.assert_called_once_with(pk=1)

        # Verify that the request fails gracefully.
        self.assertRedirects(
            response,
            redirect_url,
            fetch_redirect_response=False
        )

        feedback = [
            str(message)
            for message in get_messages(
                response.wsgi_request
            )
        ]

        self.assertTrue(
            any(
                expected_message in message
                for message in feedback
            )
        )

        # Internal database errors must not be disclosed.
        self.assertFalse(
            any(
                "database is locked" in message.lower()
                for message in feedback
            )
        )

        # Verify that no account data was created.
        self.assertEqual(
            User.objects.count(),
            original_user_count
        )

        # Existing registration records must be preserved.
        self.assertEqual(
            list(
                StudentRegistrationRequest.objects
                .order_by("pk")
                .values()
            ),
            original_registrations
        )

        # The failed operation must not change the revision.
        self.assertEqual(
            AccountIdentityLock.objects.get(pk=1).revision,
            original_revision
        )

        return response

    def test_admin_creation_handles_database_contention(self):
        # Administrators must receive controlled feedback
        # when the account creation lock is unavailable.
        self.client.force_login(self.admin)

        url = reverse("user_management:user_create")

        self.assert_identity_contention_handled(
            url=url,
            data=self.get_valid_creation_data(),
            redirect_url=url,
            expected_message=(
                "Account creation is temporarily unavailable."
            )
        )

    def test_student_registration_handles_database_contention(self):
        # Public registration must fail safely when
        # the shared synchronization lock is unavailable.
        url = reverse("student_register")

        self.assert_identity_contention_handled(
            url=url,
            data=self.get_valid_creation_data(),
            redirect_url=url,
            expected_message=(
                "Student registration is temporarily unavailable."
            )
        )

    def test_registration_approval_handles_database_contention(self):
        # A failed approval must preserve the application
        # and must not create a student account.
        registration = self.create_registration_request()

        self.client.force_login(self.admin)

        self.assert_identity_contention_handled(
            url=reverse(
                "registration_management:request_approve",
                kwargs={"pk": registration.pk}
            ),
            data={},
            redirect_url=reverse(
                "registration_management:request_list"
            ),
            expected_message=(
                "Registration approval is temporarily unavailable."
            )
        )

        registration.refresh_from_db()

        self.assertEqual(
            registration.status,
            "pending"
        )

    def test_registration_rejection_handles_database_contention(self):
        # A failed rejection must not change the
        # existing pending registration decision.
        registration = self.create_registration_request()

        self.client.force_login(self.admin)

        self.assert_identity_contention_handled(
            url=reverse(
                "registration_management:request_reject",
                kwargs={"pk": registration.pk}
            ),
            data={},
            redirect_url=reverse(
                "registration_management:request_list"
            ),
            expected_message=(
                "Registration rejection is temporarily unavailable."
            )
        )

        registration.refresh_from_db()

        self.assertEqual(
            registration.status,
            "pending"
        )

    def get_valid_edit_data(self, **overrides):
        """
        Return valid account editing information
        for administrative user management tests.
        """

        data = {
            "username": "updated_directory_student",
            "first_name": "Updated",
            "last_name": "Student",
            "email": "updated.student@example.com",
        }

        data.update(overrides)

        return data

    def get_account_snapshot(self, account):
        """
        Capture persisted account information to verify
        that unsuccessful editing operations change nothing.
        """

        User = get_user_model()

        return User.objects.filter(
            pk=account.pk
        ).values().get()

    def test_admin_can_access_user_edit_form(self):
        # Authorized administrators must receive
        # a prepopulated account editing form.
        self.client.force_login(self.admin)

        url = reverse(
            "user_management:user_edit",
            kwargs={"pk": self.student.pk}
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

        self.assertTemplateUsed(
            response,
            "user_management/user_edit.html"
        )

        form = response.context["form"]

        self.assertEqual(
            form.instance.pk,
            self.student.pk
        )

        self.assertEqual(
            form.initial["username"],
            self.student.username
        )

        self.assertEqual(
            form.initial["email"],
            self.student.email
        )

        self.assertEqual(
            set(form.fields),
            {
                "username",
                "first_name",
                "last_name",
                "email",
            }
        )

    def test_edit_button_visible_for_authorized_account(self):
        # Prevent regressions in the view-to-template
        # permission context and editing navigation.
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse(
                "user_management:user_detail",
                kwargs={"pk": self.student.pk}
            )
        )

        edit_url = reverse(
            "user_management:user_edit",
            kwargs={"pk": self.student.pk}
        )

        self.assertEqual(response.status_code, 200)

        self.assertTrue(
            response.context["can_edit_account"]
        )

        self.assertContains(
            response,
            f'href="{edit_url}"'
        )

    def test_anonymous_user_cannot_edit_accounts(self):
        # Anonymous visitors must authenticate before
        # accessing administrative account operations.
        url = reverse(
            "user_management:user_edit",
            kwargs={"pk": self.student.pk}
        )

        original_account = self.get_account_snapshot(
            self.student
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)

        response = self.client.post(
            url,
            self.get_valid_edit_data()
        )

        self.assertEqual(response.status_code, 302)

        self.assertEqual(
            self.get_account_snapshot(self.student),
            original_account
        )

    def test_non_administrators_cannot_edit_accounts(self):
        # Neither regular nor privileged application
        # users may access administrative editing.
        url = reverse(
            "user_management:user_edit",
            kwargs={"pk": self.student.pk}
        )

        for actor in (self.student, self.power_user):

            with self.subTest(actor=actor.username):

                self.client.force_login(actor)

                original_account = (
                    self.get_account_snapshot(self.student)
                )

                response = self.client.get(url)

                self.assertEqual(
                    response.status_code,
                    403
                )

                response = self.client.post(
                    url,
                    self.get_valid_edit_data()
                )

                self.assertEqual(
                    response.status_code,
                    403
                )

                self.assertEqual(
                    self.get_account_snapshot(self.student),
                    original_account
                )

    def test_application_admin_cannot_edit_protected_accounts(self):
        # Ordinary application administrators cannot
        # modify Django staff or superuser identities.
        User = get_user_model()

        User.objects.filter(
            pk=self.admin.pk
        ).update(
            is_staff=False,
            is_superuser=False
        )

        self.admin.refresh_from_db()

        self.client.force_login(self.admin)

        scenarios = (
            (True, False),
            (True, True),
        )

        for is_staff, is_superuser in scenarios:

            with self.subTest(
                is_staff=is_staff,
                is_superuser=is_superuser
            ):

                User.objects.filter(
                    pk=self.student.pk
                ).update(
                    is_staff=is_staff,
                    is_superuser=is_superuser
                )

                original_account = (
                    self.get_account_snapshot(self.student)
                )

                detail_url = reverse(
                    "user_management:user_detail",
                    kwargs={"pk": self.student.pk}
                )

                edit_url = reverse(
                    "user_management:user_edit",
                    kwargs={"pk": self.student.pk}
                )

                response = self.client.get(detail_url)

                self.assertEqual(
                    response.status_code,
                    200
                )

                self.assertFalse(
                    response.context["can_edit_account"]
                )

                self.assertNotContains(
                    response,
                    f'href="{edit_url}"'
                )

                self.assertEqual(
                    self.client.get(edit_url).status_code,
                    403
                )

                self.assertEqual(
                    self.client.post(
                        edit_url,
                        self.get_valid_edit_data()
                    ).status_code,
                    403
                )

                self.assertEqual(
                    self.get_account_snapshot(self.student),
                    original_account
                )

    def test_application_admin_cannot_edit_another_admin(self):
        # Protect other administrator identities from
        # ordinary application administrator accounts.
        User = get_user_model()

        User.objects.filter(
            pk=self.admin.pk
        ).update(
            is_staff=False,
            is_superuser=False
        )

        self.admin.refresh_from_db()

        other_admin = User.objects.create_user(
            username="protected_other_admin",
            email="other.admin@example.com",
            password="Forest!Silver84Ocean"
        )

        other_admin.profile.role = (
            UserProfile.Role.ADMIN
        )

        other_admin.profile.save(
            update_fields=["role"]
        )

        self.client.force_login(self.admin)

        original_account = self.get_account_snapshot(
            other_admin
        )

        detail_url = reverse(
            "user_management:user_detail",
            kwargs={"pk": other_admin.pk}
        )

        edit_url = reverse(
            "user_management:user_edit",
            kwargs={"pk": other_admin.pk}
        )

        response = self.client.get(detail_url)

        self.assertEqual(response.status_code, 200)

        self.assertFalse(
            response.context["can_edit_account"]
        )

        self.assertNotContains(
            response,
            f'href="{edit_url}"'
        )

        self.assertEqual(
            self.client.get(edit_url).status_code,
            403
        )

        self.assertEqual(
            self.client.post(
                edit_url,
                self.get_valid_edit_data()
            ).status_code,
            403
        )

        self.assertEqual(
            self.get_account_snapshot(other_admin),
            original_account
        )

    def test_superuser_administrator_can_edit_protected_account(self):
        # A Django superuser with the application
        # Administrator role may edit protected accounts.
        User = get_user_model()

        User.objects.filter(
            pk=self.admin.pk
        ).update(
            is_staff=True,
            is_superuser=True
        )

        User.objects.filter(
            pk=self.student.pk
        ).update(
            is_staff=True,
            is_superuser=True
        )

        self.admin.refresh_from_db()

        self.client.force_login(self.admin)

        url = reverse(
            "user_management:user_edit",
            kwargs={"pk": self.student.pk}
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            url,
            self.get_valid_edit_data()
        )

        self.assertRedirects(
            response,
            reverse(
                "user_management:user_detail",
                kwargs={"pk": self.student.pk}
            ),
            fetch_redirect_response=False
        )

        self.student.refresh_from_db()

        self.assertEqual(
            self.student.first_name,
            "Updated"
        )

        self.assertTrue(self.student.is_staff)
        self.assertTrue(self.student.is_superuser)

    def test_admin_can_edit_own_unprotected_account(self):
        # Administrators may maintain their own identity
        # without modifying their administrative role.
        User = get_user_model()

        User.objects.filter(
            pk=self.admin.pk
        ).update(
            is_staff=False,
            is_superuser=False
        )

        self.admin.refresh_from_db()

        self.client.force_login(self.admin)

        url = reverse(
            "user_management:user_edit",
            kwargs={"pk": self.admin.pk}
        )

        response = self.client.post(
            url,
            self.get_valid_edit_data(
                username=self.admin.username,
                first_name="Updated",
                last_name="Administrator",
                email=self.admin.email
            )
        )

        self.assertRedirects(
            response,
            reverse(
                "user_management:user_detail",
                kwargs={"pk": self.admin.pk}
            ),
            fetch_redirect_response=False
        )

        self.admin.refresh_from_db()

        self.admin.profile.refresh_from_db()

        self.assertEqual(
            self.admin.first_name,
            "Updated"
        )

        self.assertEqual(
            self.admin.profile.role,
            UserProfile.Role.ADMIN
        )

    def test_edit_missing_account_returns_404(self):
        # Missing accounts must not create new records
        # or expose internal database errors.
        self.client.force_login(self.admin)

        url = reverse(
            "user_management:user_edit",
            kwargs={"pk": 999999}
        )

        self.assertEqual(
            self.client.get(url).status_code,
            404
        )

        self.assertEqual(
            self.client.post(
                url,
                self.get_valid_edit_data()
            ).status_code,
            404
        )

    def test_user_edit_rejects_unsupported_methods(self):
        # Editing supports GET, HEAD and POST only.
        self.client.force_login(self.admin)

        url = reverse(
            "user_management:user_edit",
            kwargs={"pk": self.student.pk}
        )

        for method in ("PUT", "PATCH", "DELETE"):

            with self.subTest(method=method):

                response = self.client.generic(
                    method,
                    url
                )

                self.assertEqual(
                    response.status_code,
                    405
                )

    def test_user_edit_persists_only_authorized_fields(self):
        # Verify successful editing while rejecting
        # attempts to manipulate protected properties.
        self.client.force_login(self.admin)

        account = self.power_user

        original_password = account.password

        original_role = account.profile.role

        original_active = account.is_active

        original_staff = account.is_staff

        original_superuser = account.is_superuser

        original_groups = set(
            account.groups.values_list(
                "pk",
                flat=True
            )
        )

        original_permissions = set(
            account.user_permissions.values_list(
                "pk",
                flat=True
            )
        )

        url = reverse(
            "user_management:user_edit",
            kwargs={"pk": account.pk}
        )

        data = self.get_valid_edit_data(
            email="UPDATED.STUDENT@EXAMPLE.COM",
            role="admin",
            is_staff="true",
            is_superuser="true",
            is_active="false",
            password="UnauthorizedPassword123!",
            groups=[],
            user_permissions=[]
        )

        response = self.client.post(url, data)

        self.assertRedirects(
            response,
            reverse(
                "user_management:user_detail",
                kwargs={"pk": account.pk}
            ),
            fetch_redirect_response=False
        )

        account.refresh_from_db()

        account.profile.refresh_from_db()

        # Verify the four permitted identity changes.
        self.assertEqual(
            account.username,
            "updated_directory_student"
        )

        self.assertEqual(
            account.first_name,
            "Updated"
        )

        self.assertEqual(
            account.last_name,
            "Student"
        )

        self.assertEqual(
            account.email,
            "updated.student@example.com"
        )

        # Verify that protected information is unchanged.
        self.assertEqual(
            account.password,
            original_password
        )

        self.assertEqual(
            account.profile.role,
            original_role
        )

        self.assertEqual(
            account.is_active,
            original_active
        )

        self.assertEqual(
            account.is_staff,
            original_staff
        )

        self.assertEqual(
            account.is_superuser,
            original_superuser
        )

        self.assertEqual(
            set(
                account.groups.values_list(
                    "pk",
                    flat=True
                )
            ),
            original_groups
        )

        self.assertEqual(
            set(
                account.user_permissions.values_list(
                    "pk",
                    flat=True
                )
            ),
            original_permissions
        )

    def test_user_edit_accepts_unchanged_identifiers(self):
        # Existing usernames and email addresses
        # must not conflict with the account itself.
        self.client.force_login(self.admin)

        url = reverse(
            "user_management:user_edit",
            kwargs={"pk": self.student.pk}
        )

        response = self.client.post(
            url,
            self.get_valid_edit_data(
                username=self.student.username,
                email=self.student.email
            )
        )

        self.assertRedirects(
            response,
            reverse(
                "user_management:user_detail",
                kwargs={"pk": self.student.pk}
            ),
            fetch_redirect_response=False
        )

        self.student.refresh_from_db()

        self.assertEqual(
            self.student.first_name,
            "Updated"
        )

    def test_user_edit_rejects_duplicate_identifiers(self):
        # Registered usernames and email addresses
        # must remain unique regardless of letter case.
        self.client.force_login(self.admin)

        url = reverse(
            "user_management:user_edit",
            kwargs={"pk": self.student.pk}
        )

        original_account = self.get_account_snapshot(
            self.student
        )

        scenarios = (
            ("username", self.admin.username),
            ("username", self.admin.username.upper()),
            ("email", self.admin.email),
            ("email", self.admin.email.upper()),
        )

        for field, value in scenarios:

            with self.subTest(
                field=field,
                value=value
            ):

                response = self.client.post(
                    url,
                    self.get_valid_edit_data(
                        **{field: value}
                    )
                )

                self.assertEqual(
                    response.status_code,
                    200
                )

                self.assertIn(
                    field,
                    response.context["form"].errors
                )

                self.assertEqual(
                    self.get_account_snapshot(self.student),
                    original_account
                )

    def test_user_edit_rejects_pending_registration_conflicts(self):
        # Pending registration requests reserve
        # usernames and email addresses.
        registration = self.create_registration_request()

        self.client.force_login(self.admin)

        url = reverse(
            "user_management:user_edit",
            kwargs={"pk": self.student.pk}
        )

        original_account = self.get_account_snapshot(
            self.student
        )

        scenarios = (
            ("username", registration.username),
            ("username", registration.username.upper()),
            ("email", registration.email),
            ("email", registration.email.upper()),
        )

        for field, value in scenarios:

            with self.subTest(
                field=field,
                value=value
            ):

                response = self.client.post(
                    url,
                    self.get_valid_edit_data(
                        **{field: value}
                    )
                )

                self.assertEqual(
                    response.status_code,
                    200
                )

                self.assertIn(
                    field,
                    response.context["form"].errors
                )

                self.assertEqual(
                    self.get_account_snapshot(self.student),
                    original_account
                )

        registration.refresh_from_db()

        self.assertEqual(
            registration.status,
            "pending"
        )

    def test_user_edit_rejects_invalid_identity_information(self):
        # Invalid or incomplete account information
        # must never be persisted.
        self.client.force_login(self.admin)

        url = reverse(
            "user_management:user_edit",
            kwargs={"pk": self.student.pk}
        )

        original_account = self.get_account_snapshot(
            self.student
        )

        scenarios = (
            ("username", ""),
            ("username", "invalid username"),
            ("username", "a" * 151),
            ("first_name", ""),
            ("first_name", "a" * 151),
            ("last_name", ""),
            ("last_name", "a" * 151),
            ("email", ""),
            ("email", "invalid-email-address"),
        )

        for field, value in scenarios:

            with self.subTest(
                field=field,
                value=value
            ):

                response = self.client.post(
                    url,
                    self.get_valid_edit_data(
                        **{field: value}
                    )
                )

                self.assertEqual(
                    response.status_code,
                    200
                )

                self.assertIn(
                    field,
                    response.context["form"].errors
                )

                self.assertEqual(
                    self.get_account_snapshot(self.student),
                    original_account
                )

    def test_user_edit_requires_csrf_token(self):
        # Account editing must reject POST requests
        # without valid cross-site request forgery protection.
        from django.test import Client

        csrf_client = Client(
            enforce_csrf_checks=True
        )

        csrf_client.force_login(self.admin)

        original_account = self.get_account_snapshot(
            self.student
        )

        response = csrf_client.post(
            reverse(
                "user_management:user_edit",
                kwargs={"pk": self.student.pk}
            ),
            self.get_valid_edit_data()
        )

        self.assertEqual(response.status_code, 403)

        self.assertEqual(
            self.get_account_snapshot(self.student),
            original_account
        )

    def test_user_edit_handles_database_contention(self):
        # Failed lock acquisition must preserve the
        # existing account and allow a safe manual retry.
        self.client.force_login(self.admin)

        url = reverse(
            "user_management:user_edit",
            kwargs={"pk": self.student.pk}
        )

        original_account = self.get_account_snapshot(
            self.student
        )

        self.assert_identity_contention_handled(
            url=url,
            data=self.get_valid_edit_data(),
            redirect_url=url,
            expected_message=(
                "Account editing is temporarily unavailable."
            )
        )

        self.assertEqual(
            self.get_account_snapshot(self.student),
            original_account
        )

    def test_user_edit_rolls_back_after_database_failure(self):
        # Verify rollback when an integrity failure
        # occurs after the account has been written.
        from unittest.mock import patch

        from django.db import IntegrityError

        from .models import AccountIdentityLock

        User = get_user_model()

        self.client.force_login(self.admin)

        original_account = self.get_account_snapshot(
            self.student
        )

        original_revision = (
            AccountIdentityLock.objects.get(pk=1).revision
        )

        original_save = User.save

        def save_then_fail(instance, *args, **kwargs):

            # Perform the actual database update.
            original_save(
                instance,
                *args,
                **kwargs
            )

            # Simulate an integrity failure before
            # the enclosing transaction can commit.
            raise IntegrityError(
                "Simulated account update failure"
            )

        url = reverse(
            "user_management:user_edit",
            kwargs={"pk": self.student.pk}
        )

        with patch.object(
            User,
            "save",
            autospec=True,
            side_effect=save_then_fail
        ) as mocked_save:

            response = self.client.post(
                url,
                self.get_valid_edit_data()
            )

        mocked_save.assert_called_once()

        self.assertRedirects(
            response,
            url,
            fetch_redirect_response=False
        )

        # Both the account changes and synchronization
        # revision must have been rolled back.
        self.assertEqual(
            self.get_account_snapshot(self.student),
            original_account
        )

        self.assertEqual(
            AccountIdentityLock.objects.get(pk=1).revision,
            original_revision
        )

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

    def test_contention_detects_native_sqlite_error_codes(self):
        # Native SQLite error codes must take precedence
        # over potentially ambiguous error messages.
        import sqlite3

        from django.db import OperationalError
        from .account_identity import (
            is_account_database_contention,
        )

        scenarios = (
            (sqlite3.SQLITE_BUSY, True),
            (sqlite3.SQLITE_LOCKED, True),
            (sqlite3.SQLITE_BUSY | (1 << 8), True),
            (sqlite3.SQLITE_LOCKED | (1 << 8), True),
            (sqlite3.SQLITE_ERROR, False),
            (sqlite3.SQLITE_IOERR, False),
        )

        for error_code, expected in scenarios:

            with self.subTest(error_code=error_code):

                native_error = sqlite3.OperationalError(
                    "Simulated SQLite database error"
                )

                native_error.sqlite_errorcode = error_code

                error = OperationalError(
                    "Simulated database operation failure"
                )

                error.__cause__ = native_error

                self.assertEqual(
                    is_account_database_contention(error),
                    expected
                )

    def test_contention_detects_supported_error_messages(self):
        # Verify compatibility when native SQLite
        # error codes are unavailable.
        from django.db import OperationalError
        from .account_identity import (
            is_account_database_contention,
        )

        scenarios = (
            ("database is locked", True),
            ("database table is locked", True),
            ("database table is locked: auth_user", True),
            ("database schema is locked", True),
            ("database schema is locked: main", True),
            ("no such table: auth_user", False),
            ("disk I/O error", False),
            ("unable to open database file", False),
        )

        for message, expected in scenarios:

            with self.subTest(message=message):

                error = OperationalError(message)

                self.assertEqual(
                    is_account_database_contention(error),
                    expected
                )

    def test_identity_contention_rolls_back_changes(self):
        # A temporary database error must roll back
        # account creation and the synchronization revision.
        from django.db import OperationalError

        from .account_identity import (
            AccountIdentityBusyError,
            account_identity_transaction,
        )

        from .models import AccountIdentityLock

        User = get_user_model()

        original_revision = (
            AccountIdentityLock.objects.get(pk=1).revision
        )

        original_count = User.objects.count()

        with self.assertRaises(AccountIdentityBusyError):

            with account_identity_transaction():

                User.objects.create_user(
                    username="contention_rollback_user",
                    email="contention.rollback@example.com",
                    password="Forest!Silver84Ocean"
                )

                # Simulate contention after a database write.
                raise OperationalError(
                    "database is locked"
                )

        self.assertEqual(
            User.objects.count(),
            original_count
        )

        self.assertFalse(
            User.objects.filter(
                username="contention_rollback_user"
            ).exists()
        )

        self.assertEqual(
            AccountIdentityLock.objects.get(pk=1).revision,
            original_revision
        )

    def test_unrelated_operational_error_is_not_suppressed(self):
        # Unexpected database failures must propagate
        # instead of being misclassified as contention.
        from django.db import OperationalError

        from .account_identity import (
            account_identity_transaction,
        )

        from .models import AccountIdentityLock

        original_revision = (
            AccountIdentityLock.objects.get(pk=1).revision
        )

        original_error = OperationalError(
            "no such table: unexpected_table"
        )

        with self.assertRaises(OperationalError) as caught:

            with account_identity_transaction():

                raise original_error

        self.assertIs(
            caught.exception,
            original_error
        )

        self.assertEqual(
            AccountIdentityLock.objects.get(pk=1).revision,
            original_revision
        )

class AccountIdentityConcurrencyTests(TransactionTestCase):
    """
    Verify actual SQLite database contention using
    independent connections and concurrent transactions.

    TransactionTestCase permits real database commits
    and rollbacks, unlike Django's ordinary TestCase.
    """

    def setUp(self):
        from django.db import connection
        from .models import AccountIdentityLock

        # These tests specifically exercise SQLite's
        # database locking and contention behaviour.
        if connection.vendor != "sqlite":
            self.skipTest(
                "SQLite-specific concurrency tests."
            )

        # Database flushes may remove migration-created
        # records between TransactionTestCase tests.
        AccountIdentityLock.objects.get_or_create(
            pk=1,
            defaults={"revision": 0}
        )

    def get_concurrent_account_data(self):
        """
        Return credentials shared by the competing
        registration and account creation operations.
        """

        return {
            "username": "concurrent_student",
            "first_name": "Concurrent",
            "last_name": "Student",
            "email": "concurrent.student@example.com",
            "password1": "Forest!Silver84Ocean",
            "password2": "Forest!Silver84Ocean",
        }

    def exercise_concurrent_transactions(
        self,
        *,
        rollback_first_transaction=False
    ):
        """
        Hold a real database transaction open in a
        separate thread while attempting account creation
        through another database connection.
        """

        from concurrent.futures import ThreadPoolExecutor
        from threading import Event

        from django.contrib.auth.hashers import make_password

        from django.db import (
            connection,
            connections,
            transaction,
        )

        from .account_identity import (
            AccountIdentityBusyError,
            account_identity_transaction,
        )

        from .models import (
            AccountIdentityLock,
            StudentRegistrationRequest,
        )

        from .user_management_forms import (
            AdminUserCreationForm,
        )

        data = self.get_concurrent_account_data()

        password_hash = make_password(
            data["password1"]
        )

        original_revision = (
            AccountIdentityLock.objects.get(pk=1).revision
        )

        # Coordinate the two transactions without relying
        # on arbitrary sleep durations.
        lock_acquired = Event()
        release_lock = Event()

        def hold_registration_transaction():
            """
            Create a pending application while retaining
            the shared identity lock until signalled.
            """

            # Django provides thread-local connections.
            worker_connection = connections["default"]

            try:

                with account_identity_transaction():

                    StudentRegistrationRequest.objects.create(
                        username=data["username"],
                        first_name=data["first_name"],
                        last_name=data["last_name"],
                        email=data["email"],
                        password_hash=password_hash,
                        status=(
                            StudentRegistrationRequest
                            .Status.PENDING
                        ),
                    )

                    # Inform the competing transaction
                    # that the database write lock is held.
                    lock_acquired.set()

                    if not release_lock.wait(timeout=10):

                        raise TimeoutError(
                            "Concurrent transaction "
                            "release timed out."
                        )

                    if rollback_first_transaction:

                        # Explicitly roll back the registration
                        # and synchronization revision.
                        transaction.set_rollback(True)

            finally:

                # Release this thread's database connection.
                worker_connection.close()

        # Temporarily shorten SQLite's lock waiting period
        # for the competing connection in this test only.
        with connection.cursor() as cursor:

            cursor.execute("PRAGMA busy_timeout")

            original_timeout = cursor.fetchone()[0]

            cursor.execute("PRAGMA busy_timeout = 100")

        try:

            with ThreadPoolExecutor(max_workers=1) as executor:

                future = executor.submit(
                    hold_registration_transaction
                )

                try:

                    self.assertTrue(
                        lock_acquired.wait(timeout=10),
                        "The first transaction did not acquire "
                        "the account identity lock."
                    )

                    # This must encounter genuine contention,
                    # not a mocked database exception.
                    with self.assertRaises(
                        AccountIdentityBusyError
                    ):

                        with account_identity_transaction():

                            # Validation must not begin while
                            # the competing transaction holds
                            # the synchronization lock.
                            self.fail(
                                "The competing transaction "
                                "entered the protected block."
                            )

                finally:

                    # Always release the worker, even if an
                    # assertion fails, to avoid a deadlock.
                    release_lock.set()

                # Propagate unexpected worker exceptions.
                future.result(timeout=10)

        finally:

            # Restore the original database timeout.
            with connection.cursor() as cursor:

                cursor.execute(
                    f"PRAGMA busy_timeout = {int(original_timeout)}"
                )

        # Only the committed transaction may retain
        # its synchronization revision update.
        expected_revision = original_revision

        if not rollback_first_transaction:
            expected_revision += 1

        self.assertEqual(
            AccountIdentityLock.objects.get(pk=1).revision,
            expected_revision
        )

        # No account may have been created by the
        # unsuccessful competing transaction.
        User = get_user_model()

        self.assertFalse(
            User.objects.filter(
                username=data["username"]
            ).exists()
        )

        # Retry after the first transaction has released
        # the lock, revalidating all account identifiers.
        with account_identity_transaction():

            form = AdminUserCreationForm(data=data)

            if rollback_first_transaction:

                self.assertTrue(
                    form.is_valid(),
                    form.errors.as_text()
                )

                account = form.save()

                self.assertEqual(
                    account.profile.role,
                    UserProfile.Role.REGULAR
                )

            else:

                self.assertFalse(form.is_valid())

                self.assertIn(
                    "username",
                    form.errors
                )

                self.assertIn(
                    "email",
                    form.errors
                )

        return data

    def test_committed_registration_blocks_concurrent_creation(self):
        # A committed registration must reserve both
        # identifiers against subsequent account creation.
        from .models import StudentRegistrationRequest

        User = get_user_model()

        data = self.exercise_concurrent_transactions()

        self.assertEqual(
            StudentRegistrationRequest.objects.filter(
                username=data["username"],
                email=data["email"],
                status=(
                    StudentRegistrationRequest.Status.PENDING
                )
            ).count(),
            1
        )

        self.assertFalse(
            User.objects.filter(
                username=data["username"]
            ).exists()
        )

    def test_rolled_back_registration_allows_account_creation(self):
        # A rolled-back registration must not permanently
        # reserve the username or email address.
        from .models import StudentRegistrationRequest

        User = get_user_model()

        data = self.exercise_concurrent_transactions(
            rollback_first_transaction=True
        )

        self.assertFalse(
            StudentRegistrationRequest.objects.filter(
                username=data["username"]
            ).exists()
        )

        account = User.objects.get(
            username=data["username"]
        )

        self.assertEqual(
            account.email,
            data["email"]
        )

        self.assertTrue(
            account.check_password(data["password1"])
        )

        self.assertFalse(account.is_staff)
        self.assertFalse(account.is_superuser)
        self.assertFalse(account.groups.exists())

class UserRoleManagementTests(TestCase):
    """
    Verify secure application role assignment.

    Application roles must remain independent of
    Django privileges and workspace authorization.
    """

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth.models import Group, Permission

        User = get_user_model()

        # Create an ordinary application administrator.
        cls.admin = User.objects.create_user(
            username="role_test_admin",
            email="role.admin@example.com",
            password="Forest!Silver84Ocean"
        )

        cls.admin.profile.role = UserProfile.Role.ADMIN
        cls.admin.profile.save(update_fields=["role"])

        # Create a Django superuser with application
        # Administrator authorization.
        cls.super_admin = User.objects.create_superuser(
            username="role_test_super_admin",
            email="role.superadmin@example.com",
            password="Forest!Silver84Ocean"
        )

        cls.super_admin.profile.role = UserProfile.Role.ADMIN
        cls.super_admin.profile.save(update_fields=["role"])

        # Create an ordinary registered account.
        cls.student = User.objects.create_user(
            username="role_test_student",
            email="role.student@example.com",
            password="Forest!Silver84Ocean"
        )

        # Create a privileged application account.
        cls.power_user = User.objects.create_user(
            username="role_test_power",
            email="role.power@example.com",
            password="Forest!Silver84Ocean"
        )

        cls.power_user.profile.role = UserProfile.Role.POWER
        cls.power_user.profile.save(update_fields=["role"])

        # Create a protected Django staff account.
        cls.staff_account = User.objects.create_user(
            username="role_test_staff",
            email="role.staff@example.com",
            password="Forest!Silver84Ocean",
            is_staff=True
        )

        # Existing memberships and permissions must
        # survive application role changes.
        cls.workspace_group, _ = Group.objects.get_or_create(
            name="Career Services Student Assistants"
        )

        cls.power_user.groups.add(cls.workspace_group)

        permission = Permission.objects.get(
            content_type__app_label="auth",
            codename="view_user"
        )

        cls.power_user.user_permissions.add(permission)

    def test_application_admin_assignable_roles(self):
        # Ordinary administrators may assign only
        # Regular User and Power User roles.
        from .user_role_services import get_assignable_roles

        self.assertEqual(
            set(
                get_assignable_roles(
                    self.admin,
                    self.student
                )
            ),
            {
                UserProfile.Role.REGULAR,
                UserProfile.Role.POWER,
            }
        )

    def test_superuser_admin_assignable_roles(self):
        # Superusers with the Administrator role
        # may assign all three application roles.
        from .user_role_services import get_assignable_roles

        self.assertEqual(
            set(
                get_assignable_roles(
                    self.super_admin,
                    self.student
                )
            ),
            set(UserProfile.Role.values)
        )

    def test_admin_can_promote_regular_user(self):
        # Ordinary administrators may promote
        # registered users to the Power User role.
        from .user_role_services import change_user_role

        change_user_role(
            administrator=self.admin,
            account_id=self.student.pk,
            new_role=UserProfile.Role.POWER
        )

        self.student.profile.refresh_from_db()

        self.assertEqual(
            self.student.profile.role,
            UserProfile.Role.POWER
        )

    def test_role_change_preserves_other_permissions(self):
        # Changing an application role must not change
        # account identity, credentials or other permissions.
        from .user_role_services import change_user_role

        User = get_user_model()

        original_account = User.objects.filter(
            pk=self.power_user.pk
        ).values().get()

        original_groups = set(
            self.power_user.groups.values_list(
                "pk",
                flat=True
            )
        )

        original_permissions = set(
            self.power_user.user_permissions.values_list(
                "pk",
                flat=True
            )
        )

        change_user_role(
            administrator=self.admin,
            account_id=self.power_user.pk,
            new_role=UserProfile.Role.REGULAR
        )

        self.power_user.profile.refresh_from_db()

        self.assertEqual(
            self.power_user.profile.role,
            UserProfile.Role.REGULAR
        )

        self.assertEqual(
            User.objects.filter(
                pk=self.power_user.pk
            ).values().get(),
            original_account
        )

        self.assertEqual(
            set(
                self.power_user.groups.values_list(
                    "pk",
                    flat=True
                )
            ),
            original_groups
        )

        self.assertEqual(
            set(
                self.power_user.user_permissions.values_list(
                    "pk",
                    flat=True
                )
            ),
            original_permissions
        )

    def test_ordinary_admin_cannot_assign_admin_role(self):
        # Prevent unauthorized creation of additional
        # application administrator accounts.
        from django.core.exceptions import PermissionDenied

        from .user_role_services import change_user_role

        with self.assertRaises(PermissionDenied):

            change_user_role(
                administrator=self.admin,
                account_id=self.student.pk,
                new_role=UserProfile.Role.ADMIN
            )

        self.student.profile.refresh_from_db()

        self.assertEqual(
            self.student.profile.role,
            UserProfile.Role.REGULAR
        )

    def test_superuser_can_assign_admin_without_other_privileges(self):
        # Administrator assignment must not automatically
        # grant Django privileges or workspace membership.
        from .permissions import can_access_workspace
        from .user_role_services import change_user_role

        change_user_role(
            administrator=self.super_admin,
            account_id=self.student.pk,
            new_role=UserProfile.Role.ADMIN
        )

        self.student.refresh_from_db()
        self.student.profile.refresh_from_db()

        self.assertEqual(
            self.student.profile.role,
            UserProfile.Role.ADMIN
        )

        self.assertFalse(self.student.is_staff)
        self.assertFalse(self.student.is_superuser)
        self.assertFalse(self.student.groups.exists())

        self.assertFalse(
            self.student.user_permissions.exists()
        )

        self.assertFalse(
            can_access_workspace(self.student)
        )

        # The new role must nevertheless grant access
        # to authorized application administration.
        self.client.force_login(self.student)

        response = self.client.get(
            reverse("user_management:user_list")
        )

        self.assertEqual(response.status_code, 200)

    def test_non_administrators_cannot_assign_roles(self):
        # Reject unauthorized role changes regardless
        # of the requesting user's existing role.
        from django.contrib.auth.models import AnonymousUser
        from django.core.exceptions import PermissionDenied

        from .user_role_services import change_user_role

        for actor in (
            AnonymousUser(),
            self.student,
            self.power_user,
        ):

            with self.subTest(actor=str(actor)):

                with self.assertRaises(PermissionDenied):

                    change_user_role(
                        administrator=actor,
                        account_id=self.staff_account.pk,
                        new_role=UserProfile.Role.POWER
                    )

        self.staff_account.profile.refresh_from_db()

        self.assertEqual(
            self.staff_account.profile.role,
            UserProfile.Role.REGULAR
        )

    def test_administrators_cannot_modify_own_roles(self):
        # Prevent administrative self-demotion and
        # accidental loss of administrative access.
        from django.core.exceptions import PermissionDenied

        from .user_role_services import (
            change_user_role,
            get_assignable_roles,
        )

        for actor in (
            self.admin,
            self.super_admin,
        ):

            with self.subTest(actor=actor.username):

                self.assertEqual(
                    get_assignable_roles(actor, actor),
                    ()
                )

                with self.assertRaises(PermissionDenied):

                    change_user_role(
                        administrator=actor,
                        account_id=actor.pk,
                        new_role=UserProfile.Role.REGULAR
                    )

                actor.profile.refresh_from_db()

                self.assertEqual(
                    actor.profile.role,
                    UserProfile.Role.ADMIN
                )

    def test_ordinary_admin_cannot_modify_protected_accounts(self):
        # Protect other administrators and accounts
        # with elevated Django privileges.
        from django.core.exceptions import PermissionDenied

        from .user_role_services import (
            change_user_role,
            get_assignable_roles,
        )

        for target in (
            self.staff_account,
            self.super_admin,
        ):

            with self.subTest(target=target.username):

                original_role = target.profile.role

                self.assertEqual(
                    get_assignable_roles(
                        self.admin,
                        target
                    ),
                    ()
                )

                with self.assertRaises(PermissionDenied):

                    change_user_role(
                        administrator=self.admin,
                        account_id=target.pk,
                        new_role=UserProfile.Role.POWER
                    )

                target.profile.refresh_from_db()

                self.assertEqual(
                    target.profile.role,
                    original_role
                )

    def test_superuser_can_demote_another_administrator(self):
        # Authorized demotion must preserve an active
        # administrator and revoke administrative access.
        from .user_role_services import change_user_role

        change_user_role(
            administrator=self.super_admin,
            account_id=self.admin.pk,
            new_role=UserProfile.Role.POWER
        )

        self.admin.profile.refresh_from_db()

        self.assertEqual(
            self.admin.profile.role,
            UserProfile.Role.POWER
        )

        self.assertTrue(
            UserProfile.objects.filter(
                role=UserProfile.Role.ADMIN,
                user__is_active=True
            ).exists()
        )

        # The demoted administrator must lose access
        # to restricted administrative endpoints.
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("user_management:user_list")
        )

        self.assertEqual(response.status_code, 403)

    def test_invalid_role_is_rejected(self):
        # Reject manipulated or nonexistent role identifiers.
        from django.core.exceptions import ValidationError

        from .user_role_services import change_user_role

        for role in (
            "superuser",
            "staff",
            "invalid_role",
            "",
        ):

            with self.subTest(role=role):

                with self.assertRaises(ValidationError):

                    change_user_role(
                        administrator=self.super_admin,
                        account_id=self.student.pk,
                        new_role=role
                    )

        self.student.profile.refresh_from_db()

        self.assertEqual(
            self.student.profile.role,
            UserProfile.Role.REGULAR
        )

    def test_role_service_rechecks_current_authorization(self):
        # A previously authenticated administrator must
        # not retain authority after demotion or deactivation.
        from django.core.exceptions import PermissionDenied

        from .user_role_services import change_user_role

        User = get_user_model()

        # Revoke the administrator's database role
        # without refreshing the in-memory actor.
        UserProfile.objects.filter(
            user_id=self.admin.pk
        ).update(
            role=UserProfile.Role.REGULAR
        )

        with self.assertRaises(PermissionDenied):

            change_user_role(
                administrator=self.admin,
                account_id=self.student.pk,
                new_role=UserProfile.Role.POWER
            )

        # Restore the role, but deactivate the account.
        UserProfile.objects.filter(
            user_id=self.admin.pk
        ).update(
            role=UserProfile.Role.ADMIN
        )

        User.objects.filter(
            pk=self.admin.pk
        ).update(
            is_active=False
        )

        with self.assertRaises(PermissionDenied):

            change_user_role(
                administrator=self.admin,
                account_id=self.student.pk,
                new_role=UserProfile.Role.POWER
            )

        self.student.profile.refresh_from_db()

        self.assertEqual(
            self.student.profile.role,
            UserProfile.Role.REGULAR
        )

    def get_role_url(self, account):
        """Return the account's role management URL."""
        return reverse(
            "user_management:user_role_edit",
            kwargs={"pk": account.pk}
        )

    def get_detail_url(self, account):
        """Return the account's details URL."""
        return reverse(
            "user_management:user_detail",
            kwargs={"pk": account.pk}
        )

    def test_role_endpoint_displays_authorized_choices(self):
        # Available form choices must reflect the
        # requesting administrator's authority.
        scenarios = (
            (
                self.admin,
                {"regular", "power"}
            ),
            (
                self.super_admin,
                {"regular", "power", "admin"}
            ),
        )

        for actor, expected_roles in scenarios:

            with self.subTest(actor=actor.username):

                self.client.force_login(actor)

                response = self.client.get(
                    self.get_role_url(self.student)
                )

                self.assertEqual(response.status_code, 200)

                self.assertTemplateUsed(
                    response,
                    "user_management/user_role_edit.html"
                )

                form = response.context["form"]

                self.assertEqual(
                    set(form.fields),
                    {"role"}
                )

                self.assertEqual(
                    {value for value, label
                     in form.fields["role"].choices},
                    expected_roles
                )

                self.assertEqual(
                    form.initial["role"],
                    UserProfile.Role.REGULAR
                )

                self.assertFalse(form.is_bound)

    def test_manage_role_button_visibility(self):
        # Navigation must use the same permission
        # policy as the protected role endpoint.
        scenarios = (
            (self.admin, self.student, True),
            (self.admin, self.admin, False),
            (self.admin, self.super_admin, False),
            (self.admin, self.staff_account, False),
            (self.super_admin, self.student, True),
            (self.super_admin, self.admin, True),
            (self.super_admin, self.super_admin, False),
        )

        for actor, target, allowed in scenarios:

            with self.subTest(
                actor=actor.username,
                target=target.username
            ):

                self.client.force_login(actor)

                response = self.client.get(
                    self.get_detail_url(target)
                )

                self.assertEqual(response.status_code, 200)

                self.assertEqual(
                    response.context["can_manage_role"],
                    allowed
                )

                link = (
                    f'href="{self.get_role_url(target)}"'
                )

                if allowed:
                    self.assertContains(response, link)
                else:
                    self.assertNotContains(response, link)

    def test_anonymous_role_endpoint_access_is_denied(self):
        # Anonymous visitors cannot view or submit
        # application role management requests.
        url = self.get_role_url(self.student)

        self.assertEqual(
            self.client.get(url).status_code,
            302
        )

        self.assertEqual(
            self.client.post(
                url,
                {"role": "admin"}
            ).status_code,
            302
        )

        self.student.profile.refresh_from_db()

        self.assertEqual(
            self.student.profile.role,
            UserProfile.Role.REGULAR
        )

    def test_non_admin_role_endpoint_access_is_denied(self):
        # Regular and Power Users must not access
        # administrative role management endpoints.
        url = self.get_role_url(self.student)

        for actor in (self.student, self.power_user):

            with self.subTest(actor=actor.username):

                self.client.force_login(actor)

                self.assertEqual(
                    self.client.get(url).status_code,
                    403
                )

                self.assertEqual(
                    self.client.post(
                        url,
                        {"role": "admin"}
                    ).status_code,
                    403
                )

        self.student.profile.refresh_from_db()

        self.assertEqual(
            self.student.profile.role,
            UserProfile.Role.REGULAR
        )

    def test_role_endpoint_protects_restricted_accounts(self):
        # Direct URL access must remain prohibited
        # even when navigation buttons are hidden.
        scenarios = (
            (self.admin, self.admin),
            (self.admin, self.super_admin),
            (self.admin, self.staff_account),
            (self.super_admin, self.super_admin),
        )

        for actor, target in scenarios:

            with self.subTest(
                actor=actor.username,
                target=target.username
            ):

                self.client.force_login(actor)

                original_role = target.profile.role

                url = self.get_role_url(target)

                self.assertEqual(
                    self.client.get(url).status_code,
                    403
                )

                self.assertEqual(
                    self.client.post(
                        url,
                        {"role": "regular"}
                    ).status_code,
                    403
                )

                target.profile.refresh_from_db()

                self.assertEqual(
                    target.profile.role,
                    original_role
                )

    def test_role_endpoint_rejects_manipulated_choices(self):
        # Forged POST parameters must not bypass
        # the administrator's assignment authority.
        self.client.force_login(self.admin)

        url = self.get_role_url(self.student)

        for role in (
            "admin",
            "superuser",
            "staff",
            "invalid_role",
            "",
        ):

            with self.subTest(role=role):

                response = self.client.post(
                    url,
                    {"role": role}
                )

                self.assertEqual(
                    response.status_code,
                    200
                )

                self.assertIn(
                    "role",
                    response.context["form"].errors
                )

                self.student.profile.refresh_from_db()

                self.assertEqual(
                    self.student.profile.role,
                    UserProfile.Role.REGULAR
                )

    def test_role_endpoint_preserves_independent_permissions(self):
        # An authorized role change must preserve
        # all unrelated account properties.
        User = get_user_model()

        self.client.force_login(self.admin)

        account = self.power_user

        original_account = User.objects.filter(
            pk=account.pk
        ).values().get()

        original_groups = set(
            account.groups.values_list(
                "pk",
                flat=True
            )
        )

        original_permissions = set(
            account.user_permissions.values_list(
                "pk",
                flat=True
            )
        )

        response = self.client.post(
            self.get_role_url(account),
            {
                "role": "regular",
                "is_staff": "true",
                "is_superuser": "true",
                "is_active": "false",
                "username": "unauthorized_username",
                "password": "UnauthorizedPassword123!",
                "groups": [self.workspace_group.pk],
            }
        )

        self.assertRedirects(
            response,
            self.get_detail_url(account),
            fetch_redirect_response=False
        )

        account.refresh_from_db()
        account.profile.refresh_from_db()

        self.assertEqual(
            account.profile.role,
            UserProfile.Role.REGULAR
        )

        self.assertEqual(
            User.objects.filter(
                pk=account.pk
            ).values().get(),
            original_account
        )

        self.assertEqual(
            set(
                account.groups.values_list(
                    "pk",
                    flat=True
                )
            ),
            original_groups
        )

        self.assertEqual(
            set(
                account.user_permissions.values_list(
                    "pk",
                    flat=True
                )
            ),
            original_permissions
        )

    def test_superuser_can_assign_admin_through_endpoint(self):
        # Authorized Administrator assignment must
        # not grant Django or workspace privileges.
        from .permissions import can_access_workspace

        self.client.force_login(self.super_admin)

        response = self.client.post(
            self.get_role_url(self.student),
            {"role": "admin"}
        )

        self.assertRedirects(
            response,
            self.get_detail_url(self.student),
            fetch_redirect_response=False
        )

        self.student.refresh_from_db()
        self.student.profile.refresh_from_db()

        self.assertEqual(
            self.student.profile.role,
            UserProfile.Role.ADMIN
        )

        self.assertFalse(self.student.is_staff)
        self.assertFalse(self.student.is_superuser)
        self.assertFalse(self.student.groups.exists())

        self.assertFalse(
            self.student.user_permissions.exists()
        )

        self.assertFalse(
            can_access_workspace(self.student)
        )

        # The newly assigned application role must
        # permit access to application administration.
        self.client.force_login(self.student)

        response = self.client.get(
            reverse("user_management:user_list")
        )

        self.assertEqual(response.status_code, 200)

    def test_role_endpoint_rejects_missing_accounts_and_methods(self):
        # Missing accounts and unsupported methods
        # must receive appropriate HTTP responses.
        self.client.force_login(self.admin)

        missing_url = reverse(
            "user_management:user_role_edit",
            kwargs={"pk": 999999}
        )

        self.assertEqual(
            self.client.get(missing_url).status_code,
            404
        )

        self.assertEqual(
            self.client.post(
                missing_url,
                {"role": "power"}
            ).status_code,
            404
        )

        url = self.get_role_url(self.student)

        for method in ("PUT", "PATCH", "DELETE"):

            with self.subTest(method=method):

                response = self.client.generic(
                    method,
                    url
                )

                self.assertEqual(
                    response.status_code,
                    405
                )

        self.student.profile.refresh_from_db()

        self.assertEqual(
            self.student.profile.role,
            UserProfile.Role.REGULAR
        )

    def test_role_endpoint_requires_csrf_protection(self):
        # Reject forged cross-site requests that
        # do not provide a valid CSRF token.
        from django.test import Client

        csrf_client = Client(
            enforce_csrf_checks=True
        )

        csrf_client.force_login(self.admin)

        response = csrf_client.post(
            self.get_role_url(self.student),
            {"role": "power"}
        )

        self.assertEqual(response.status_code, 403)

        self.student.profile.refresh_from_db()

        self.assertEqual(
            self.student.profile.role,
            UserProfile.Role.REGULAR
        )

    def test_role_endpoint_handles_database_contention(self):
        # Temporary lock contention must produce
        # safe feedback without modifying roles.
        from unittest.mock import patch

        from django.contrib.messages import get_messages
        from django.db import OperationalError

        from .models import AccountIdentityLock

        self.client.force_login(self.admin)

        original_revision = (
            AccountIdentityLock.objects.get(pk=1).revision
        )

        url = self.get_role_url(self.student)

        with patch(
            "core.account_identity."
            "AccountIdentityLock.objects.filter",
            side_effect=OperationalError(
                "database is locked"
            )
        ) as lock_query:

            response = self.client.post(
                url,
                {"role": "power"}
            )

        lock_query.assert_called_once_with(pk=1)

        self.assertRedirects(
            response,
            url,
            fetch_redirect_response=False
        )

        feedback = [
            str(message)
            for message in get_messages(
                response.wsgi_request
            )
        ]

        self.assertTrue(
            any(
                "Role management is temporarily unavailable"
                in message
                for message in feedback
            )
        )

        self.assertFalse(
            any(
                "database is locked" in message.lower()
                for message in feedback
            )
        )

        self.student.profile.refresh_from_db()

        self.assertEqual(
            self.student.profile.role,
            UserProfile.Role.REGULAR
        )

        self.assertEqual(
            AccountIdentityLock.objects.get(pk=1).revision,
            original_revision
        )

    def test_role_endpoint_rolls_back_after_database_failure(self):
        # Verify that a failure occurring after
        # persistence reverses the complete transaction.
        from unittest.mock import patch

        from django.db import IntegrityError

        from .models import AccountIdentityLock

        self.client.force_login(self.admin)

        original_profile = UserProfile.objects.filter(
            user_id=self.student.pk
        ).values().get()

        original_revision = (
            AccountIdentityLock.objects.get(pk=1).revision
        )

        original_save = UserProfile.save

        def save_then_fail(instance, *args, **kwargs):

            # Execute the real profile database update.
            original_save(
                instance,
                *args,
                **kwargs
            )

            # Simulate failure before transaction commit.
            raise IntegrityError(
                "Simulated role update failure"
            )

        url = self.get_role_url(self.student)

        with patch.object(
            UserProfile,
            "save",
            autospec=True,
            side_effect=save_then_fail
        ) as mocked_save:

            response = self.client.post(
                url,
                {"role": "power"}
            )

        mocked_save.assert_called_once()

        self.assertRedirects(
            response,
            url,
            fetch_redirect_response=False
        )

        # Both the profile and synchronization revision
        # must retain their original persisted values.
        self.assertEqual(
            UserProfile.objects.filter(
                user_id=self.student.pk
            ).values().get(),
            original_profile
        )

        self.assertEqual(
            AccountIdentityLock.objects.get(pk=1).revision,
            original_revision
        )