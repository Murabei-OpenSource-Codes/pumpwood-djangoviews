"""
Create a custom JSON Renderer.

Use `pumpwood_communication.serializers import pumpJsonDump` to dump
alternative python types such as pandas DataFrames and datetimes, not
been necessary to treat at the codes.
"""
from django.core.exceptions import ImproperlyConfigured
# Treat for development error when importing module without Django App
from rest_framework.renderers import JSONRenderer
from pumpwood_communication.serializers import pumpJsonDump


class PumpwoodJSONRenderer(JSONRenderer):
    """JSONRenderer that use pumpJsonDump to dump data to JSON."""

    charset = 'utf-8'

    def render(self, data, media_type=None, renderer_context=None):
        """Overwrite render function to use pumpJsonDump."""
        return pumpJsonDump(data)
