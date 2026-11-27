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