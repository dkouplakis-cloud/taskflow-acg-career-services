
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


@login_required
@require_http_methods(["GET", "POST"])
def task_create(request, project_id):
    """
    Create a task inside a project owned by
    the currently authenticated user.

    GET displays the task creation form.
    POST validates and saves the new task.
    """

    # Only allow access to projects owned
    # by the currently authenticated user.
    project = get_object_or_404(
        Project,
        pk=project_id,
        owner=request.user
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


@login_required
@require_http_methods(["GET", "POST"])
def task_update(request, project_id, task_id):
    """
    Edit an existing task belonging to a project
    owned by the authenticated user.
    """

    project = get_object_or_404(
        Project,
        pk=project_id,
        owner=request.user
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


@login_required
@require_http_methods(["POST"])
def task_complete(request, project_id, task_id):
    """
    Mark a task as completed.

    Only the owner of the parent project
    can perform this action.
    """

    project = get_object_or_404(
        Project,
        pk=project_id,
        owner=request.user
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

@login_required
@require_http_methods(["POST"])
def task_delete(request, project_id, task_id):
    """
    Permanently delete a task belonging to
    a project owned by the authenticated user.

    Only POST requests are permitted.
    """

    # Verify project ownership.
    project = get_object_or_404(
        Project,
        pk=project_id,
        owner=request.user
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