
"""
Main URL configuration for TaskFlow.

This file connects the application's components:
- Core: original TaskFlow homepage and shared pages.
- Projects: project management functionality.
- Authentication: login, logout, and account management.
- Admin: Django's built-in administration interface.

Named URL patterns help maintain clean, reusable navigation.
"""

from django.contrib import admin
from django.urls import include, path
from core.auth_views import TaskFlowLoginView

urlpatterns = [
    # Django's built-in administration interface.
    path("admin/", admin.site.urls),

    # Custom TaskFlow catalogue administration interface.
    path(
        "manage/catalog/",
        include("catalog.management_urls")
    ),
    
    # Role-aware login using Django's secure LoginView.
    # This route must appear before the built-in auth URLs.
    path(
        "accounts/login/",
        TaskFlowLoginView.as_view(),
        name="login"
    ),

    # Preserve Django's logout and password management.
    path(
        "accounts/",
        include("django.contrib.auth.urls")
    ),

    # Project management: listing and creating projects.
    path("projects/", include("projects.urls")),

    # Original TaskFlow homepage and future shared pages.
    # The empty prefix connects core's home view to "/".
    path("", include("core.urls")),
]