"""Functions to run query at django using Pumpwood Rest API."""
from django.db.models import Q


def filter_by_dict(query_set, filter_dict={}, exclude_dict={}, order_by=[]):
    """
    Filter query using list dictonary.

    Filter query set using function args as argument for filter ORM function.
    filter_list for filter_list, exclude_list for exclude and order by or
    order by.

    Args:
        query_set:
            Django original query set.
        filter_dict [dict]:
            Dictionary to be used as argument of
            query_set.filter(**filter_dict).
        exclude_dict [dict]:
            Dictionary to be used as argument o
            query_set.exclude(**exclude_dict)
        order_by [list]:
            List with arguments for query_set.order_by(*order_by)
    Returns:
        Filtered query set.
    """
    q_arg = None
    for key, value in filter_dict.items():
        # Check if JSON fields are being fetched and change key to django
        # sintaxe
        kwargs = {}
        if "->" in key:
            key = key.replace("->", "__")
        kwargs[key] = value

        temp_q_arg = Q(**kwargs)
        if q_arg is not None:
            q_arg = q_arg & temp_q_arg
        else:
            q_arg = temp_q_arg

    for key, value in exclude_dict.items():
        # Check if JSON fields are being fetched and change key to django
        # sintaxe
        kwargs = {}
        if "->" in key:
            key = key.replace("->", "__")
        kwargs[key] = value

        # For exclude arguents set as NOT true at filter
        temp_q_arg = ~Q(**kwargs)
        if q_arg is not None:
            q_arg = q_arg & temp_q_arg
        else:
            q_arg = temp_q_arg

    # Check if JSON fields are being fetched and change key to django
    # sintaxe
    order_by = [o.replace("->", "__") for o in order_by]
    if q_arg is None:
        return query_set\
            .order_by(*order_by)
    else:
        return query_set\
            .filter(q_arg)\
            .order_by(*order_by)
