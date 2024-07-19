"""
Define custom exception handlers for Pumpwood systems.

Custom erros can be used to correctly treat Pumpwood Exceptions and return
the treated erro as a JSON with not 2XX status code.

`custom_exception_handler` can be used at REST_FRAMEWORK MiddleWare at Django.

```python
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'knox.auth.TokenAuthentication',
    ),
    'EXCEPTION_HANDLER': (
        # Add custom handler for API Calls
        'pumpwood_djangoviews.exception_handler.custom_exception_handler'
    )
}
```
"""
from django.core.exceptions import (
    FieldError, ObjectDoesNotExist, PermissionDenied)
from django.db.utils import IntegrityError
from rest_framework.response import Response
from pumpwood_communication.exceptions import (
    PumpWoodException, PumpWoodObjectDoesNotExist, PumpWoodQueryException,
    PumpWoodUnauthorized, PumpWoodIntegrityError)


def custom_exception_handler(exc, context) -> Response:
    """
    Treat custom exception handler to PumpWoodExceptions.

    Args:
        exc [Exception]:
            Exception raised processing request.
        context:
            Context of the error that was raised.
    Returns:
        Return a response with error code depending of the PumpWoodException
        raised. It returns a serialized dictionary with exception data.
    """
    from rest_framework.views import exception_handler

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

    # Treat Pumpwood Exceptions and return the serialized information on a
    # dictonary with correct status_code
    if issubclass(type(exc), PumpWoodException):
        payload = exc.to_dict()
        return Response(
            payload, status=exc.status_code)

    response = exception_handler(exc, context)
    return response
