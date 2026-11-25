
"""
Automated tests for Career Services project permissions.

Verify that authorized staff have office-wide access
without requiring ownership of individual projects.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from .permissions import can_modify_project_tasks
from .models import Project
from datetime import timedelta
from django.utils import timezone


class CareerServicesOfficeWideAccessTests(TestCase):
    """
    Verify that non-owner Career Services staff can
    view and manage projects across the office.
    """

    @classmethod
    def setUpTestData(cls):
        # Create the authorized Career Services group.
        staff_group, _ = Group.objects.get_or_create(
            name="Career Services Staff"
        )

        User = get_user_model()

        # Create two separate, non-superuser staff accounts.
        cls.owner = User.objects.create_user(
            username="project_owner_test"
        )

        cls.other_staff = User.objects.create_user(
            username="non_owner_staff_test"
        )

        cls.owner.groups.add(staff_group)
        cls.other_staff.groups.add(staff_group)

        # The project belongs to the first account only.
        cls.project = Project.objects.create(
            owner=cls.owner,
            name="Career Services Authorization Test"
        )

    def test_non_owner_staff_can_view_project_listing(self):
        """Staff can see projects they do not own."""

        self.client.force_login(self.other_staff)

        response = self.client.get(
            reverse("projects:project_list")
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            self.project.name
        )

    def test_non_owner_staff_can_view_project_details(self):
        """Staff can open another account's project."""

        self.client.force_login(self.other_staff)

        response = self.client.get(
            reverse(
                "projects:project_detail",
                args=[self.project.pk]
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            self.project.name
        )

    def test_non_owner_staff_can_open_project_edit_form(self):
        """Staff can edit projects regardless of ownership."""

        self.client.force_login(self.other_staff)

        response = self.client.get(
            reverse(
                "projects:project_update",
                args=[self.project.pk]
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Save Changes"
        )

    def test_non_owner_staff_can_view_project_analytics(self):
        """
        Career Services staff can access analytics for
        office projects they do not personally own.
        """
        self.client.force_login(self.other_staff)

        response = self.client.get(
            reverse("projects:analytics")
        )

        # The Analytics dashboard must be accessible.
        self.assertEqual(response.status_code, 200)

        # Non-owner staff must see the office project.
        visible_projects = list(response.context["projects"])

        self.assertIn(self.project, visible_projects)

        self.assertEqual(
            response.context["total_projects"],
            1
        )

class ScopedProjectVisibilityTests(TestCase):
    """
    Verify that faculty and student assistants can see
    only explicitly authorized internal projects.
    """

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        cls.owner = User.objects.create_user(
            username="scoped_project_owner"
        )
        cls.faculty = User.objects.create_user(
            username="authorized_faculty_test"
        )
        cls.assistant = User.objects.create_user(
            username="authorized_assistant_test"
        )
        cls.student = User.objects.create_user(
            username="ordinary_student_test"
        )

        faculty_group, _ = Group.objects.get_or_create(
            name="Authorized Faculty"
        )
        assistant_group, _ = Group.objects.get_or_create(
            name="Career Services Student Assistants"
        )

        cls.faculty.groups.add(faculty_group)
        cls.assistant.groups.add(assistant_group)

        cls.project = Project.objects.create(
            owner=cls.owner,
            name="Authorized Career Workshop"
        )
        cls.other_project = Project.objects.create(
            owner=cls.owner,
            name="Confidential Office Project"
        )

        from .models import ProjectAccess

        ProjectAccess.objects.create(
            project=cls.project,
            user=cls.faculty,
            access_level=ProjectAccess.AccessLevel.VIEWER
        )

        ProjectAccess.objects.create(
            project=cls.project,
            user=cls.assistant,
            access_level=ProjectAccess.AccessLevel.CONTRIBUTOR
        )

        # A grant alone must not authorize an ordinary student.
        ProjectAccess.objects.create(
            project=cls.project,
            user=cls.student,
            access_level=ProjectAccess.AccessLevel.VIEWER
        )

    def test_faculty_sees_only_granted_project(self):
        """Authorized faculty have project-specific visibility."""
        self.client.force_login(self.faculty)

        response = self.client.get(
            reverse("projects:project_list")
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.project.name)
        self.assertNotContains(response, self.other_project.name)

    def test_assistant_sees_only_granted_project(self):
        """Authorized assistants have project-specific visibility."""
        self.client.force_login(self.assistant)

        response = self.client.get(
            reverse("projects:project_list")
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.project.name)
        self.assertNotContains(response, self.other_project.name)

    def test_faculty_cannot_open_ungranted_project(self):
        """A faculty account cannot bypass project scoping."""
        self.client.force_login(self.faculty)

        response = self.client.get(
            reverse(
                "projects:project_detail",
                args=[self.other_project.pk]
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_student_grant_does_not_bypass_workspace_security(self):
        """Ordinary students cannot access internal projects."""
        self.client.force_login(self.student)

        response = self.client.get(
            reverse("projects:project_list")
        )

        self.assertEqual(response.status_code, 403)

    def test_viewer_cannot_modify_project_tasks(self):
        """Viewer access must not permit task modifications."""

        self.assertFalse(
            can_modify_project_tasks(
                self.faculty,
                self.project
            )
        )

    def test_contributor_can_modify_only_granted_project(self):
        """Contributors can modify tasks only in granted projects."""

        self.assertTrue(
            can_modify_project_tasks(
                self.assistant,
                self.project
            )
        )

        self.assertFalse(
            can_modify_project_tasks(
                self.assistant,
                self.other_project
            )
        )

    def test_student_grant_cannot_allow_task_modification(self):
        """A project grant cannot bypass workspace authorization."""

        self.assertFalse(
            can_modify_project_tasks(
                self.student,
                self.project
            )
        )

    def test_viewer_cannot_open_task_creation(self):
        """Viewers cannot create tasks in assigned projects."""
        self.client.force_login(self.faculty)

        response = self.client.get(
            reverse(
                "projects:task_create",
                args=[self.project.pk]
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_contributor_can_open_task_creation(self):
        """Contributors can create tasks in assigned projects."""
        self.client.force_login(self.assistant)

        response = self.client.get(
            reverse(
                "projects:task_create",
                args=[self.project.pk]
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_contributor_cannot_create_tasks_in_ungranted_project(self):
        """Contributors cannot access unrelated project tasks."""
        self.client.force_login(self.assistant)

        response = self.client.get(
            reverse(
                "projects:task_create",
                args=[self.other_project.pk]
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_viewer_cannot_open_task_editing(self):
        """Viewers cannot edit tasks in granted projects."""
        from tasks.models import Task

        task = Task.objects.create(
            project=self.project,
            name="Viewer Permission Test Task",
            due_date=timezone.localdate() + timedelta(days=7)
        )

        self.client.force_login(self.faculty)

        response = self.client.get(
            reverse(
                "projects:task_update",
                args=[self.project.pk, task.pk]
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_contributor_can_open_task_editing(self):
        """Contributors can edit tasks in granted projects."""
        from tasks.models import Task

        task = Task.objects.create(
            project=self.project,
            name="Contributor Permission Test Task",
            due_date=timezone.localdate() + timedelta(days=7)
        )

        self.client.force_login(self.assistant)

        response = self.client.get(
            reverse(
                "projects:task_update",
                args=[self.project.pk, task.pk]
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_contributor_cannot_edit_ungranted_project_task(self):
        """Contributors cannot edit tasks in unrelated projects."""
        from tasks.models import Task

        task = Task.objects.create(
            project=self.other_project,
            name="Confidential Project Task",
            due_date=timezone.localdate() + timedelta(days=7)
        )

        self.client.force_login(self.assistant)

        response = self.client.get(
            reverse(
                "projects:task_update",
                args=[self.other_project.pk, task.pk]
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_viewer_cannot_complete_task(self):
        """
        Viewers cannot complete tasks, and unauthorized
        POST requests must leave task status unchanged.
        """
        from tasks.models import Task

        # Create a pending task in the isolated test database.
        task = Task.objects.create(
            project=self.project,
            name="Viewer Completion Security Test",
            status="pending",
            due_date=timezone.localdate() + timedelta(days=7)
        )

        # This faculty account has Viewer access only.
        self.client.force_login(self.faculty)

        response = self.client.post(
            reverse(
                "projects:task_complete",
                args=[self.project.pk, task.pk]
            )
        )

        # The request must be denied.
        self.assertEqual(response.status_code, 403)

        # Confirm that no unauthorized modification occurred.
        task.refresh_from_db()
        self.assertEqual(task.status, "pending")

    def test_contributor_can_complete_task(self):
        """
        Contributors can complete tasks in projects
        where they have explicit Contributor access.
        """
        from tasks.models import Task

        # Create a pending task in the isolated test database.
        task = Task.objects.create(
            project=self.project,
            name="Contributor Completion Security Test",
            status="pending",
            due_date=timezone.localdate() + timedelta(days=7)
        )

        # This student assistant has Contributor access.
        self.client.force_login(self.assistant)

        response = self.client.post(
            reverse(
                "projects:task_complete",
                args=[self.project.pk, task.pk]
            )
        )

        # Successful completion redirects to project details.
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            reverse(
                "projects:project_detail",
                args=[self.project.pk]
            )
        )

        # Verify that the database records the completion.
        task.refresh_from_db()
        self.assertEqual(task.status, "completed")

    def test_contributor_cannot_complete_ungranted_project_task(self):
        """
        Contributors cannot complete tasks belonging
        to projects outside their authorized scope.
        """
        from tasks.models import Task

        # Create a pending task in an unrelated project.
        task = Task.objects.create(
            project=self.other_project,
            name="Confidential Completion Security Test",
            status="pending",
            due_date=timezone.localdate() + timedelta(days=7)
        )

        # This assistant has Contributor access only
        # to self.project, not self.other_project.
        self.client.force_login(self.assistant)

        response = self.client.post(
            reverse(
                "projects:task_complete",
                args=[self.other_project.pk, task.pk]
            )
        )

        # Do not reveal inaccessible project resources.
        self.assertEqual(response.status_code, 404)

        # Verify that the task remains unchanged.
        task.refresh_from_db()
        self.assertEqual(task.status, "pending")

    def test_viewer_cannot_delete_task(self):
        """
        Viewer access must not permit task deletion.
        Unauthorized requests must preserve the task.
        """
        from tasks.models import Task

        # Create a task in Django's isolated test database.
        task = Task.objects.create(
            project=self.project,
            name="Viewer Deletion Security Test",
            due_date=timezone.localdate() + timedelta(days=7)
        )

        self.client.force_login(self.faculty)

        # Attempt deletion using the required POST method.
        response = self.client.post(
            reverse(
                "projects:task_delete",
                args=[self.project.pk, task.pk]
            )
        )

        # Viewer permissions must not permit deletion.
        self.assertEqual(response.status_code, 403)

        # Confirm that the task still exists.
        self.assertTrue(
            Task.objects.filter(pk=task.pk).exists()
        )

    def test_contributor_can_delete_task(self):
        """
        Contributors may delete tasks in projects
        where they have explicit Contributor access.
        """
        from tasks.models import Task

        # Create a task in Django's isolated test database.
        task = Task.objects.create(
            project=self.project,
            name="Contributor Deletion Security Test",
            due_date=timezone.localdate() + timedelta(days=7)
        )

        task_id = task.pk

        # This assistant has Contributor access to the project.
        self.client.force_login(self.assistant)

        response = self.client.post(
            reverse(
                "projects:task_delete",
                args=[self.project.pk, task_id]
            )
        )

        # Successful deletion redirects to project details.
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            reverse(
                "projects:project_detail",
                args=[self.project.pk]
            )
        )

        # Confirm that the task was actually deleted.
        self.assertFalse(
            Task.objects.filter(pk=task_id).exists()
        )

    def test_contributor_cannot_delete_ungranted_project_task(self):
        """
        Contributors cannot delete tasks belonging
        to projects outside their authorized scope.
        """
        from tasks.models import Task

        # Create a task in a project without a Contributor grant.
        task = Task.objects.create(
            project=self.other_project,
            name="Cross-Project Deletion Security Test",
            due_date=timezone.localdate() + timedelta(days=7)
        )

        task_id = task.pk

        # This assistant has access to self.project only.
        self.client.force_login(self.assistant)

        response = self.client.post(
            reverse(
                "projects:task_delete",
                args=[self.other_project.pk, task_id]
            )
        )

        # Inaccessible projects must not be exposed.
        self.assertEqual(response.status_code, 404)

        # The unauthorized attempt must not delete the task.
        self.assertTrue(
            Task.objects.filter(pk=task_id).exists()
        )

    def test_contributor_analytics_only_shows_granted_projects(self):
        """
        Contributors must see analytics only for projects
        where they have explicit access.
        """
        # This assistant has access to self.project,
        # but not to self.other_project.
        self.client.force_login(self.assistant)

        response = self.client.get(
            reverse("projects:analytics")
        )

        # The authorized Analytics dashboard must load.
        self.assertEqual(response.status_code, 200)

        # Inspect the projects supplied to the template.
        visible_projects = list(response.context["projects"])

        # The granted project must be visible.
        self.assertIn(self.project, visible_projects)

        # The ungranted project must remain hidden.
        self.assertNotIn(self.other_project, visible_projects)

        # Only one authorized project should be counted.
        self.assertEqual(
            response.context["total_projects"],
            1
        )

    def test_contributor_cannot_filter_analytics_by_ungranted_project(self):
        """
        Contributors cannot access analytics for projects
        outside their explicitly granted scope.
        """
        self.client.force_login(self.assistant)

        # Attempt to access analytics for an ungranted project.
        response = self.client.get(
            reverse("projects:analytics"),
            {"project": self.other_project.pk}
        )

        # Do not expose analytics for inaccessible projects.
        self.assertEqual(response.status_code, 404)

    def test_contributor_analytics_hides_unrelated_team_members(self):
        """
        Contributors see team members associated with
        granted projects, not unrelated projects.
        """
        from core.models import TeamMember

        # Use two distinct seeded Career Services team members.
        members = list(
            TeamMember.objects.filter(
                is_active=True
            ).order_by("pk")[:2]
        )

        self.assertEqual(len(members), 2)

        authorized_member, unrelated_member = members

        # Assign one manager to the granted project.
        self.project.project_manager = authorized_member
        self.project.save(update_fields=["project_manager"])

        # Assign another manager to the ungranted project.
        self.other_project.project_manager = unrelated_member
        self.other_project.save(
            update_fields=["project_manager"]
        )

        self.client.force_login(self.assistant)

        response = self.client.get(
            reverse("projects:analytics")
        )

        self.assertEqual(response.status_code, 200)

        # Inspect the team members exposed to the template.
        visible_member_ids = {
            member.pk
            for member in response.context["team_workload"]
        }

        # Include the granted project's manager.
        self.assertIn(
            authorized_member.pk,
            visible_member_ids
        )

        # Exclude the ungranted project's manager.
        self.assertNotIn(
            unrelated_member.pk,
            visible_member_ids
        )

    def test_contributor_analytics_excludes_ungranted_project_tasks(self):
        """
        Analytics statistics must exclude tasks from
        projects outside the Contributor's access scope.
        """
        from tasks.models import Task

        # Create a task in the authorized project.
        Task.objects.create(
            project=self.project,
            name="Authorized Analytics Task",
            status="pending",
            due_date=timezone.localdate() + timedelta(days=7)
        )

        # Create another task in an unauthorized project.
        Task.objects.create(
            project=self.other_project,
            name="Confidential Analytics Task",
            status="pending",
            due_date=timezone.localdate() + timedelta(days=7)
        )

        self.client.force_login(self.assistant)

        response = self.client.get(
            reverse("projects:analytics")
        )

        self.assertEqual(response.status_code, 200)

        statistics = response.context["statistics"]

        # Only tasks from the granted project may be counted.
        authorized_tasks = Task.objects.filter(
            project=self.project
        )

        self.assertEqual(
            statistics["total"],
            authorized_tasks.count()
        )

        self.assertEqual(
            statistics["pending"],
            authorized_tasks.filter(status="pending").count()
        )

    def test_contributor_analytics_workload_excludes_ungranted_tasks(self):
        """
        Team workload statistics must count assignments
        only from projects the Contributor can access.
        """
        from core.models import TeamMember
        from tasks.models import Task

        member = TeamMember.objects.filter(
            is_active=True
        ).order_by("pk").first()

        self.assertIsNotNone(member)

        # Associate the member with the granted project.
        self.project.project_manager = member
        self.project.save(update_fields=["project_manager"])

        # Create an authorized completed assignment.
        Task.objects.create(
            project=self.project,
            name="Authorized Workload Task",
            assignee=member,
            status="completed",
            due_date=timezone.localdate() + timedelta(days=7)
        )

        # Create an unauthorized assignment for the same member.
        Task.objects.create(
            project=self.other_project,
            name="Confidential Workload Task",
            assignee=member,
            status="pending",
            due_date=timezone.localdate() + timedelta(days=7)
        )

        self.client.force_login(self.assistant)

        response = self.client.get(
            reverse("projects:analytics")
        )

        self.assertEqual(response.status_code, 200)

        # Retrieve the member's visible workload statistics.
        workload = next(
            item
            for item in response.context["team_workload"]
            if item.pk == member.pk
        )

        # The unauthorized assignment must not be counted.
        self.assertEqual(workload.assigned_total, 1)
        self.assertEqual(workload.assigned_completed, 1)

        # Expandable task lists must also remain scoped.
        self.assertEqual(
            len(workload.assigned_task_list),
            1
        )
        self.assertEqual(
            workload.assigned_task_list[0].project_id,
            self.project.pk
        )