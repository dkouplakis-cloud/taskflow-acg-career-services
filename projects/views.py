"""
Views for displaying and managing user projects.

Project information is accessible only to
authenticated users with appropriate ownership.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_http_methods
from core.models import TeamMember
from django.db.models import Count, Q
from django.utils import timezone
from tasks.models import Task
from collections import defaultdict
from .forms import ProjectForm
from .models import Project

@login_required
def project_list(request):
    """
    Display projects belonging to the authenticated user.

    Database-level filtering prevents projects belonging
    to other users from appearing in this list.
    """

    # Retrieve only projects owned by the current user.
    projects = Project.objects.filter(owner=request.user)

    context = {
        'projects': projects,
    }

    return render(
        request,
        'projects/project_list.html',
        context
    )


@login_required
@require_http_methods(["GET", "POST"])
def project_create(request):
    """
    Allow an authenticated user to create a project.

    GET displays an empty form.
    POST validates and saves the submitted information.
    """

    if request.method == 'POST':
        form = ProjectForm(request.POST)
        
        if form.is_valid():
            # Assign project ownership on the server.
            project = form.save(commit=False)
            project.owner = request.user
            project.save()

            # Save the selected project collaborators.
            form.save_m2m()

            # Confirm successful creation.
            messages.success(
                request,
                'Your project was created successfully.'
            )

            return redirect('projects:project_list')

    else:
        # Display an empty form for a new project.
        form = ProjectForm()

    # Reuse this template for creation and future editing.
    context = {
        'form': form,
        'page_title': 'Create a Project',
        'submit_label': 'Create Project',
    }

    return render(
        request,
        'projects/project_form.html',
        context
    )

@login_required
@require_http_methods(["GET"])
def project_detail(request, project_id):
    """
    Display an individual project and its tasks.

    Only the authenticated project's owner
    can access its information.

    Tasks are retrieved through the existing
    Project-to-Task relationship.
    """

    # Retrieve the project only if it belongs
    # to the currently authenticated user.
    project = get_object_or_404(
        Project.objects.prefetch_related('tasks'),
        pk=project_id,
        owner=request.user
    )

    
    # Retrieve the project's tasks.
    tasks = list(project.tasks.all())

    # Calculate task statistics dynamically.
    total_tasks = len(tasks)

    pending_tasks = sum(
        task.status == "pending"
        for task in tasks
    )

    in_progress_tasks = sum(
        task.status == "in_progress"
        for task in tasks
    )

    completed_tasks = sum(
        task.status == "completed"
        for task in tasks
    )

    # Calculate the overall completion percentage.
    completion_percentage = (
        round((completed_tasks / total_tasks) * 100)
        if total_tasks > 0
        else 0
    )

    task_stats = {
        "total": total_tasks,
        "pending": pending_tasks,
        "in_progress": in_progress_tasks,
        "completed": completed_tasks,
        "completion_percentage": completion_percentage,
    }
    

    # ==========================================
    # TASK SEARCH, FILTERING AND SORTING
    # ==========================================

    # Read and safely normalize URL parameters.
    search_query = request.GET.get("q", "").strip()[:200]
    status_filter = request.GET.get("status", "")
    priority_filter = request.GET.get("priority", "")
    sort_order = request.GET.get("sort", "due_soon")

    # Start with tasks belonging to this project.
    # Project ownership is already verified above.
    visible_tasks = project.tasks.select_related(
        "assignee"
    ).all()

    # Search task names and descriptions.
    if search_query:
        visible_tasks = visible_tasks.filter(
            Q(name__icontains=search_query)
            | Q(description__icontains=search_query)
        )

    # Filter by task status.
    allowed_statuses = (
        "pending",
        "in_progress",
        "completed",
    )

    if status_filter in allowed_statuses:
        visible_tasks = visible_tasks.filter(
            status=status_filter
        )

    # Filter by priority.
    allowed_priorities = (
        "low",
        "medium",
        "high",
    )

    if priority_filter in allowed_priorities:
        visible_tasks = visible_tasks.filter(
            priority=priority_filter
        )

    # Use an allowlist for safe database sorting.
    sort_options = {
        "due_soon": ("due_date", "pk"),
        "due_late": ("-due_date", "-pk"),
        "name_az": ("name", "pk"),
        "name_za": ("-name", "-pk"),
    }

    if sort_order not in sort_options:
        sort_order = "due_soon"

    visible_tasks = visible_tasks.order_by(
        *sort_options[sort_order]
    )

    # Number of tasks matching the current filters.
    visible_task_count = visible_tasks.count()

    # Retain the selected filters in the interface.
    task_filters = {
        "q": search_query,
        "status": status_filter,
        "priority": priority_filter,
        "sort": sort_order,
    }

    context = {
        "project": project,
        "tasks": tasks,
        "task_stats": task_stats,
        "visible_tasks": visible_tasks,
        "visible_task_count": visible_task_count,
        "task_filters": task_filters,
    }

    return render(
        request,
        "projects/project_detail.html",
        context
    )

@login_required
@require_http_methods(["GET", "POST"])
def project_update(request, project_id):
    """
    Allow the owner to edit an existing project.

    GET displays the current project information.
    POST validates and saves the updated information.
    """

    # Only the project's owner can access this page.
    project = get_object_or_404(
        Project,
        pk=project_id,
        owner=request.user
    )

    if request.method == "POST":
        form = ProjectForm(
            request.POST,
            instance=project
        )

        if form.is_valid():
            # Save project fields and collaborators.
            form.save()

            messages.success(
                request,
                "Your project was updated successfully."
            )

            return redirect(
                "projects:project_detail",
                project_id=project.pk
            )

    else:
        # Prepopulate the form with existing project data.
        form = ProjectForm(instance=project)

    context = {
        "form": form,
        "project": project,
        "page_title": "Edit Project",
        "submit_label": "Save Changes",
    }

    return render(
        request,
        "projects/project_form.html",
        context
    )

@login_required
def analytics_dashboard(request):
    """
    Display task analytics for projects owned
    by the currently authenticated user.

    Supports filtering by a specific project.
    """

    # Only include the logged-in user's projects.
    projects = Project.objects.filter(
        owner=request.user
    ).order_by("name")

    # Initially display analytics for all projects.
    selected_project = None

    # Optional project filter from the URL.
    project_id = request.GET.get("project")

    if project_id:
        selected_project = get_object_or_404(
            projects,
            pk=project_id
        )

    # Only retrieve tasks from owned projects.
    tasks = Task.objects.filter(
        project__owner=request.user
    )

    # Filter tasks if a project was selected.
    if selected_project is not None:
        tasks = tasks.filter(
            project=selected_project
        )

    # Calculate task status and priority statistics.
    statistics = tasks.aggregate(
        total=Count("id"),

        pending=Count(
            "id",
            filter=Q(status="pending")
        ),

        in_progress=Count(
            "id",
            filter=Q(status="in_progress")
        ),

        completed=Count(
            "id",
            filter=Q(status="completed")
        ),

        high_priority=Count(
            "id",
            filter=Q(priority="high")
        ),

        medium_priority=Count(
            "id",
            filter=Q(priority="medium")
        ),

        low_priority=Count(
            "id",
            filter=Q(priority="low")
        ),

        overdue=Count(
            "id",
            filter=(
                Q(due_date__lt=timezone.localdate())
                & ~Q(status="completed")
            )
        )
    )

    total_tasks = statistics["total"]
    completed_tasks = statistics["completed"]

    # Safely calculate completion rate.
    completion_rate = (
        round(completed_tasks / total_tasks * 100)
        if total_tasks > 0
        else 0
    )

    # Calculate workload for each Career Services team member.
    # Only count tasks from projects owned by this user.

    workload_filter = Q(
        assigned_tasks__project__owner=request.user
    )

    # Respect the selected project filter.
    if selected_project is not None:
        workload_filter &= Q(
            assigned_tasks__project=selected_project
        )

    
    # Start with the active Career Services team.
    team_members = TeamMember.objects.filter(
        is_active=True
    )

    # When filtering by project, show its manager,
    # collaborators and any existing task assignees.
    if selected_project is not None:

        member_ids = set(
            selected_project.collaborators.values_list(
                "pk",
                flat=True
            )
        )

        if selected_project.project_manager_id:
            member_ids.add(
                selected_project.project_manager_id
            )

        # Keep previously assigned members visible,
        # even if the project team later changes.
        member_ids.update(
            Task.objects.filter(
                project=selected_project,
                assignee__isnull=False
            ).values_list(
                "assignee_id",
                flat=True
            )
        )

        team_members = team_members.filter(
            pk__in=member_ids
        )

    team_workload = team_members.annotate(

        assigned_total=Count(
            "assigned_tasks",
            filter=workload_filter,
            distinct=True
        ),
        assigned_completed=Count(
            "assigned_tasks",
            filter=(
                workload_filter
                & Q(assigned_tasks__status="completed")
            ),
            distinct=True
        )
    ).order_by("full_name")


    # Prepare task lists for the expandable team cards.
    # The existing tasks queryset is already restricted
    # to projects owned by the authenticated user
    # and respects the selected project filter.

    assigned_task_map = defaultdict(list)
    overseen_task_map = defaultdict(list)

    visible_tasks = tasks.select_related(
        "project",
        "assignee"
    ).order_by("due_date", "pk")

    for task in visible_tasks:

        # Tasks assigned directly to a team member.
        if task.assignee_id:
            assigned_task_map[
                task.assignee_id
            ].append(task)

        # Tasks overseen by the project manager.
        if task.project.project_manager_id:
            overseen_task_map[
                task.project.project_manager_id
            ].append(task)

    # Calculate each team member's completion percentage.
    # These values are calculated for display only.
    
    for member in team_workload:

        # Tasks directly assigned to this member.
        member.assigned_task_list = (
            assigned_task_map.get(member.pk, [])
        )

        # Tasks belonging to projects managed by
        # this member, even when assigned to others.
        member.overseen_task_list = (
            overseen_task_map.get(member.pk, [])
        )

        member.overseen_task_count = len(
            member.overseen_task_list
        )

        # Direct-assignment completion rate.
        member.completion_rate = (
            round(
                member.assigned_completed
                / member.assigned_total
                * 100
            )
            if member.assigned_total > 0
            else 0
        )

    context = {
        "projects": projects,
        "selected_project": selected_project,
        "total_projects": projects.count(),
        "statistics": statistics,
        "completion_rate": completion_rate,
        "team_workload": team_workload,
    }

    return render(
        request,
        "projects/analytics.html",
        context
    )