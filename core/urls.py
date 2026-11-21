
"""
URL configuration for TaskFlow's Core application.

Core manages shared pages inherited from the original
TaskFlow midterm project.

Named routes allow navigation throughout Django
without hardcoded HTML file paths.
"""

from django.urls import path

from . import views


# Namespace prevents naming conflicts with other apps.
app_name = "core"


urlpatterns = [
    # Original TaskFlow homepage.
    path(
        "",
        views.home,
        name="home"
    ),

    # Original About page, integrated into Django.
    path(
        "about/",
        views.about,
        name="about"
    ),

    # Original Contact page, integrated into Django.
    path(
        "contact/",
        views.contact,
        name="contact"
    ),
]