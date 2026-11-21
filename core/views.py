
"""
Core views for TaskFlow.

This application manages shared website pages,
including the original TaskFlow homepage.

The homepage preserves the frontend structure
developed during the midterm project.
"""

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .forms import ContactMessageForm

def home(request):
    """
    Render the original TaskFlow homepage.

    The template extends the shared Django layout
    and preserves the original homepage components.

    Database-backed statistics and recent task activity
    will be integrated in subsequent steps.
    """
    return render(request, "core/home.html")

def about(request):
    """
    Render the original TaskFlow About page.

    The page preserves the midterm project's
    Career Services information, team profiles,
    and supporting content.

    Its shared navigation and layout are
    provided by Django's layout.html.
    """
    return render(request, "core/about.html")

@require_http_methods(["GET", "POST"])
def contact(request):
    """
    Display the Contact page and process submissions.

    GET: Render the original TaskFlow Contact page.
    POST: Validate and save the submitted message.
    """

    if request.method == "POST":

        # Validate the submitted data on the server.
        form = ContactMessageForm(request.POST)

        if form.is_valid():

            # Save the validated message to SQLite.
            form.save()

            return JsonResponse(
                {
                    "success": True,
                    "message": "Your message was saved successfully."
                },
                status=201
            )

        # Return validation errors without saving.
        return JsonResponse(
            {
                "success": False,
                "errors": {
                    field: list(errors)
                    for field, errors in form.errors.items()
                }
            },
            status=400
        )

    # Display the Contact page for GET requests.
    return render(request, "core/contact.html")