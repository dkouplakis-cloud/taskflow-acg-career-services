from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import resolve_url
from django.test import RequestFactory

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