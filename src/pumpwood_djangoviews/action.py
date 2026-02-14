"""
Define actions decorator.

Define action decorator that can be used to expose function at execute
action pumpwood end-points.

Example of using the decorator to expose function to end-point:
```python
[...]

class ExampleModel(models.Model):
    STATUS = (
        ("inactive", "Archived"),
        ("dev", "Development"),
        ("homolog", "Homologation"),
        ("production", "Production"),
    )

    status = models.CharField(
        choices=STATUS, max_length=15,
        verbose_name="Status",
        help_text="Status")
    description = models.CharField(
        null=False, max_length=100, unique=True,
        verbose_name="Description",
        help_text="Dashboard description")
    notes = models.TextField(
        null=False, default="", blank=True,
        verbose_name="Notes",
        help_text="A long description of the dashboard")
    dimensions = models.JSONField(
        encoder=PumpWoodJSONEncoder, null=False, default=dict,
        blank=True,
        verbose_name="Dimentions",
        help_text="Key/Value Dimentions")

    @action(info='Expose an action associated with an object')
    # It is important to use the type tips to correctly convert the
    # request payload to correct python types
    def object_action(self, string_arg: str = None, int_arg: int) -> List[str]:

        [...]

    @classmethod
    @action(info='Expose a classmethod')
    def class_method(cls, list_of_dict_arg: List[dict]) -> bool:
        # Class method will not receive pk when running execute_action
        [...]

    @action(info='Pass the auth_header as argument to function.',
            auth_header="auth_header")
    # Auth header will be passed to function as argument, it can be used to
    # impersonate user using PumpWoodMicroserive.
    def pass_auth_header_to_function(self, list_of_dict_arg: List[dict],
                                     auth_header: dict) -> str:
        # Passing auth header to microservice object will impersonate
        # user.
        related_fields_fetched = microservice.list(
            model_class="MicroserviceRelatedModel",
            filter_dict={"fk_field": self.id},
            auth_header=auth_header)
        [...]
```
"""
import inspect
import textwrap
import pandas as pd
import typing
from datetime import date, datetime
from typing import cast, Callable
from pumpwood_communication.exceptions import PumpWoodActionArgsException
from pumpwood_miscellaneous.type import ActionReturnFile


