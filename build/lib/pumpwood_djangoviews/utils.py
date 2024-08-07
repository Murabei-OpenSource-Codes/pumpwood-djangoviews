"""Miscellaneous auxiliary functions."""
from django.urls import reverse


def reverse_object_admin_url(obj, id: int = None) -> str:
    """
    Return Admin URL for an object.

    If id is set return object change admin URL, if not set list admin URL.

    Args:
        obj [object|model_class]:
            Object or Django model to be reversed.
        id [int]:
            Id of the object to be reversed.

    Returns:
        Reverse Admin URL.
    """
    if id is not None:
        return reverse(
            'admin:%s_%s_change' % (
                obj._meta.app_label,
                obj._meta.model_name),  args=[id])
    else:
        return reverse(
            'admin:%s_%s_changelist' % (
                obj._meta.app_label, obj._meta.model_name))
