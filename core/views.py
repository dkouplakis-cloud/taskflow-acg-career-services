
"""
Core views for TaskFlow.

This application manages shared website pages,
including the original TaskFlow homepage.

The homepage preserves the frontend structure
developed during the midterm project.
"""

from django.shortcuts import render


def home(request):
    """
    Render the original TaskFlow homepage.

    The template extends the shared Django layout
    and preserves the original homepage components.

    Database-backed statistics and recent task activity
    will be integrated in subsequent steps.
    """
    return render(request, "core/home.html")