class Action:
    """Define a Action class to be used in decorator action."""

    func_return: str
    """Type of the return associated with funciton."""
    doc_string: str
    """Doc string of the function"""
    action_name: str
    """Name of the function."""
    is_static_function: bool
    """True if funciton is staticmethod or a classmethod (does not require
       an object to run)"""
    parameters: dict
    """Dictionary with function arguments with types and if it is necessary
       (not set a default value) or opcional (with default value)."""
    info: str
    """Info associated with function that will be passed to user at [GET]
       `action end-point.`"""
    auth_header: str
    """Function argument that will receive `auth_header` information.
       auth_header can be to user impersonation when calling other end-points
       from the function."""
    request: str
    """Function argument that will receive Django request object``. This
       object can be used to pass context to serializers and other
       funcionalities."""
    permission_role: str
    """Permission associated with action, if not set it will consider default
       permission pumpwood scheme: `can_run_actions`/custom action
       permission."""

    def __init__(self, func: Callable, info: str,
                 auth_header: str = None, request: str = None,
                 permission_role="can_run_actions") -> Callable:
        """__init__.

        Args:
            func (Callable):
                Function that will be decorated with @action Pumpwood
                decorator.
            info (str):
                Function information that will be returned at [GET] `actions`
                to user.
            auth_header (str):
                Function argument that will be populated with `auth_header`
                when executing the function.
            request (str):
                Function argument that will be populated with Django's request
                object.
            permission_role (str):
                Set a permission role to by pass Pumpwood action permission
                validation. Role must be in `['can_delete', 'can_delete_file',
                'can_delete_many', 'can_list', 'can_list_without_pag',
                'can_retrieve', 'can_retrieve_file', 'can_run_actions',
                'can_save', 'authenticated', 'default', 'is_superuser']`.
        """
        def extract_param_type(param) -> None:
            """Extract paramter type."""
            resp = {"many": False}
            if param.annotation == inspect.Parameter.empty:
                if param.default == inspect.Parameter.empty:
                    resp["type"] = "Any"
                else:
                    resp["type"] = type(param.default).__name__
            elif type(param.annotation) is str:
                resp["type"] = param.annotation
            elif isinstance(param.annotation, type):
                resp["type"] = param.annotation.__name__
            elif typing.get_origin(param.annotation) == typing.Literal:
                resp["type"] = "options"
                typing_args = typing.get_args(param.annotation)
                resp["in"] = [
                    {"value": x, "description": x}
                    for x in typing_args]
            elif typing.get_origin(param.annotation) is list:
                resp["many"] = True
                list_args = typing.get_args(param.annotation)
                if len(list_args) == 0:
                    resp["type"] = "Any"
                else:
                    resp["type"] = list_args[0].__name__
            else:
                resp["type"] = str(param.annotation).replace(
                    'typing.', '')
            return resp

        def extract_return_type(return_annotation):
            """Extract result type."""
            is_many = (
                typing.get_origin(return_annotation) in (list, typing.List))
            if is_many:
                list_args = typing.get_args(return_annotation)
                if len(list_args) == 0:
                    return {"many": True, "type": "Any"}
                return_annotation = list_args[0]

            if return_annotation in (inspect.Parameter.empty, typing.Any):
                return {"many": is_many, "type": "Any"}

            if type(return_annotation) is str:
                return {"many": is_many, "type": return_annotation}

            is_actionreturnfile = (
                inspect.isclass(return_annotation) and
                issubclass(return_annotation, ActionReturnFile))
            if is_actionreturnfile:
                return {"many": is_many, "type": 'file'}

            if isinstance(return_annotation, type):
                return {"many": is_many, "type": return_annotation.__name__}

            if (typing.get_origin(return_annotation) == typing.Literal):
                typing_args = typing.get_args(return_annotation)
                in_options = [
                    {"value": x, "description": str(x)}
                    for x in typing_args]
                return {"many": is_many, "type": 'options', 'in': in_options}

            return_type = str(return_annotation).replace('typing.', '')
            return {
                "many": is_many,
                "type": return_type
            }

        # Getting function parameters hint
        signature = inspect.signature(func)
        function_parameters = signature.parameters
        parameters = {}
        is_static_function = True
        for key in function_parameters.keys():
            if key == "self":
                is_static_function = False
                # Does not return self parameter to user
                continue

            if key == "cls":
                # Does not return cls parameter from class functions
                continue

            # Do not return as function paramters auth_header or request
            # since they are set by Pumpwood.
            if auth_header is not None:
                if key == auth_header:
                    continue
            if request is not None:
                if key == request:
                    continue

            param = function_parameters[key]
            param_type = extract_param_type(param)
            temp_dict = {
                "required": param.default is inspect.Parameter.empty}
            temp_dict.update(param_type)
            parameters[key] = temp_dict
            if param.default is not inspect.Parameter.empty:
                parameters[key]['default_value'] = param.default

        # Getting return types:
        return_annotation = signature.return_annotation
        self.func_return = extract_return_type(return_annotation)
        self.doc_string = textwrap.dedent(func.__doc__).strip()
        self.action_name = func.__name__
        self.is_static_function = is_static_function
        self.parameters = parameters
        self.info = info
        self.auth_header = auth_header
        self.request = request
        self.permission_role = permission_role

    def to_dict(self) -> dict:
        """Return dict representation of the action.

        Returns:
            Return a dictonary used to serialize action to action end-point.
            Keys avaiable:
            - **action_name [str]**: Name of the function.
            - **is_static_function [bool]**: Boolean value indicating if
                the function is a classmethod or staticmethod.
            - **info [str]**: Information that will be avaiable to user using
                action end-points.
            - **return [str]**: Type of the return of the function.
            - **parameters [dict]**: Arguments of the function with
                information of types, default values.
            - **doc_string [str]**: Doc string associated with the function.
            - **permission_role [str]**: Permission role associated with
                action.
        """
        result = {
            "action_name": self.action_name,
            "is_static_function": self.is_static_function,
            "info": self.info,
            "return": self.func_return,
            "parameters": self.parameters,
            "doc_string": self.doc_string,
            "permission_role": self.permission_role}
        return result


