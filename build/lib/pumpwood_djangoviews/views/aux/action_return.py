"""Auxiliary function to treat bytes return."""
from typing import Literal, Any
from django.http import HttpResponse
from pumpwood_communication.exceptions import PumpWoodNotImplementedError
from pumpwood_communication.type import ActionReturnFile
from werkzeug.utils import secure_filename


class AuxViewActionReturnFile:
    """Class to treat bytes return."""

    @classmethod
    def can_treat(cls, action_result: Any):
        """Check if this class can treat the action results."""
        return isinstance(action_result, ActionReturnFile)

    @classmethod
    def run(cls, action_result: ActionReturnFile,
            mode: Literal['file', 'base64', 'streaming'] = 'file'):
        """Treat run data for bytes type."""
        # Set file name as secure
        filename = secure_filename(action_result.filename)

        if mode == 'file':
            return cls.return_file(
                filename=filename, content=action_result.content,
                content_type=action_result.content_type)
        if mode == 'base64':
            return cls.return_base64(
                filename=filename, content=action_result.content,
                content_type=action_result.content_type)
        if mode == 'streaming':
            return cls.return_streaming(
                filename=filename, content=action_result.content,
                content_type=action_result.content_type)

    @classmethod
    def return_file(cls, filename: str, content: bytes,
                    content_type: str = None):
        """Return as file format."""
        content_type = (
            content_type if content_type is not None
            else "application/octet-stream")
        response = HttpResponse(
            content, content_type=content_type)
        response['Content-Disposition'] = (
            'attachment; filename="{filename}"').format(filename=filename)
        return response

    @classmethod
    def return_base64(cls, filename: str, content: bytes,
                      content_type: str = None):
        """Return as base64 format."""
        msg = "Return action file on base64 format is not implemented"
        raise PumpWoodNotImplementedError(msg)

    @classmethod
    def return_streaming(cls, filename: str, content: bytes,
                         content_type: str = None):
        """Return as streaming format."""
        msg = "Return action file on streaming format is not implemented"
        raise PumpWoodNotImplementedError(msg)
