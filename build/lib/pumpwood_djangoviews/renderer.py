"""Custom JSON Renderer."""
from rest_framework.renderers import JSONRenderer
from pumpwood_communication.serializers import pumpJsonDump


class PumpwoodJSONRenderer(JSONRenderer):
    charset = 'utf-8'

    def render(self, data, media_type=None, renderer_context=None):
        return pumpJsonDump(data)