def action(info: str = "", auth_header: str = None,
           request: str = None, permission_role: str = "can_run_actions"):
    """Define decorator that will convert the function into a rest action.

    Args:
        info (str):
            Just an information about the decorated function that will be
            returned in GET /rest/<model_class>/actions/.
        auth_header (str):
            Variable that will receive the auth_header, this can be used
            at the function to impersonation of the user to call other
            microservices.
        request (str):
            Pass the request as a parameter to the function. This variable
            will set the name of the argument that will receive request
            as parameter.
        permission_role (str):
            Set a permission role to by pass Pumpwood action permission
            validation. Role must be in `['can_delete', 'can_delete_file',
            'can_delete_many', 'can_list', 'can_list_without_pag',
            'can_retrieve', 'can_retrieve_file', 'can_run_actions',
            'can_save']`.

    Returns:
        Return decorated function.

    Example:
    ```python
    from pumpwood_djangoviews.action import action

    [...]

    # Action associated with a classmethod, is_static_function=True
    # when returning information of the action. auth_header will
    # be passed to function making possible to impersonate the user
    @classmethod
    @action(info='Dump dashboards and parameters', auth_header="auth_header")
    def dump_dashboards(cls,
                        dashboard_name: str,
                        auth_header: dict,
                        filter_alias: List[str] = None,
                        exclude_alias: List[str] = None) -> List[str]:
        test_data = microservice.retrieve(
            model_class='TestEndPoint',
            auth_header=auth_header)
        [...]

    # Action associated with a classmethod, is_static_function=False
    # when returning information of the action. Auth header won't be passed
    # as function argument.
    @action(info='Dump dashboards and parameters')
    def delete_dashboards(cls, dashboard_name: str) -> dict:
        [...]
    ```
    """
    def action_decorator(func):
        func.is_action = True
        func.action_object = Action(
            func=func, info=info, auth_header=auth_header,
            request=request, permission_role=permission_role)
        return func
    return action_decorator


def load_action_parameters(func: Callable, parameters: dict, request) -> dict:
    """Cast arguments to its original types.

    Args:
        func (Callable):
            Function that parameters will be casted according to function
            arguments tips.
        parameters (dict):
            Parameters received at execute action end-point, they will be
            casted according to funciton tips.
        request:
            Django request.

    Returns:
        Return parameters casted according to tips at function arguments.
    """
    signature = inspect.signature(func)
    function_parameters = signature.parameters
    # Loaded parameters for action run
    return_parameters = {}
    # Errors found when processing the parameters
    errors = {}
    # Unused parameters, passed but not in function
    unused_params = set(parameters.keys()) - set(function_parameters.keys())

    # The request user parameter, set the logged user
    auth_header_arg = func.action_object.auth_header
    request_arg = func.action_object.request

    if len(unused_params) != 0:
        errors["unused args"] = {
            "type": "unused args",
            "message": list(unused_params)}

    for key in function_parameters.keys():
        # pass if arguments are self and cls for classmethods
        if key in ['self', 'cls']:
            continue

        # If arguent correspont auth header, set with request auth header
        if key == auth_header_arg:
            token = request.headers.get('Authorization')
            return_parameters[key] = {'Authorization': token}
            continue

        # If arguent correspont request, set with request
        if key == request_arg:
            return_parameters[key] = request
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
