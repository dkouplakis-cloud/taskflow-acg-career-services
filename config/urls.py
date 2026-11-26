
"""
Main URL configuration for TaskFlow.

This file connects the application's components:
- Core: original TaskFlow homepage and shared pages.
- Projects: project management functionality.
- Authentication: login, logout, and account management.
- Admin: Django's built-in administration interface.

Named URL patterns help maintain clean, reusable navigation.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from core.auth_views import TaskFlowLoginView, student_register
from django.contrib.auth.decorators import login_not_required
from django.views.static import serve

urlpatterns = [
    # Django's built-in administration interface.
    path("admin/", admin.site.urls),

    # Custom TaskFlow catalogue administration interface.
    path(
        "manage/catalog/",
        include("catalog.management_urls")
    ),

    # Public registration for regular student accounts.
    # Privileged workspace roles cannot be self-assigned.
    path(
        "accounts/register/",
        student_register,
        name="student_register"
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

    # User-facing career services catalogue.
    # Separate from the administrator management interface.
    path(
        "catalog/",
        include("catalog.urls")
    ),

    # Original TaskFlow homepage and future shared pages.
    # The empty prefix connects core's home view to "/".
    path("", include("core.urls")),
]

# ---------------------------------------------------------
# DEVELOPMENT MEDIA FILE SERVING
# ---------------------------------------------------------

# Allow Django to serve uploaded catalogue images
# during local development only.
#
# Production media serving will be configured
# separately when deploying TaskFlow over HTTPS.

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        view=login_not_required(serve),
        document_root=settings.MEDIA_ROOT,
    )