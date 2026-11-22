
"""
Core views for TaskFlow.

This application manages shared website pages,
including the original TaskFlow homepage.

The homepage preserves the frontend structure
developed during the midterm project.
"""

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from datetime import timedelta
from django.utils import timezone

from django.db.models import Count, Q
from projects.models import Project
from tasks.models import Task
from .forms import ContactMessageForm


def home(request):
    """
    Display database-backed dashboard statistics
    for the authenticated user's projects and tasks.
    """

    context = {
        "total_projects": 0,
        "active_projects": 0,
        "total_tasks": 0,
        "pending_tasks": 0,
        "in_progress_tasks": 0,
        "completed_tasks": 0,
        "recent_tasks": [],
        "upcoming_task_deadlines": [],
        "overdue_tasks": [],
        "upcoming_project_deadlines": [],
        "overdue_projects": [],
        "next_deadline": None,
        "featured_project": None,
        "featured_project_task_count": 0,
        "featured_project_completed_count": 0,
        "featured_project_progress": 0,
        "featured_project_next_task": None,
    }

    if request.user.is_authenticated:

        # Only retrieve projects owned by this user.
        projects = Project.objects.filter(
            owner=request.user
        )

        # Retrieve tasks belonging to those projects.
        tasks = Task.objects.filter(
            project__owner=request.user
        )


        # ----------------------------------------
        # FEATURED PROJECT FOR HOME HERO
        # ----------------------------------------

        # Prefer the most recently updated active
        # project. Otherwise, select the latest
        # unfinished project or most recent project.
        featured_project = (
            projects
            .filter(status=Project.Status.ACTIVE)
            .order_by("-updated_at", "-pk")
            .first()
        )

        if featured_project is None:
            featured_project = (
                projects
                .exclude(status=Project.Status.COMPLETED)
                .order_by("-updated_at", "-pk")
                .first()
            )

        if featured_project is None:
            featured_project = (
                projects
                .order_by("-updated_at", "-pk")
                .first()
            )

        if featured_project is not None:
            featured_tasks = tasks.filter(
                project=featured_project
            )

            summary = featured_tasks.aggregate(
                total=Count("pk"),
                completed=Count(
                    "pk",
                    filter=Q(
                        status=Task.Status.COMPLETED
                    )
                ),
            )

            total = summary["total"]
            completed = summary["completed"]

            progress = (
                round((completed / total) * 100)
                if total > 0
                else 0
            )

            next_task = (
                featured_tasks
                .exclude(status=Task.Status.COMPLETED)
                .order_by("due_date", "pk")
                .first()
            )

            context.update({
                "featured_project": featured_project,
                "featured_project_task_count": total,
                "featured_project_completed_count": completed,
                "featured_project_progress": progress,
                "featured_project_next_task": next_task,
            })

        # Retrieve the five most recently updated tasks
        # belonging to this user's projects.
        context["recent_tasks"] = (
            tasks
            .select_related("project", "assignee")
            .order_by("-updated_at", "-pk")[:5]
        )

        # Calculate project statistics.
        context.update(
            projects.aggregate(
                total_projects=Count("pk"),
                active_projects=Count(
                    "pk",
                    filter=Q(status=Project.Status.ACTIVE)
                ),
            )
        )

        # Calculate task statistics.
        context.update(
            tasks.aggregate(
                total_tasks=Count("pk"),
                pending_tasks=Count(
                    "pk",
                    filter=Q(status=Task.Status.PENDING)
                ),
                in_progress_tasks=Count(
                    "pk",
                    filter=Q(status=Task.Status.IN_PROGRESS)
                ),
                completed_tasks=Count(
                    "pk",
                    filter=Q(status=Task.Status.COMPLETED)
                ),
            )
        )

        # ----------------------------------------
        # UPCOMING DEADLINES
        # ----------------------------------------

        today = timezone.localdate()
        deadline_limit = today + timedelta(days=7)

        # Incomplete tasks belonging to the user.
        incomplete_tasks = tasks.exclude(
            status=Task.Status.COMPLETED
        )

        # Projects that are not completed.
        incomplete_projects = projects.exclude(
            status=Project.Status.COMPLETED
        )

        # Tasks due within the next 7 days.
        upcoming_task_deadlines = (
            incomplete_tasks
            .filter(
                due_date__gte=today,
                due_date__lte=deadline_limit
            )
            .select_related("project", "assignee")
            .order_by("due_date", "pk")[:5]
        )

        # Tasks whose deadlines have passed.
        overdue_tasks = (
            incomplete_tasks
            .filter(due_date__lt=today)
            .select_related("project", "assignee")
            .order_by("due_date", "pk")[:5]
        )

        # Projects due within the next 7 days.
        upcoming_project_deadlines = (
            incomplete_projects
            .filter(
                deadline__gte=today,
                deadline__lte=deadline_limit
            )
            .order_by("deadline", "pk")[:5]
        )

        # Projects whose deadlines have passed.
        overdue_projects = (
            incomplete_projects
            .filter(deadline__lt=today)
            .order_by("deadline", "pk")[:5]
        )

        # Make deadline information available
        # to the Django Home template.
        context.update({
            "upcoming_task_deadlines": upcoming_task_deadlines,
            "overdue_tasks": overdue_tasks,
            "upcoming_project_deadlines": upcoming_project_deadlines,
            "overdue_projects": overdue_projects,
        })


        # ----------------------------------------
        # NEXT SCHEDULED DEADLINE
        # ----------------------------------------

        # Find the nearest upcoming incomplete task.
        next_task = (
            incomplete_tasks
            .filter(due_date__gte=today)
            .select_related("project")
            .order_by("due_date", "pk")
            .first()
        )

        # Find the nearest upcoming unfinished project.
        next_project = (
            incomplete_projects
            .filter(deadline__gte=today)
            .order_by("deadline", "pk")
            .first()
        )

        # Select whichever deadline occurs first.
        if next_task and (
            not next_project
            or next_task.due_date <= next_project.deadline
        ):
            context["next_deadline"] = {
                "type": "Task",
                "title": next_task.name,
                "due_date": next_task.due_date,
                "project": next_task.project,
                "priority": next_task.get_priority_display(),
            }

        elif next_project:
            context["next_deadline"] = {
                "type": "Project",
                "title": next_project.name,
                "due_date": next_project.deadline,
                "project": next_project,
                "priority": None,
            }

    return render(
        request,
        "core/home.html",
        context
    )

def about(request):
    """
    Render the original TaskFlow About page.

    The page preserves the midterm project's
    Career Services information, team profiles,
    and supporting content.

    Its shared navigation and layout are
    provided by Django's layout.html.
    """
    return render(request, "core/about.html")

@require_http_methods(["GET", "POST"])
def contact(request):
    """
    Display the Contact page and process submissions.

    GET: Render the original TaskFlow Contact page.
    POST: Validate and save the submitted message.
    """

    if request.method == "POST":

        # Validate the submitted data on the server.
        form = ContactMessageForm(request.POST)

        if form.is_valid():

            # Save the validated message to SQLite.
            form.save()

            return JsonResponse(
                {
                    "success": True,
                    "message": "Your message was saved successfully."
                },
                status=201
            )

        # Return validation errors without saving.
        return JsonResponse(
            {
                "success": False,
                "errors": {
                    field: list(errors)
                    for field, errors in form.errors.items()
                }
            },
            status=400
        )

    # Display the Contact page for GET requests.
    return render(request, "core/contact.html")