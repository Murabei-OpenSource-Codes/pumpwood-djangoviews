"""
Create a custom JSON Renderer.

Use `pumpwood_communication.serializers import pumpJsonDump` to dump
alternative python types such as pandas DataFrames and datetimes, not
been necessary to treat at the codes.
"""
import orjson
from rest_framework.renderers import BaseRenderer
from rest_framework.parsers import BaseParser
from pumpwood_communication.serializers import pumpJsonDump


class PumpwoodJSONRenderer(BaseRenderer):
    """JSONRenderer that use pumpJsonDump to dump data to JSON."""

    media_type = "application/json"
    format = "json"
    charset = 'utf-8'

    def render(self, data, media_type=None, renderer_context=None):
        """Overwrite render function to use pumpJsonDump."""
        return pumpJsonDump(data)


class PumpwoodJSONParser(BaseParser):
    """Parses JSON request bodies using orjson."""
    media_type = "application/json"

    def parse(self, stream, media_type=None, parser_context=None):
        """Parse json data using orjson for fast process."""
        # DRF gives us a stream (file-like object)
        raw_data = stream.read()
        if not raw_data:
            return {}
        return orjson.loads(raw_data)
