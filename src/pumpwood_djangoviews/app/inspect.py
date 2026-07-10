"""Class to inspect the application and extract actions and permissions."""
import inspect
from django.apps import apps
from slugify import slugify


class PumpwoodDjangoAppInspect:
    """Class to inspect the application and extract actions and permissions."""

    def __init__(self, app_name: str):
        """Initialize the AppInspect class."""
        self.app_name = app_name

    @classmethod
    def _resolve_local_model(cls, model_class: str):
        """Return Django model for a Pumpwood model_class string."""
        target = (model_class or '').lower()
        for model in apps.get_models():
            name = model.__name__
            if name.lower() == target:
                return model
            if slugify(name) == target:
                return model
        return None

    @classmethod
    def list_actions_local(cls, model_class: str):
        """List actions from local model without HTTP."""
        model = cls._resolve_local_model(model_class=model_class)
        if model is None:
            return None

        members = {}
        members.update(inspect.getmembers(model, inspect.isfunction))
        members.update(inspect.getmembers(model, inspect.ismethod))
        action_list = []
        for func in members.values():
            if not getattr(func, 'is_action', False):
                continue

            action_obj = getattr(func, 'action_object', None)
            if action_obj is not None:
                action_list.append(action_obj.to_dict())
        print("action_list", action_list)
        return action_list