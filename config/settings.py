"""
Django settings for the TaskFlow project.

TaskFlow is a project-based task management application
developed for ACG Career Services.

Configuration includes:
- Environment-based secret key management
- Authentication and session support
- Projects and Tasks applications
- Shared Django templates
- Existing TaskFlow CSS, JavaScript, and images
- SQLite database for local development
"""

import os
from pathlib import Path

from dotenv import load_dotenv


# ============================================================
# 1. BASE DIRECTORY AND ENVIRONMENT VARIABLES
# ============================================================

# Identify the root directory of the Django project.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load local configuration values from the .env file.
# The .env file must never be committed to GitHub.
load_dotenv(BASE_DIR / '.env')


# ============================================================
# 2. SECURITY AND DEVELOPMENT CONFIGURATION
# ============================================================

# Read the secret key from the environment rather than
# storing sensitive information directly in source code.
SECRET_KEY = os.environ['DJANGO_SECRET_KEY']

# Enable detailed errors during local development only.
# This must be disabled before production deployment.
DEBUG = True

# An empty list is suitable for local development with
# DEBUG enabled and Django's default localhost handling.
ALLOWED_HOSTS = []

# ============================================================
# 3. INSTALLED APPLICATIONS
# ============================================================

INSTALLED_APPS = [
    # Built-in Django applications.
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # TaskFlow applications.
    # Core manages shared pages such as Home, About, and Contact.
    'core.apps.CoreConfig',

    # Projects organize work into separate user-owned workspaces.
    'projects.apps.ProjectsConfig',

    # Tasks belong to projects and track individual activities.
    'tasks.apps.TasksConfig',

    # Public Career Services catalogue.
    'catalog.apps.CatalogConfig',
]


# ============================================================
# 4. MIDDLEWARE
# ============================================================

# Process security, sessions, authentication, CSRF
# protection, messages, and clickjacking protection.
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.LoginRequiredMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# ============================================================
# 5. ROOT URL CONFIGURATION
# ============================================================

# Main URL configuration includes the admin interface
# and routes belonging to TaskFlow applications.
ROOT_URLCONF = 'config.urls'


# ============================================================
# 6. DJANGO TEMPLATE CONFIGURATION
# ============================================================

TEMPLATES = [
    {
        'BACKEND': (
            'django.template.backends.django.DjangoTemplates'
        ),

        # Locate reusable templates in the root templates folder.
        # Individual pages can extend templates/layout.html.
        'DIRS': [
            BASE_DIR / 'templates',
        ],

        # Also discover templates within installed applications.
        'APP_DIRS': True,

        'OPTIONS': {
            'context_processors': [

                'django.template.context_processors.debug',

                # Make the current request available in templates.
                'django.template.context_processors.request',

                # Provide the authenticated user and permissions.
                'django.contrib.auth.context_processors.auth',

                'core.context_processors.workspace_navigation',

                # Display success, warning, and error messages.
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


# ============================================================
# 7. WSGI APPLICATION
# ============================================================

# Entry point for WSGI-compatible application servers.
WSGI_APPLICATION = 'config.wsgi.application'


# ============================================================
# 8. DATABASE CONFIGURATION
# ============================================================

# SQLite provides persistent local storage for Projects,
# Tasks, users, sessions, and other Django models.
#
# The local database is excluded from Git version control.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# ============================================================
# 9. PASSWORD VALIDATION
# ============================================================

# Use Django's built-in password validators to improve
# password security when users create their accounts.
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'UserAttributeSimilarityValidator'
        ),
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'MinimumLengthValidator'
        ),
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'CommonPasswordValidator'
        ),
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'NumericPasswordValidator'
        ),
    },
]


# ============================================================
# 10. INTERNATIONALIZATION AND TIME ZONE
# ============================================================

# English is the primary language of the user interface.
LANGUAGE_CODE = 'en-us'

# Use Athens local time for date-sensitive project
# management, including project and task deadlines.
TIME_ZONE = 'Europe/Athens'

# Enable Django's internationalization support.
USE_I18N = True

# Store timezone-aware timestamps for reliable processing.
USE_TZ = True


# ============================================================
# 11. STATIC FILES
# ============================================================

# URL prefix used for CSS, JavaScript, and image assets.
STATIC_URL = 'static/'

# Reuse the existing frontend assets from our original
# TaskFlow application without duplicating source files.
#
# Directory structure:
# assets/
#     css/
#     js/
#     images/
STATICFILES_DIRS = [
    BASE_DIR / 'assets',
]

# ---------------------------------------------------------
# USER-UPLOADED MEDIA FILES
# ---------------------------------------------------------

# URL prefix for uploaded images and other media.
MEDIA_URL = '/media/'

# Directory where uploaded media files are stored.
MEDIA_ROOT = BASE_DIR / 'media'


# ============================================================
# 12. DEFAULT PRIMARY KEY
# ============================================================

# Use 64-bit automatically generated primary keys for
# Django models unless a model specifies another key.
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ============================================================
# 13. AUTHENTICATION REDIRECTS
# ============================================================

# Redirect unauthenticated users to the sign-in page.
# Django preserves the originally requested destination.
LOGIN_URL = 'login'

# Display the user's projects after a normal sign-in.
LOGIN_REDIRECT_URL = 'projects:project_list'

# Return users to the sign-in page after logging out.
LOGOUT_REDIRECT_URL = 'login'