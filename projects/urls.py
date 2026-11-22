"""
URL configuration for project management.

Named routes allow views and templates to reference
project pages without hardcoding URL paths.
"""

from django.urls import path
from . import views
from tasks import views as task_views

# Namespace prevents conflicts with routes in other Django apps.
app_name = 'projects'

urlpatterns = [
    # Display projects belonging to the authenticated user.
    path(
        '',
        views.project_list,
        name='project_list'
    ),

    # Display and process the new-project form.
    path(
        'new/',
        views.project_create,
        name='project_create'
    ),

    # Display a specific project and its associated tasks.
    path(
        '<int:project_id>/',
        views.project_detail,
        name='project_detail'
    ),

    # Edit an existing project.
    path(
        '<int:project_id>/edit/',
        views.project_update,
        name='project_update'
    ),

    # Create a task inside an existing project.
    path(
        '<int:project_id>/tasks/new/',
        task_views.task_create,
        name='task_create'
    ),

    path(
        "<int:project_id>/tasks/<int:task_id>/edit/",
        task_views.task_update,
        name="task_update"
    ),

    path(
        "<int:project_id>/tasks/<int:task_id>/complete/",
        task_views.task_complete,
        name="task_complete"
    ),

    # Analytics dashboard for the user's projects.
    path(
        "analytics/",
        views.analytics_dashboard,
        name="analytics"
    ),


    # Delete a task from a project.
    path(
        "<int:project_id>/tasks/<int:task_id>/delete/",
        task_views.task_delete,
        name="task_delete"
    ),

]