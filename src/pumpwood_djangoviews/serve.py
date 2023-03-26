"""
Codes to serve files using PumpwoodEnd Points.
"""
import os
from django.http import FileResponse
from rest_framework.decorators import (
    permission_classes, api_view)
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.http import HttpResponse, StreamingHttpResponse
from django.contrib.auth.decorators import login_required

class ServeMediaFiles:
    """
    Class to serve files using Pumpwood Storage Object and checking user
    authentication.
    """

    def __init__(self, storage_object):
        self.storage_object = storage_object

    def as_view(self):
        """Return a view function using storage_object set on object."""
        @login_required
        def download_from_storage_view(request, file_path):
            file_interator = self.storage_object.get_read_file_iterator(
                file_path)
            file_name = os.path.basename(file_path)
            content_disposition = 'attachment; filename="{}"'.format(
                file_name)
            return StreamingHttpResponse(file_interator, headers={
                'Content-Disposition': content_disposition})
        return download_from_storage_view
