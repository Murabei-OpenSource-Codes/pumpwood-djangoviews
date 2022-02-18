#!/usr/bin/python
# -*- coding: utf-8 -*-
from rest_framework.decorators import (
    permission_classes, api_view)
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.http import HttpResponse


@api_view(['GET'])
@permission_classes((IsAuthenticated,))
def serve_X_Accel_protected(request, path, **kwargs):
    """
    Verify if user is logged and serve files in Ngnix using X-Accel to
    avoid django overhead.
    """
    response = HttpResponse('', status=200)
    response['X-Accel-Redirect'] = '/protected/' + path
    response['Content-Type'] = ''
    return response


@api_view(['GET'])
@permission_classes((AllowAny,))
def serve_X_Accel_unprotected(request, path, **kwargs):
    """
    Serve files in Ngnix using X-Accel to avoid django overhead.
    """
    response = HttpResponse('', status=200)
    response['X-Accel-Redirect'] = '/unprotected/' + path
    response['Content-Type'] = ''
    return response
