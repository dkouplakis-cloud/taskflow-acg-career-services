
"""
URL configuration for TaskFlow's Core application.

The Core application manages shared website pages,
including the original homepage from the midterm project.

Named URLs allow Django templates to reference pages
without hardcoding their addresses.
"""

from django.urls import path

from . import views


# Namespace prevents URL naming conflicts with other apps.
app_name = "core"


urlpatterns = [

    # Display the original TaskFlow homepage.
    # This route will become the application's root URL.
    path("", views.home, name="home"),

]