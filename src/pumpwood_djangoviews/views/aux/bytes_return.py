"""Auxiliary function to treat bytes return."""
from typing import Literal, Any
from django.http import HttpResponse
from pumpwood_communication.exceptions import (
    PumpWoodOtherException, PumpWoodNotImplementedError)
from werkzeug.utils import secure_filename


class AuxViewReturnBytes:
    """Class to treat bytes return."""

    @classmethod
    def validate(cls, result: Any):
        """Validate return data."""
        msg = (
            "Bytes return from an action must be a dictonary with "
            "'__filename__', '__content__' keys. '__content_type__' is "
            "optional.")
        print('type(result):', type(result))
        if not isinstance(result, dict):
            raise PumpWoodOtherException(msg)

        set_result_keys = set(result.keys())
        val_keys = {'__filename__', '__content__'} - set_result_keys
        if len(val_keys) != 0:
            raise PumpWoodOtherException(msg)

        return {
            'filename': result['__filename__'],
            'content': result['__content__'],
            'content_type': result.get('__content_type__'),
        }

    @classmethod
    def run(cls, result: dict,
            mode: Literal['file', 'base64', 'streaming'] = 'file'):
        """Treat run data for bytes type."""
        return_data = cls.validate(result=result)

        # Set file name as secure
        filename = secure_filename(return_data['filename'])

        if mode == 'file':
            return cls.return_file(
                filename=filename, content=return_data['content'],
                content_type=return_data['content_type'])
        if mode == 'base64':
            return cls.return_base64(
                filename=filename, content=return_data['content'],
                content_type=return_data['content_type'])
        if mode == 'streaming':
            return cls.return_streaming(
                filename=filename, content=return_data['content'],
                content_type=return_data['content_type'])

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
