"""Functions to run query at django using Pumpwood Rest API."""
from django.db.models import Q, Sum, Avg, Count, Max, Min, StdDev, Variance
from typing import List, Dict
from pumpwood_communication.exceptions import (
    PumpWoodQueryException, PumpWoodNotImplementedError)


def filter_by_dict(query_set, filter_dict: dict = None,
                   exclude_dict: dict = None, order_by: list = None,
                   **kwargs):
    """Filter query using list dictonary.

    Filter query set using function args as argument for filter ORM function.
    filter_list for filter_list, exclude_list for exclude and order by or
    order by.

    Args:
        query_set:
            Django original query set.
        filter_dict (dict):
            Dictionary to be used as argument of
            query_set.filter(**filter_dict).
        exclude_dict (dict):
            Dictionary to be used as argument o
            query_set.exclude(**exclude_dict)
        order_by (dict):
            List with arguments for query_set.order_by(*order_by)
        **kwargs:
            Other unused parameters to help with function call compatibility.

    Returns:
        Filtered query set.
    """
    filter_dict = {} if filter_dict is None else filter_dict
    exclude_dict = {} if exclude_dict is None else exclude_dict
    order_by = [] if order_by is None else order_by

    q_arg = None
    for key, value in filter_dict.items():
        # Check if JSON fields are being fetched and change key to Django
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
        # Check if JSON fields are being fetched and change key to Django
        # sintaxe
        kwargs = {}
        if "->" in key:
            key = key.replace("->", "__")
        kwargs[key] = value

        # For exclude arguments set as NOT true at filter
        temp_q_arg = ~Q(**kwargs)
        if q_arg is not None:
            q_arg = q_arg & temp_q_arg
        else:
            q_arg = temp_q_arg

    # Check if JSON fields are being fetched and change key to Django
    # sintaxe
    order_by = [o.replace("->", "__") for o in order_by]
    if q_arg is None:
        return query_set\
            .order_by(*order_by)
    else:
        return query_set\
            .filter(q_arg)\
            .order_by(*order_by)


def aggregate_by_dict(query_set, group_by: List[str], agg: Dict,
                      order_by: List[str] = [], **kwargs):
    """Create Django query for aggregation end-point.

    ..: notes::
        Aggregation functions implemented:
        - sum: Calculate the sum of elements, translates to Sum Django ORM.
        - mean: Calculate the mean of elements, translates Avg Django ORM.
        - count: Count elements, translates Count Django ORM.
        - min: Calculate the min value of elements, translates Min Django ORM.
        - max: Calculate the max value of elements, translates Max Django ORM.
        - std: Calculate the standard desviation value of elements, translates
            StdDev Django ORM. It correponds to **population** standard
            desviation.
        - var: Calculate the variance value of elements, translates Variance
            Django ORM. It correponds to **population** variance.

    Args:
        query_set:
            Django query set to perform aggregation over.
        group_by (List[str]):
            List of fields that will be used at group_by clause.
        agg (Dict):
            Definition of the aggregation clause of the query, result column
            will return as the key of the dictionary. It is set as a dictonary
            with keys 'field' inidicating on which field to perform aggregation
            and 'function' setting the aggregation function.
        order_by (List[str]):
            Ordenation of the fields after aggregation.
        **kwargs:
            Other unused parameters to help with function call compatibility.

    Returns:
        A query set with results of aggregation. It will return the columns
        that were set on group_by list and keys of the agg as columns with
        the results of the aggregations.
    """
    DICT_ORM = {
        'sum': Sum, 'mean': Avg, 'count': Count, 'min': Min, 'max': Max,
        'std': StdDev, 'var': Variance}

    # Create a dictionary with arguments for annotate function on Django
    annotate_args = {}
    for key, value in agg.items():
        field = value.get('field')
        function = value.get('function')
        is_not_val_arg_type = (
            (type(field) is not str) or
            (type(function) is not str))
        if is_not_val_arg_type:
            msg = (
                "agg key [{key}] field [{field}] or function [{function}] are "
                "not strings or are None")
            raise PumpWoodQueryException(
                message=msg, payload={
                    'key': key, 'field': field, 'function': function})

        django_orm_fun = DICT_ORM.get(function)
        if django_orm_fun is None:
            msg = (
                "agg key [{key}] function [{function}] is not implemented")
            raise PumpWoodNotImplementedError(
                message=msg, payload={
                    'key': key, 'function': function})

        annotate_args[key] = django_orm_fun(field)

    # Apply group_by fields using values, aggregate them according to
    # annotate parameters and after that order the results (including
    # aggregation fields)
    if len(group_by) != 0:
        return query_set\
            .values(*group_by)\
            .annotate(**annotate_args)\
            .order_by(*order_by)
    else:
        # Aggregate result is a dictonary, to keep pattern it will be returned
        # as a list with one entry
        return [query_set.aggregate(**annotate_args)]
