"""Define actions decorator."""
import inspect
import pandas as pd
from typing import cast
from datetime import date, datetime
from typing import Callable

from pumpwood_communication.exceptions import PumpWoodActionArgsException


class Action:
    """Define a Action class to be used in decorator action."""

    def __init__(self, func: Callable, info: str, auth_header: str = None):
        """."""
        signature = inspect.signature(func)
        function_parameters = signature.parameters
        parameters = {}
        is_static_function = True
        for key in function_parameters.keys():
            if key in ['self', 'cls', auth_header]:
                if key == "self":
                    is_static_function = False
                continue
            param = function_parameters[key]

            if param.annotation == inspect.Parameter.empty:
                if inspect.Parameter.empty:
                    param_type = "Any"
                else:
                    param_type = type(param.default).__name__
            else:
                param_type = param.annotation \
                    if type(param.annotation) == str \
                    else param.annotation.__name__

            parameters[key] = {
                "required": param.default is inspect.Parameter.empty,
                "type": param_type
            }

            if param.default is not inspect.Parameter.empty:
                parameters[key]['default_value'] = param.default

        self.action_name = func.__name__
        self.is_static_function = is_static_function
        self.parameters = parameters
        self.info = info
        self.auth_header = auth_header

    def to_dict(self):
        """Return dict representation of the action."""
        return {
            "action_name": self.action_name,
            "is_static_function": self.is_static_function,
            "info": self.info,
            "parameters": self.parameters}


def action(info: str = "", auth_header: str = None):
    """
    Define decorator that will convert the function into a rest action.

    Args:
        info: Just an information about the decorated function that will be
        returned in GET /rest/<model_class>/actions/.
    Kwargs:
        request_user (str): Variable that will receive logged user.
    Returns:
        func: Action decorator.

    """
    def action_decorator(func):
        func.is_action = True
        func.action_object = Action(
            func=func, info=info, auth_header=auth_header)
        return func
    return action_decorator


def load_action_parameters(func: Callable, parameters: dict, request):
    """Cast arguments to its original types."""
    signature = inspect.signature(func)
    function_parameters = signature.parameters
    # Loaded parameters for action run
    return_parameters = {}
    # Errors found when processing the parameters
    errors = {}
    # Unused parameters, passed but not in function
    unused_params = set(parameters.keys()) - set(function_parameters.keys())

    # The request user parameter, set the logged user
    auth_header = func.action_object.auth_header

    if len(unused_params) != 0:
        errors["unused args"] = {
            "type": "unused args",
            "message": list(unused_params)}

    for key in function_parameters.keys():
        # pass if arguments are self and cls for classmethods
        if key in ['self', 'cls']:
            continue

        # If arguent is the request user one, set with the logged user
        if key == auth_header:
            token = request.headers.get('Authorization')
            return_parameters[key] = {'Authorization': token}
            continue

        param_type = function_parameters[key]
        par_value = parameters.get(key)
        if par_value is not None:
            try:
                if param_type.annotation == date:
                    return_parameters[key] = pd.to_datetime(par_value).date()
                elif param_type.annotation == datetime:
                    return_parameters[key] = \
                        pd.to_datetime(par_value).to_pydatetime()
                else:
                    return_parameters[key] = param_type.annotation(par_value)

            # If any error ocorrur then still try to cast data from python
            # typing
            except Exception:
                try:
                    return_parameters[key] = return_parameters[key] = cast(
                        param_type.annotation, par_value)
                except Exception as e:
                    errors[key] = {
                        "type": "unserialize",
                        "message": str(e)}
        # If parameter is not passed and required return error
        elif param_type.default is inspect.Parameter.empty:
            errors[key] = {
                "type": "nodefault",
                "message": "not set and no default"}

    # Raise if there is any error in serilization
    if len(errors.keys()) != 0:
        template = "[{key}]: {message}"
        error_msg = "error when unserializing function arguments:\n"
        error_list = []
        for key in errors.keys():
            error_list.append(template.format(
                key=key, message=errors[key]["message"]))
        error_msg = error_msg + "\n".join(error_list)
        raise PumpWoodActionArgsException(
            status_code=400, message=error_msg, payload={
                "arg_errors": errors})

    return return_parameters
