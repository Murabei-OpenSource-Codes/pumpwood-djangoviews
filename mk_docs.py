"""Make documentation using pydocs."""
import django
from django.conf import settings
from pdoc import pdoc
from pdoc.render import configure
from pathlib import Path

settings.configure(
    DEBUG_PROPAGATE_EXCEPTIONS=True,
    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:'
        },
        'secondary': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:'
        }
    },
    SITE_ID=1,
    SECRET_KEY='not very secret in tests',
    USE_I18N=True,
    STATIC_URL='/static/',
    ROOT_URLCONF='tests.urls',
    TEMPLATES=[
        {
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'APP_DIRS': True,
            'OPTIONS': {
                "debug": True,  # We want template errors to raise
            }
        },
    ],
    MIDDLEWARE=(
        'django.middleware.common.CommonMiddleware',
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'django.contrib.messages.middleware.MessageMiddleware',
    ),
    INSTALLED_APPS=(
        'django.contrib.admin',
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.sites',
        'django.contrib.staticfiles',
        'rest_framework',

        # MFA Admin
        'knox',

        # Django Pumpwood Auth Models
        'pumpwood_djangoauth',
        'pumpwood_djangoauth.i8n',
        'pumpwood_djangoauth.mfaadmin',
        'pumpwood_djangoauth.registration',
        'pumpwood_djangoauth.system',
        'pumpwood_djangoauth.metabase',
        'pumpwood_djangoauth.api_permission',
    ),
    PASSWORD_HASHERS=(
        'django.contrib.auth.hashers.MD5PasswordHasher',
    ),
)
django.setup()


configure(
    docformat='google',
    include_undocumented=False)
pdoc(
    'src/pumpwood_djangoviews',
    output_directory=Path("docs/"))
