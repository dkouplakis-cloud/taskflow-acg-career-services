
"""
Security tests for TaskFlow workspace membership management.

Verify that confidential Career Services workspace access
remains independent of application roles, Django privileges
and unrelated group memberships.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.db.models import QuerySet
from django.test import TestCase
import time

from django.contrib.messages import get_messages
from django.db import OperationalError
from django.test import Client
from django.urls import reverse
from projects.models import Project, ProjectAccess
from projects.permissions import (
    can_modify_project_tasks,
    visible_projects_for_user,
)

from .models import AccountIdentityLock, UserProfile
from .permissions import (
    WORKSPACE_GROUP_NAMES,
    can_access_workspace,
    is_career_services_staff,
)

from .user_workspace_services import (
    NO_WORKSPACE_ACCESS,
    can_manage_workspace_membership,
    change_workspace_membership,
    get_workspace_memberships,
    WORKSPACE_STATE_MAX_AGE,
    create_workspace_state_token,
    get_workspace_authorization_state,
)


class WorkspaceMembershipManagementTests(TestCase):
    """
    Verify authorization, membership persistence,
    project isolation and transactional rollback.
    """

    @classmethod
    def setUpTestData(cls):

        User = get_user_model()

        # Create an authorized workspace administrator.
        cls.super_admin = User.objects.create_superuser(
            username="workspace_super_admin",
            email="workspace.superadmin@example.com",
            password="Forest!Silver84Ocean"
        )

        cls.super_admin.profile.role = (
            UserProfile.Role.ADMIN
        )

        cls.super_admin.profile.save(
            update_fields=["role"]
        )

        # Create an administrator without Django
        # superuser authority.
        cls.admin = User.objects.create_user(
            username="workspace_admin",
            email="workspace.admin@example.com",
            password="Forest!Silver84Ocean"
        )

        cls.admin.profile.role = UserProfile.Role.ADMIN

        cls.admin.profile.save(
            update_fields=["role"]
        )

        # Create the ordinary account being managed.
        cls.student = User.objects.create_user(
            username="workspace_student",
            email="workspace.student@example.com",
            password="Forest!Silver84Ocean"
        )

        # Create a Django superuser without the
        # application Administrator role.
        cls.unprivileged_superuser = (
            User.objects.create_superuser(
                username="workspace_other_superuser",
                email="workspace.other@example.com",
                password="Forest!Silver84Ocean"
            )
        )

        # Reuse the migration-initialized workspace groups.
        cls.staff_group, _ = Group.objects.get_or_create(
            name="Career Services Staff"
        )

        cls.faculty_group, _ = Group.objects.get_or_create(
            name="Authorized Faculty"
        )

        cls.assistant_group, _ = Group.objects.get_or_create(
            name="Career Services Student Assistants"
        )

        cls.super_admin.groups.add(cls.staff_group)

        # Unrelated memberships and permissions must
        # remain untouched by the management service.
        cls.unrelated_group = Group.objects.create(
            name="Unrelated Test Group"
        )

        cls.permission = Permission.objects.get(
            content_type__app_label="auth",
            codename="view_user"
        )

        # Create two independent internal projects.
        cls.project_one = Project.objects.create(
            owner=cls.super_admin,
            name="Internal Project One"
        )

        cls.project_two = Project.objects.create(
            owner=cls.super_admin,
            name="Internal Project Two"
        )

    def assign_membership(self, membership):
        """Assign membership through the secured service."""

        return change_workspace_membership(
            administrator=self.super_admin,
            account_id=self.student.pk,
            membership=membership
        )

    def create_project_grant(
        self,
        project,
        access_level=ProjectAccess.AccessLevel.VIEWER
    ):
        """Create an explicit project authorization grant."""

        return ProjectAccess.objects.create(
            project=project,
            user=self.student,
            access_level=access_level
        )

    def test_unauthorized_accounts_cannot_manage_memberships(self):
        # Both Administrator role and Django superuser
        # authority are required. Self-assignment is denied.
        from django.contrib.auth.models import AnonymousUser

        scenarios = (
            (AnonymousUser(), self.student),
            (self.admin, self.student),
            (self.student, self.admin),
            (self.unprivileged_superuser, self.student),
            (self.super_admin, self.super_admin),
        )

        for actor, target in scenarios:

            with self.subTest(
                actor=str(actor),
                target=target.username
            ):

                original_memberships = (
                    get_workspace_memberships(target)
                )

                self.assertFalse(
                    can_manage_workspace_membership(
                        actor,
                        target
                    )
                )

                with self.assertRaises(PermissionDenied):

                    change_workspace_membership(
                        administrator=actor,
                        account_id=target.pk,
                        membership="Career Services Staff"
                    )

                self.assertEqual(
                    get_workspace_memberships(target),
                    original_memberships
                )

    def test_service_rechecks_current_administrator_authority(self):
        # Stale in-memory administrator privileges must
        # not permit unauthorized membership changes.
        User = get_user_model()

        # Revoke the administrator's application role.
        UserProfile.objects.filter(
            user_id=self.super_admin.pk
        ).update(
            role=UserProfile.Role.REGULAR
        )

        with self.assertRaises(PermissionDenied):

            self.assign_membership(
                "Career Services Staff"
            )

        # Restore the role but revoke superuser authority.
        UserProfile.objects.filter(
            user_id=self.super_admin.pk
        ).update(
            role=UserProfile.Role.ADMIN
        )

        User.objects.filter(
            pk=self.super_admin.pk
        ).update(
            is_superuser=False
        )

        with self.assertRaises(PermissionDenied):

            self.assign_membership(
                "Career Services Staff"
            )

        # Restore superuser authority but deactivate
        # the administrator's account.
        User.objects.filter(
            pk=self.super_admin.pk
        ).update(
            is_superuser=True,
            is_active=False
        )

        with self.assertRaises(PermissionDenied):

            self.assign_membership(
                "Career Services Staff"
            )

        self.assertEqual(
            get_workspace_memberships(self.student),
            ()
        )

    def test_membership_preserves_independent_permissions(self):
        # Membership changes must preserve identity,
        # application roles and unrelated permissions.
        User = get_user_model()

        self.student.groups.add(
            self.unrelated_group
        )

        self.student.user_permissions.add(
            self.permission
        )

        original_account = User.objects.filter(
            pk=self.student.pk
        ).values().get()

        original_profile = UserProfile.objects.filter(
            user_id=self.student.pk
        ).values().get()

        for membership in WORKSPACE_GROUP_NAMES:

            with self.subTest(membership=membership):

                self.assign_membership(membership)

                self.assertEqual(
                    get_workspace_memberships(self.student),
                    (membership,)
                )

                self.assertTrue(
                    self.student.groups.filter(
                        pk=self.unrelated_group.pk
                    ).exists()
                )

                self.assertEqual(
                    set(
                        self.student.user_permissions
                        .values_list("pk", flat=True)
                    ),
                    {self.permission.pk}
                )

                self.assertEqual(
                    User.objects.filter(
                        pk=self.student.pk
                    ).values().get(),
                    original_account
                )

                self.assertEqual(
                    UserProfile.objects.filter(
                        user_id=self.student.pk
                    ).values().get(),
                    original_profile
                )

    def test_staff_membership_grants_office_wide_access(self):
        # Staff membership must provide office-wide
        # project visibility and task modification access.
        self.assign_membership(
            "Career Services Staff"
        )

        self.assertTrue(
            can_access_workspace(self.student)
        )

        self.assertTrue(
            is_career_services_staff(self.student)
        )

        self.assertEqual(
            set(
                visible_projects_for_user(self.student)
                .values_list("pk", flat=True)
            ),
            {
                self.project_one.pk,
                self.project_two.pk,
            }
        )

        for project in (
            self.project_one,
            self.project_two,
        ):

            self.assertTrue(
                can_modify_project_tasks(
                    self.student,
                    project
                )
            )

    def test_scoped_memberships_require_explicit_project_grants(self):
        # Faculty and student assistants must never
        # receive office-wide project authorization.
        memberships = (
            "Authorized Faculty",
            "Career Services Student Assistants",
        )

        for membership in memberships:

            with self.subTest(membership=membership):

                self.assign_membership(membership)

                self.assertTrue(
                    can_access_workspace(self.student)
                )

                self.assertFalse(
                    is_career_services_staff(self.student)
                )

                # Workspace membership alone does not
                # grant access to confidential projects.
                self.assertFalse(
                    visible_projects_for_user(
                        self.student
                    ).exists()
                )

                self.assertFalse(
                    can_modify_project_tasks(
                        self.student,
                        self.project_one
                    )
                )

                # Viewer grants permit visibility only.
                grant = self.create_project_grant(
                    self.project_one
                )

                self.assertEqual(
                    set(
                        visible_projects_for_user(
                            self.student
                        ).values_list("pk", flat=True)
                    ),
                    {self.project_one.pk}
                )

                self.assertFalse(
                    can_modify_project_tasks(
                        self.student,
                        self.project_one
                    )
                )

                # Contributor grants permit task changes
                # only within the assigned project.
                grant.access_level = (
                    ProjectAccess.AccessLevel.CONTRIBUTOR
                )

                grant.save(
                    update_fields=["access_level"]
                )

                self.assertTrue(
                    can_modify_project_tasks(
                        self.student,
                        self.project_one
                    )
                )

                self.assertFalse(
                    can_modify_project_tasks(
                        self.student,
                        self.project_two
                    )
                )

    def test_revocation_removes_grants_and_prevents_reactivation(self):
        # Revoking membership must remove old project
        # grants so later membership restoration is safe.
        self.assign_membership(
            "Career Services Student Assistants"
        )

        self.create_project_grant(
            self.project_one,
            ProjectAccess.AccessLevel.CONTRIBUTOR
        )

        self.assertTrue(
            can_modify_project_tasks(
                self.student,
                self.project_one
            )
        )

        # Revoke all managed workspace memberships.
        self.assign_membership(NO_WORKSPACE_ACCESS)

        self.assertEqual(
            get_workspace_memberships(self.student),
            ()
        )

        self.assertFalse(
            can_access_workspace(self.student)
        )

        self.assertFalse(
            visible_projects_for_user(
                self.student
            ).exists()
        )

        self.assertFalse(
            ProjectAccess.objects.filter(
                user_id=self.student.pk
            ).exists()
        )

        self.assertFalse(
            can_modify_project_tasks(
                self.student,
                self.project_one
            )
        )

        # Restoring membership must not reactivate
        # the previously removed authorization grants.
        self.assign_membership(
            "Career Services Student Assistants"
        )

        self.assertTrue(
            can_access_workspace(self.student)
        )

        self.assertFalse(
            visible_projects_for_user(
                self.student
            ).exists()
        )

        self.assertFalse(
            can_modify_project_tasks(
                self.student,
                self.project_one
            )
        )

    def test_membership_change_removes_previous_project_grants(self):
        # Normalize legacy accounts containing multiple
        # workspace memberships and remove obsolete grants.
        self.student.groups.add(
            self.faculty_group,
            self.assistant_group,
            self.unrelated_group
        )

        self.create_project_grant(
            self.project_one
        )

        self.create_project_grant(
            self.project_two,
            ProjectAccess.AccessLevel.CONTRIBUTOR
        )

        self.assign_membership(
            "Authorized Faculty"
        )

        self.assertEqual(
            get_workspace_memberships(self.student),
            ("Authorized Faculty",)
        )

        self.assertFalse(
            ProjectAccess.objects.filter(
                user_id=self.student.pk
            ).exists()
        )

        self.assertTrue(
            self.student.groups.filter(
                pk=self.unrelated_group.pk
            ).exists()
        )

        # Membership changes must never delete projects
        # or modify their ownership.
        self.assertEqual(
            Project.objects.filter(
                pk__in=[
                    self.project_one.pk,
                    self.project_two.pk,
                ],
                owner=self.super_admin
            ).count(),
            2
        )

    def test_unchanged_membership_preserves_project_grants(self):
        # Resubmitting an unchanged membership must
        # not remove legitimate project assignments.
        self.assign_membership(
            "Authorized Faculty"
        )

        grant = self.create_project_grant(
            self.project_one,
            ProjectAccess.AccessLevel.CONTRIBUTOR
        )

        self.assign_membership(
            "Authorized Faculty"
        )

        grant.refresh_from_db()

        self.assertEqual(
            grant.access_level,
            ProjectAccess.AccessLevel.CONTRIBUTOR
        )

        self.assertTrue(
            can_modify_project_tasks(
                self.student,
                self.project_one
            )
        )

    def test_obsolete_grants_without_membership_are_removed(self):
        # Historical grants must not expose projects
        # to accounts without workspace membership.
        self.create_project_grant(
            self.project_one,
            ProjectAccess.AccessLevel.CONTRIBUTOR
        )

        self.assertFalse(
            visible_projects_for_user(
                self.student
            ).exists()
        )

        self.assertFalse(
            can_modify_project_tasks(
                self.student,
                self.project_one
            )
        )

        # Explicitly retaining no membership must
        # clean up obsolete authorization records.
        self.assign_membership(NO_WORKSPACE_ACCESS)

        self.assertFalse(
            ProjectAccess.objects.filter(
                user_id=self.student.pk
            ).exists()
        )

        # Initial membership assignment must also
        # remove any obsolete project grants.
        self.create_project_grant(
            self.project_two
        )

        self.assign_membership(
            "Authorized Faculty"
        )

        self.assertFalse(
            visible_projects_for_user(
                self.student
            ).exists()
        )

        self.assertFalse(
            ProjectAccess.objects.filter(
                user_id=self.student.pk
            ).exists()
        )

    def test_invalid_memberships_and_inactive_accounts_are_rejected(self):
        # Arbitrary Django groups and manipulated
        # membership identifiers must be rejected.
        for membership in (
            "",
            "admin",
            "superuser",
            "Invalid Workspace Group",
            self.unrelated_group.name,
        ):

            with self.subTest(membership=membership):

                with self.assertRaises(ValidationError):

                    self.assign_membership(membership)

                self.assertEqual(
                    get_workspace_memberships(self.student),
                    ()
                )

        # Existing membership can be revoked even
        # after an account has been deactivated.
        self.assign_membership(
            "Authorized Faculty"
        )

        self.create_project_grant(
            self.project_one
        )

        User = get_user_model()

        User.objects.filter(
            pk=self.student.pk
        ).update(
            is_active=False
        )

        self.student.refresh_from_db()

        self.assertFalse(
            can_access_workspace(self.student)
        )

        with self.assertRaises(ValidationError):

            self.assign_membership(
                "Career Services Staff"
            )

        self.assertEqual(
            get_workspace_memberships(self.student),
            ("Authorized Faculty",)
        )

        self.assign_membership(NO_WORKSPACE_ACCESS)

        self.assertEqual(
            get_workspace_memberships(self.student),
            ()
        )

        self.assertFalse(
            ProjectAccess.objects.filter(
                user_id=self.student.pk
            ).exists()
        )

    def test_missing_or_misconfigured_workspace_groups_are_rejected(self):
        # Missing authorization groups must not be
        # silently recreated during assignment.
        self.faculty_group.delete()

        with self.assertRaises(ValidationError):

            self.assign_membership(
                "Authorized Faculty"
            )

        self.assertFalse(
            Group.objects.filter(
                name="Authorized Faculty"
            ).exists()
        )

        # Workspace groups carrying Django permissions
        # must not silently grant additional privileges.
        self.assistant_group.permissions.add(
            self.permission
        )

        with self.assertRaises(ValidationError):

            self.assign_membership(
                "Career Services Student Assistants"
            )

        self.assertEqual(
            get_workspace_memberships(self.student),
            ()
        )

        self.assertFalse(
            can_access_workspace(self.student)
        )

    def test_membership_changes_roll_back_after_database_failure(self):
        # Both membership changes and deleted project
        # grants must roll back if persistence fails.
        self.assign_membership(
            "Authorized Faculty"
        )

        self.student.groups.add(
            self.unrelated_group
        )

        grant = self.create_project_grant(
            self.project_one,
            ProjectAccess.AccessLevel.CONTRIBUTOR
        )

        original_groups = set(
            self.student.groups.values_list(
                "pk",
                flat=True
            )
        )

        original_revision = (
            AccountIdentityLock.objects.get(pk=1).revision
        )

        original_delete = QuerySet.delete

        def delete_then_fail(queryset, *args, **kwargs):

            # Perform the actual database deletion.
            result = original_delete(
                queryset,
                *args,
                **kwargs
            )

            # Simulate failure after project grants
            # have been removed from the database.
            if queryset.model is ProjectAccess:

                raise IntegrityError(
                    "Simulated project grant deletion failure"
                )

            return result

        with patch.object(
            QuerySet,
            "delete",
            autospec=True,
            side_effect=delete_then_fail
        ):

            with self.assertRaises(IntegrityError):

                self.assign_membership(
                    "Career Services Student Assistants"
                )

        # Original membership and unrelated groups
        # must remain intact after rollback.
        self.assertEqual(
            set(
                self.student.groups.values_list(
                    "pk",
                    flat=True
                )
            ),
            original_groups
        )

        self.assertEqual(
            get_workspace_memberships(self.student),
            ("Authorized Faculty",)
        )

        # The deleted project grant must be restored
        # by the enclosing atomic transaction.
        grant.refresh_from_db()

        self.assertEqual(
            grant.access_level,
            ProjectAccess.AccessLevel.CONTRIBUTOR
        )

        self.assertTrue(
            can_modify_project_tasks(
                self.student,
                self.project_one
            )
        )

        self.assertEqual(
            AccountIdentityLock.objects.get(pk=1).revision,
            original_revision
        )

    def get_workspace_url(self, account):
        """Return the account's workspace management URL."""

        return reverse(
            "user_management:user_workspace_edit",
            kwargs={"pk": account.pk}
        )

    def get_detail_url(self, account):
        """Return the account's details URL."""

        return reverse(
            "user_management:user_detail",
            kwargs={"pk": account.pk}
        )

    def get_workspace_token(self, account):
        """Retrieve a fresh signed token through the HTTP interface."""

        response = self.client.get(
            self.get_workspace_url(account)
        )

        self.assertEqual(response.status_code, 200)

        token = response.context["form"]["state_token"].value()

        self.assertTrue(token)

        return token

    def submit_workspace_membership(
        self,
        account,
        membership,
        token
    ):
        """Submit a confirmed workspace membership update."""

        return self.client.post(
            self.get_workspace_url(account),
            {
                "membership": membership,
                "confirm_change": "on",
                "state_token": token,
            }
        )

    def assert_stale_submission_rejected(
        self,
        account,
        membership,
        token
    ):
        """Verify rejection without authorization modifications."""

        account.refresh_from_db()

        original_state = (
            get_workspace_authorization_state(account)
        )

        original_revision = (
            AccountIdentityLock.objects.get(pk=1).revision
        )

        response = self.submit_workspace_membership(
            account,
            membership,
            token
        )

        self.assertRedirects(
            response,
            self.get_workspace_url(account),
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
                "authorization" in message.lower()
                for message in feedback
            )
        )

        account.refresh_from_db()

        self.assertEqual(
            get_workspace_authorization_state(account),
            original_state
        )

        self.assertEqual(
            AccountIdentityLock.objects.get(pk=1).revision,
            original_revision
        )

    def test_workspace_endpoint_displays_authorization_state(self):
        # The interface must accurately display the
        # reviewed memberships and existing project grants.
        self.assign_membership("Authorized Faculty")

        self.create_project_grant(self.project_one)

        self.client.force_login(self.super_admin)

        response = self.client.get(
            self.get_workspace_url(self.student)
        )

        self.assertEqual(response.status_code, 200)

        self.assertTemplateUsed(
            response,
            "user_management/user_workspace_edit.html"
        )

        self.assertEqual(
            list(response.context["current_memberships"]),
            ["Authorized Faculty"]
        )

        self.assertEqual(
            response.context["project_grant_count"],
            1
        )

        form = response.context["form"]

        self.assertEqual(
            set(form.fields),
            {
                "membership",
                "confirm_change",
                "state_token",
            }
        )

        self.assertEqual(
            form.initial["membership"],
            "Authorized Faculty"
        )

        self.assertTrue(
            form.fields["confirm_change"].required
        )

        self.assertTrue(
            form.fields["state_token"].required
        )

        self.assertTrue(form["state_token"].value())

        self.assertContains(
            response,
            'name="state_token"'
        )

    def test_workspace_management_button_visibility(self):
        # Only eligible superuser administrators
        # may see the workspace management action.
        scenarios = (
            (self.super_admin, self.student, True),
            (self.super_admin, self.admin, True),
            (self.super_admin, self.super_admin, False),
            (self.admin, self.student, False),
            (self.admin, self.admin, False),
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
                    response.context["can_manage_workspace"],
                    allowed
                )

                link = (
                    f'href="{self.get_workspace_url(target)}"'
                )

                if allowed:
                    self.assertContains(response, link)
                else:
                    self.assertNotContains(response, link)

    def test_anonymous_workspace_endpoint_access_is_denied(self):
        # Anonymous users cannot retrieve or submit
        # workspace management forms.
        url = self.get_workspace_url(self.student)

        self.assertEqual(
            self.client.get(url).status_code,
            302
        )

        self.assertEqual(
            self.client.post(
                url,
                {
                    "membership": "Career Services Staff",
                    "confirm_change": "on",
                }
            ).status_code,
            302
        )

        self.assertEqual(
            get_workspace_memberships(self.student),
            ()
        )

    def test_unauthorized_workspace_endpoint_access_is_denied(self):
        # Direct URL access must enforce both
        # administrative authorization requirements.
        scenarios = (
            (self.admin, self.student),
            (self.student, self.admin),
            (self.unprivileged_superuser, self.student),
            (self.super_admin, self.super_admin),
        )

        for actor, target in scenarios:

            with self.subTest(
                actor=actor.username,
                target=target.username
            ):

                self.client.force_login(actor)

                original_memberships = (
                    get_workspace_memberships(target)
                )

                url = self.get_workspace_url(target)

                self.assertEqual(
                    self.client.get(url).status_code,
                    403
                )

                self.assertEqual(
                    self.client.post(
                        url,
                        {
                            "membership": "Career Services Staff",
                            "confirm_change": "on",
                            "state_token": "invalid",
                        }
                    ).status_code,
                    403
                )

                self.assertEqual(
                    get_workspace_memberships(target),
                    original_memberships
                )

    def test_workspace_endpoint_rejects_invalid_form_data(self):
        # Mandatory confirmation, valid membership and
        # a signed state token must all be supplied.
        self.client.force_login(self.super_admin)

        token = self.get_workspace_token(self.student)

        valid_data = {
            "membership": "Authorized Faculty",
            "confirm_change": "on",
            "state_token": token,
        }

        scenarios = (
            ({"confirm_change": ""}, "confirm_change"),
            ({"state_token": ""}, "state_token"),
            ({"state_token": "x" * 1025}, "state_token"),
            ({"membership": ""}, "membership"),
            (
                {"membership": self.unrelated_group.name},
                "membership"
            ),
            ({"membership": "superuser"}, "membership"),
        )

        for overrides, error_field in scenarios:

            with self.subTest(overrides=overrides):

                response = self.client.post(
                    self.get_workspace_url(self.student),
                    {
                        **valid_data,
                        **overrides,
                    }
                )

                self.assertEqual(response.status_code, 200)

                self.assertIn(
                    error_field,
                    response.context["form"].errors
                )

                self.assertEqual(
                    get_workspace_memberships(self.student),
                    ()
                )

    def test_workspace_endpoint_assigns_membership_safely(self):
        # A valid submission may change membership
        # but must preserve unrelated privileges.
        self.client.force_login(self.super_admin)

        self.student.groups.add(
            self.unrelated_group
        )

        original_role = self.student.profile.role

        token = self.get_workspace_token(self.student)

        response = self.client.post(
            self.get_workspace_url(self.student),
            {
                "membership": (
                    "Career Services Student Assistants"
                ),
                "confirm_change": "on",
                "state_token": token,
                "role": "admin",
                "is_staff": "true",
                "is_superuser": "true",
                "is_active": "false",
            }
        )

        self.assertRedirects(
            response,
            self.get_detail_url(self.student),
            fetch_redirect_response=False
        )

        self.student.refresh_from_db()
        self.student.profile.refresh_from_db()

        self.assertEqual(
            get_workspace_memberships(self.student),
            ("Career Services Student Assistants",)
        )

        self.assertEqual(
            self.student.profile.role,
            original_role
        )

        self.assertTrue(self.student.is_active)
        self.assertFalse(self.student.is_staff)
        self.assertFalse(self.student.is_superuser)

        self.assertTrue(
            self.student.groups.filter(
                pk=self.unrelated_group.pk
            ).exists()
        )

        self.assertTrue(
            can_access_workspace(self.student)
        )

        # Scoped membership alone grants no projects.
        self.assertFalse(
            visible_projects_for_user(
                self.student
            ).exists()
        )

    def test_workspace_endpoint_revokes_and_restores_membership(self):
        # Previously granted project permissions
        # must not reactivate when membership returns.
        self.assign_membership(
            "Career Services Student Assistants"
        )

        self.create_project_grant(
            self.project_one,
            ProjectAccess.AccessLevel.CONTRIBUTOR
        )

        self.client.force_login(self.super_admin)

        token = self.get_workspace_token(self.student)

        response = self.submit_workspace_membership(
            self.student,
            NO_WORKSPACE_ACCESS,
            token
        )

        self.assertRedirects(
            response,
            self.get_detail_url(self.student),
            fetch_redirect_response=False
        )

        self.assertFalse(
            can_access_workspace(self.student)
        )

        self.assertFalse(
            ProjectAccess.objects.filter(
                user_id=self.student.pk
            ).exists()
        )

        # Restore membership using a fresh state token.
        token = self.get_workspace_token(self.student)

        response = self.submit_workspace_membership(
            self.student,
            "Career Services Student Assistants",
            token
        )

        self.assertRedirects(
            response,
            self.get_detail_url(self.student),
            fetch_redirect_response=False
        )

        self.assertTrue(
            can_access_workspace(self.student)
        )

        self.assertFalse(
            visible_projects_for_user(
                self.student
            ).exists()
        )

        self.assertFalse(
            can_modify_project_tasks(
                self.student,
                self.project_one
            )
        )

    def test_workspace_endpoint_preserves_unchanged_grants(self):
        # Resubmitting the existing authorized
        # membership must preserve valid grants.
        self.assign_membership("Authorized Faculty")

        grant = self.create_project_grant(
            self.project_one,
            ProjectAccess.AccessLevel.CONTRIBUTOR
        )

        self.client.force_login(self.super_admin)

        token = self.get_workspace_token(self.student)

        response = self.submit_workspace_membership(
            self.student,
            "Authorized Faculty",
            token
        )

        self.assertRedirects(
            response,
            self.get_detail_url(self.student),
            fetch_redirect_response=False
        )

        grant.refresh_from_db()

        self.assertEqual(
            grant.access_level,
            ProjectAccess.AccessLevel.CONTRIBUTOR
        )

        self.assertTrue(
            can_modify_project_tasks(
                self.student,
                self.project_one
            )
        )

    def test_workspace_endpoint_restricts_inactive_accounts(self):
        # Inactive accounts may have existing access
        # revoked but cannot receive new membership.
        self.assign_membership("Authorized Faculty")

        self.create_project_grant(self.project_one)

        self.student.is_active = False

        self.student.save(
            update_fields=["is_active"]
        )

        self.client.force_login(self.super_admin)

        response = self.client.get(
            self.get_workspace_url(self.student)
        )

        self.assertEqual(response.status_code, 200)

        form = response.context["form"]

        self.assertEqual(
            {
                value
                for value, label
                in form.fields["membership"].choices
            },
            {"", NO_WORKSPACE_ACCESS}
        )

        token = form["state_token"].value()

        response = self.submit_workspace_membership(
            self.student,
            "Career Services Staff",
            token
        )

        self.assertEqual(response.status_code, 200)

        self.assertIn(
            "membership",
            response.context["form"].errors
        )

        self.assertEqual(
            get_workspace_memberships(self.student),
            ("Authorized Faculty",)
        )

        response = self.submit_workspace_membership(
            self.student,
            NO_WORKSPACE_ACCESS,
            token
        )

        self.assertRedirects(
            response,
            self.get_detail_url(self.student),
            fetch_redirect_response=False
        )

        self.assertEqual(
            get_workspace_memberships(self.student),
            ()
        )

        self.assertFalse(
            ProjectAccess.objects.filter(
                user_id=self.student.pk
            ).exists()
        )

    def test_stale_membership_and_account_status_are_rejected(self):
        # An outdated form must not overwrite newer
        # membership or account activation changes.
        self.client.force_login(self.super_admin)

        token = self.get_workspace_token(self.student)

        # Simulate another administrative operation.
        self.assign_membership("Authorized Faculty")

        self.assert_stale_submission_rejected(
            self.student,
            NO_WORKSPACE_ACCESS,
            token
        )

        # Capture a fresh token before deactivation.
        token = self.get_workspace_token(self.student)

        self.student.is_active = False

        self.student.save(
            update_fields=["is_active"]
        )

        self.assert_stale_submission_rejected(
            self.student,
            NO_WORKSPACE_ACCESS,
            token
        )

    def test_stale_project_grant_changes_are_rejected(self):
        # Detect additions, permission-level changes
        # and deletions of individual project grants.
        self.assign_membership("Authorized Faculty")

        self.client.force_login(self.super_admin)

        token = self.get_workspace_token(self.student)

        grant = self.create_project_grant(
            self.project_one
        )

        # A new project grant invalidates the old form.
        self.assert_stale_submission_rejected(
            self.student,
            NO_WORKSPACE_ACCESS,
            token
        )

        token = self.get_workspace_token(self.student)

        # Changing a grant's level must invalidate
        # the token even when the grant count is unchanged.
        grant.access_level = (
            ProjectAccess.AccessLevel.CONTRIBUTOR
        )

        grant.save(
            update_fields=["access_level"]
        )

        self.assert_stale_submission_rejected(
            self.student,
            NO_WORKSPACE_ACCESS,
            token
        )

        token = self.get_workspace_token(self.student)

        grant.delete()

        # Removing a project grant also invalidates
        # the previously reviewed authorization state.
        self.assert_stale_submission_rejected(
            self.student,
            "Career Services Staff",
            token
        )

    def test_manipulated_and_cross_account_tokens_are_rejected(self):
        # Signed tokens must not be manipulated
        # or transferred to another target account.
        self.client.force_login(self.super_admin)

        token = self.get_workspace_token(self.student)

        manipulated_token = token + "invalid"

        self.assert_stale_submission_rejected(
            self.student,
            "Authorized Faculty",
            manipulated_token
        )

        self.assert_stale_submission_rejected(
            self.admin,
            "Career Services Staff",
            token
        )

        self.assertEqual(
            get_workspace_memberships(self.student),
            ()
        )

        self.assertEqual(
            get_workspace_memberships(self.admin),
            ()
        )

    def test_cross_administrator_state_tokens_are_rejected(self):
        # Even another fully authorized administrator
        # cannot reuse a token issued to someone else.
        self.client.force_login(self.super_admin)

        token = self.get_workspace_token(self.student)

        second_administrator = (
            self.unprivileged_superuser
        )

        second_administrator.profile.role = (
            UserProfile.Role.ADMIN
        )

        second_administrator.profile.save(
            update_fields=["role"]
        )

        self.client.force_login(second_administrator)

        self.assert_stale_submission_rejected(
            self.student,
            "Authorized Faculty",
            token
        )

    def test_expired_workspace_state_tokens_are_rejected(self):
        # Authorization snapshots must expire after
        # the configured review period.
        self.client.force_login(self.super_admin)

        authorization_state = (
            get_workspace_authorization_state(
                self.student
            )
        )

        expired_timestamp = (
            time.time()
            - WORKSPACE_STATE_MAX_AGE
            - 60
        )

        # Generate a genuinely signed but expired token.
        # Avoid real waiting or changing the system clock.
        with patch(
            "django.core.signing.time.time",
            return_value=expired_timestamp
        ):

            token = create_workspace_state_token(
                administrator=self.super_admin,
                account=self.student,
                state=authorization_state
            )

        self.assert_stale_submission_rejected(
            self.student,
            "Authorized Faculty",
            token
        )

    def test_workspace_endpoint_enforces_http_and_csrf_restrictions(self):
        # Missing accounts and unsupported HTTP methods
        # must receive appropriate error responses.
        self.client.force_login(self.super_admin)

        missing_url = reverse(
            "user_management:user_workspace_edit",
            kwargs={"pk": 999999}
        )

        self.assertEqual(
            self.client.get(missing_url).status_code,
            404
        )

        self.assertEqual(
            self.client.post(
                missing_url,
                {"membership": "Authorized Faculty"}
            ).status_code,
            404
        )

        url = self.get_workspace_url(self.student)

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

        # Use a valid authorization snapshot but
        # deliberately omit the CSRF token.
        token = self.get_workspace_token(self.student)

        csrf_client = Client(
            enforce_csrf_checks=True
        )

        csrf_client.force_login(self.super_admin)

        response = csrf_client.post(
            url,
            {
                "membership": "Authorized Faculty",
                "confirm_change": "on",
                "state_token": token,
            }
        )

        self.assertEqual(response.status_code, 403)

        self.assertEqual(
            get_workspace_memberships(self.student),
            ()
        )

    def test_workspace_endpoint_handles_database_failures(self):
        # Database contention must provide safe
        # feedback without exposing internal details.
        self.assign_membership("Authorized Faculty")

        grant = self.create_project_grant(
            self.project_one
        )

        self.client.force_login(self.super_admin)

        token = self.get_workspace_token(self.student)

        original_revision = (
            AccountIdentityLock.objects.get(pk=1).revision
        )

        url = self.get_workspace_url(self.student)

        with patch(
            "core.account_identity."
            "AccountIdentityLock.objects.filter",
            side_effect=OperationalError(
                "database is locked"
            )
        ) as lock_query:

            response = self.submit_workspace_membership(
                self.student,
                NO_WORKSPACE_ACCESS,
                token
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
                "Workspace management is temporarily unavailable"
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

        # Simulate a separate persistence failure.
        with patch(
            "core.user_management_views."
            "change_workspace_membership",
            side_effect=IntegrityError(
                "Simulated database conflict"
            )
        ):

            response = self.submit_workspace_membership(
                self.student,
                NO_WORKSPACE_ACCESS,
                token
            )

        self.assertRedirects(
            response,
            url,
            fetch_redirect_response=False
        )

        self.assertEqual(
            get_workspace_memberships(self.student),
            ("Authorized Faculty",)
        )

        grant.refresh_from_db()

        self.assertEqual(
            grant.access_level,
            ProjectAccess.AccessLevel.VIEWER
        )

        self.assertEqual(
            AccountIdentityLock.objects.get(pk=1).revision,
            original_revision
        )