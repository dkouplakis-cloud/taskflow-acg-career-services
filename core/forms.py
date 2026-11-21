"""
TaskFlow | ACG Career Services

Django forms for the Core application.

ContactMessageForm validates Contact submissions
before they are saved to the database.
"""

from django import forms

from .models import ContactMessage


class ContactMessageForm(forms.ModelForm):
    """
    Validate messages submitted through the
    TaskFlow Contact page.

    Validation is performed on the server,
    independently of JavaScript.
    """

    # Enforce the same message length limits
    # as the original frontend Contact form.
    message = forms.CharField(
        min_length=10,
        max_length=2000,
        strip=True,
        widget=forms.Textarea
    )

    class Meta:
        model = ContactMessage

        fields = [
            "name",
            "email",
            "subject",
            "message",
        ]