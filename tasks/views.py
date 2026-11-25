
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.http import require_http_methods
from .models import Task
from projects.models import Project
from .forms import TaskForm
from core.permissions import workspace_required

from django.core.exceptions import PermissionDenied
from projects.permissions import (
    can_modify_project_tasks,
    visible_projects_for_user,
)

@workspace_required
@require_http_methods(["GET", "POST"])
def task_create(request, project_id):
    """
    Create a task inside a project owned by
    the currently authenticated user.

    GET displays the task creation form.
    POST validates and saves the new task.
    """

    # Retrieve only projects visible to this workspace member.
    project = get_object_or_404(
        visible_projects_for_user(request.user),
        pk=project_id
    )

    # Viewing a project does not automatically grant
    # permission to create tasks within it.
    if not can_modify_project_tasks(request.user, project):
        raise PermissionDenied(
            "You do not have permission to create "
            "tasks in this project."
        )

    if request.method == "POST":

        # Pass the project to restrict eligible assignees.
        form = TaskForm(
            request.POST,
            project=project
        )

        if form.is_valid():

            # Assign the project on the server.
            # Never trust a submitted project ID.
            task = form.save(commit=False)
            task.project = project
            task.save()

            messages.success(
                request,
                "Your task was created successfully."
            )

            # Return to the project's task workspace.
            return redirect(
                "projects:project_detail",
                project_id=project.pk
            )

    else:

        # Display an empty task creation form.
        form = TaskForm(
            project=project
        )

    context = {
        "form": form,
        "project": project,
        "page_title": "Create a Task",
        "submit_label": "Create Task",
    }

    return render(
        request,
        "tasks/task_form.html",
        context
    )

"""
Edit a task within an authorized Career Services project.

Staff may edit tasks across all office projects.
Contributors may edit tasks in explicitly granted
projects. Viewers cannot modify tasks.
"""

@workspace_required
@require_http_methods(["GET", "POST"])
def task_update(request, project_id, task_id):
    """
    Edit an existing task belonging to a project
    owned by the authenticated user.
    """

    # Verify that this user is allowed to access the project.
    project = get_object_or_404(
        visible_projects_for_user(request.user),
        pk=project_id
    )

    # Viewing a project does not grant task-editing rights.
    if not can_modify_project_tasks(request.user, project):
        raise PermissionDenied(
            "You do not have permission to edit "
            "tasks in this project."
        )

    task = get_object_or_404(
        Task,
        pk=task_id,
        project=project
    )

    if request.method == "POST":
        form = TaskForm(
            request.POST,
            instance=task,
            project=project
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Task updated successfully."
            )

            return redirect(
                "projects:project_detail",
                project_id=project.pk
            )

    else:
        form = TaskForm(
            instance=task,
            project=project
        )

    context = {
        "form": form,
        "project": project,
        "task": task,
        "page_title": "Edit Task",
        "submit_label": "Save Changes",
    }

    return render(
        request,
        "tasks/task_form.html",
        context
    )


@workspace_required
@require_http_methods(["POST"])
def task_complete(request, project_id, task_id):
    """
    Mark a task as completed.

    Only the owner of the parent project
    can perform this action.
    """

    # Retrieve only projects visible to this workspace member.
    project = get_object_or_404(
        visible_projects_for_user(request.user),
        pk=project_id
    )

    # Only staff and explicitly authorized Contributors
    # may change the status of tasks in this project.
    if not can_modify_project_tasks(request.user, project):
        raise PermissionDenied(
            "You do not have permission to complete "
            "tasks in this project."
        )

    task = get_object_or_404(
        Task,
        pk=task_id,
        project=project
    )

    if task.status != "completed":

        task.status = "completed"

        task.save(
            update_fields=["status", "updated_at"]
        )

        messages.success(
            request,
            f'"{task.name}" marked as completed.'
        )

    else:

        messages.info(
            request,
            "This task is already completed."
        )

    return redirect(
        "projects:project_detail",
        project_id=project.pk
    )


@workspace_required
@require_http_methods(["POST"])
def task_delete(request, project_id, task_id):
    """
    Delete a task within an authorized Career Services project.

    Career Services staff may delete tasks across all projects.
    Contributors may delete tasks in explicitly granted projects.
    Viewers cannot delete tasks.

    Only POST requests are permitted.
    """

    # Retrieve only projects visible to this workspace member.
    project = get_object_or_404(
        visible_projects_for_user(request.user),
        pk=project_id
    )

    # Verify modification permissions before deleting anything.
    if not can_modify_project_tasks(request.user, project):
        raise PermissionDenied(
            "You do not have permission to delete "
            "tasks in this project."
        )

    # Verify that the task belongs to this project.
    task = get_object_or_404(
        Task,
        pk=task_id,
        project=project
    )

    # Preserve the task name for the notification.
    task_name = task.name

    # Remove the task from the database.
    task.delete()

    messages.success(
        request,
        f'Task "{task_name}" was deleted successfully.'
    )

    return redirect(
        "projects:project_detail",
        project_id=project.pk
    )