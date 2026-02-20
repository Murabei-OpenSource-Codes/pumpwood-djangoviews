"""Auxiliary funcitons for fields and serializers."""
import importlib


def _import_function_by_string(module_function_string):
    """Help when importing a function using a string."""
    # Split the module and function names
    module_name, function_name = module_function_string.rsplit('.', 1)
    # Import the module
    module = importlib.import_module(module_name)
    # Retrieve the function
    func = getattr(module, function_name)
    return func
