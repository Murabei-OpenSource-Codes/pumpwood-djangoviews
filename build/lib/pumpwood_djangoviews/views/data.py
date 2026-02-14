"""Create data views using Pumpwood pattern.

Define base views associated with Pumpwood end-points.
"""
import pandas as pd
from typing import Union
from rest_framework.response import Response
from pumpwood_communication import exceptions
from pumpwood_djangoviews.query import filter_by_dict
from pumpwood_djangoviews.views.simple import PumpWoodRestService


class PumpWoodDataBaseRestService(PumpWoodRestService):
    """This view extends PumpWoodRestService, including pivot function.

    This view will make data end-points avaiable at frontend for retriving
    data without the use of serializers using pivot end-point and bulk
    save of data using bulk-save end-point.
    """

    _view_type = "data"

    model_variables = []
    """Specify which model variables will be returned in pivot. Line index are
       the model_variables - columns (function pivot parameter) itens."""
    expected_cols_bulk_save = []
    """Set the collumns needed at bulk_save."""

    def pivot(self, request) -> Union[list, dict]:
        """Pivot QuerySet data acording to columns selected, and filters.

        ###### Request payload data:
        `filter_dict`, `exclude_dict` and `order_by` parameters have same
        behaviour as list end-point.

        - **columns [List[str]]:**
            List of variables that will be considered as collumns to pivot
            data.
        - **format [{‘dict’, ‘list’, ‘series’, ‘split’, ‘tight’, ‘records’,
            ‘index’}]:** Format paramter to convert pandas DataFrame to
            dictonary. This dictonary will be returned by the function.
        - **variables [List[str]]:** Variables to be returned, this will
            modify default behaviour of returning `model_variables` attribute
            fields.
        - **show_deleted [bool]:** If model has deleted field, results
            flaged as deleted won't be fetched. Setting show_deleted = True
            will return this filtered results.
        - **add_pk_column [bool]:** If True, pk columns will be added to
            results. Using pk columns will not permit to pivot information
            (makes no sense). So far only `id` column will be added to results
            treating composite pks is on the roadmap.
        - **limit [int]:** Limit of the query results (number of objects that
            will be returned).

        ###### Request query data:
        No query parameters.

        Returns:
            Return a pandas DataFrame serialized according to format
            parameter.

        Raises:
            PumpWoodForbidden:
                'Pivot is not avaiable, set model_variables at view'. Indicates
                that this end-point is not avaiable. To habilitate it, it is
                necessary to set `model_variables` attribute at view.
            PumpWoodQueryException:
                'Columns must be a list of elements.'. Indicates that columns
                type is not a list of strings.
            PumpWoodQueryException:
                'Column chosen as pivot is not at model variables'. Indicates
                that column is not present on `model_variables` attribute.
            PumpWoodQueryException:
                Propagate errors raised when executing the query.
            PumpWoodQueryException:
                'value column not at melted data, it is not possible
                 to pivot dataframe.'. Indicates that value column is not
                 avaiable query results, so it not possible to pivot data.
        """
        if len(self.model_variables) == 0:
            msg = "Pivot is not avaiable, set model_variables at view"
            raise exceptions.PumpWoodForbidden(msg)

        columns = request.data.get('columns', [])
        format = request.data.get('format', 'list')
        model_variables = (
            request.data.get('variables') or self.model_variables)
        show_deleted = request.data.get('show_deleted', False)
        add_pk_column = request.data.get('add_pk_column', False)
        limit = request.data.get('limit', None)

        if type(columns) is not list:
            raise exceptions.PumpWoodQueryException(
                'Columns must be a list of elements.')
        if len(set(columns) - set(model_variables)) != 0:
            raise exceptions.PumpWoodQueryException(
                'Column chosen as pivot is not at model variables')

        index = list(set(model_variables) - set(columns))
        filter_dict = request.data.get('filter_dict', {})
        exclude_dict = request.data.get('exclude_dict', {})
        order_by = request.data.get('order_by', {})

        if hasattr(self.service_model, 'deleted'):
            if not show_deleted:
                filter_dict["deleted"] = False

        #############################
        # Add id columns to results #
        # TODO: Add other fields if set as composite primary key.
        if add_pk_column:
            if len(columns) != 0:
                raise exceptions.PumpWoodException(
                    "Can not add pk column and pivot information")
            model_variables = ['id'] + model_variables

        # Limit pivot results if limit parameter is set
        query_set = self.base_query(request=request)
        if limit is not None:
            query_set = query_set[:int(limit)]

        arg_dict = {
            'query_set': query_set,
            'filter_dict': filter_dict, 'exclude_dict': exclude_dict,
            'order_by': order_by}
        query_set = filter_by_dict(**arg_dict)

        try:
            filtered_objects_as_list = list(
                query_set.values_list(*(model_variables)))
        except TypeError as e:
            raise exceptions.PumpWoodQueryException(message=str(e))

        melted_data = pd.DataFrame(
            filtered_objects_as_list, columns=model_variables)

        if len(columns) == 0:
            return Response(melted_data.to_dict(format))

        if melted_data.shape[0] == 0:
            return Response({})
        else:
            if "value" not in melted_data.columns:
                raise exceptions.PumpWoodQueryException(
                    "'value' column not at melted data, it is not possible"
                    " to pivot dataframe.")

            pivoted_table = pd.pivot_table(
                melted_data, values='value', index=index,
                columns=columns, aggfunc=lambda x: tuple(x)[0])

            return Response(
                pivoted_table.reset_index().to_dict(format))

    def bulk_save(self, request) -> dict:
        r"""Bulk save data.

        This end-point is prefereble for large datainputs on Pumpwood, it is
        not possible to update entries, just add new ones.

        It is much more performant than adding one by one using save
        end-point.

        ###### Request payload data:
        List of dictionaries which must have self.expected_cols_bulk_save.

        ###### Request query data:
        No query parameters.

        Args:
            request:
                Django request.

        Returns:
            A dictonary with key `saved_count` indicating the number of
            objects that were add to database.

        Raises:
            PumpWoodForbidden:
                'Bulk save not avaiable. Set expected_cols_bulk_save on
                PumpWoodDataBaseRestService View to habilitate funciton.'
                Indicates that bulk_save end-point was not configured
                for this model class. It is necessary to set
                `expected_cols_bulk_save` attribute to make end-point
                avaiable.
            PumpWoodObjectSavingException:
                'Post payload is a list of objects.'. Indicates that the
                request payload is not a list as expected.
            PumpWoodObjectSavingException:
                'Expected columns and data columns do not match:
                \nExpected columns:{expected}
                \nData columns:{data_cols}'. Indicates that the fields passed
                on the objects are diferent from the expected by the end-point
                check the data or the configuration of the end-point.
        """
        if len(self.expected_cols_bulk_save) == 0:
            msg = (
                "Bulk save not avaiable. Set expected_cols_bulk_save on "
                "PumpWoodDataBaseRestService View to habilitate funciton.")
            raise exceptions.PumpWoodForbidden(msg)

        data_to_save = request.data
        if type(data_to_save) is not list:
            raise exceptions.PumpWoodObjectSavingException(
                'Post payload is a list of objects.')

        pd_data_to_save = pd.DataFrame(data_to_save)
        pd_data_cols = set(list(pd_data_to_save.columns))

        if len(set(self.expected_cols_bulk_save) - pd_data_cols) == 0:
            objects_to_load = []
            for d in data_to_save:
                new_obj = self.service_model(**d)
                objects_to_load.append(new_obj)

            self.service_model.objects.bulk_create(objects_to_load)
            return Response({'saved_count': len(objects_to_load)})
        else:
            msg = (
                'Expected columns and data columns do not match:' +
                '\nExpected columns:{expected}' +
                '\nData columns:{data_cols}')
            raise exceptions.PumpWoodObjectSavingException(
                    message=msg,
                    payload={
                        "expected": list(self.expected_cols_bulk_save),
                        "data_cols": pd_data_cols})
