"""
Views for displaying and managing user projects.

Project information is accessible only to
authenticated users with appropriate ownership.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods

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
            # Do not save immediately: ownership must be
            # assigned by the server, not by the submitted form.
            project = form.save(commit=False)
            project.owner = request.user
            project.save()

            # Confirm successful creation to the user.
            messages.success(
                request,
                'Your project was created successfully.'
            )

            # Return to the user's project list.
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