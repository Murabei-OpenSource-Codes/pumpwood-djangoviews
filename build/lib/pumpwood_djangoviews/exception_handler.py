"""Define custom exception handlers for Pumpwood systems."""
from rest_framework.views import exception_handler
from pumpwood_communication.exceptions import (
    PumpWoodException, PumpWoodObjectDoesNotExist, PumpWoodQueryException,
    PumpWoodUnauthorized, PumpWoodIntegrityError)
from rest_framework.response import Response
from django.core.exceptions import (
    FieldError, ObjectDoesNotExist, PermissionDenied)
from django.db.utils import IntegrityError


def custom_exception_handler(exc, context):
    """Treat custom exception handler to PumpWoodExceptions."""
    ##########################################################
    # Call REST framework's default exception handler first, #
    # to get the standard error response.
    if issubclass(type(exc), FieldError):
        pump_exc = PumpWoodQueryException(message=str(exc))
        payload = pump_exc.to_dict()
        return Response(
            payload, status=pump_exc.status_code)

    if issubclass(type(exc), IntegrityError):
        pump_exc = PumpWoodIntegrityError(message=str(exc))
        payload = pump_exc.to_dict()
        return Response(
            payload, status=pump_exc.status_code)

    if issubclass(type(exc), ObjectDoesNotExist):
        pump_exc = PumpWoodObjectDoesNotExist(message=str(exc))
        payload = pump_exc.to_dict()
        return Response(
            payload, status=pump_exc.status_code)

    if issubclass(type(exc), PermissionDenied):
        pump_exc = PumpWoodUnauthorized(message=str(exc))
        payload = pump_exc.to_dict()
        return Response(
            payload, status=pump_exc.status_code)

    if issubclass(type(exc), PumpWoodException):
        payload = exc.to_dict()
        return Response(
            payload, status=exc.status_code)

    response = exception_handler(exc, context)
    return response
