"""
URL configuration for project management.

Named routes allow views and templates to reference
project pages without hardcoding URL paths.
"""

from django.urls import path

from . import views


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
]