"""Create views using Pumpwood pattern.

Define base views associated with Pumpwood end-points.
"""
import os
import pandas as pd
import simplejson as json
import datetime
import pumpwood_djangoauth.i8n.translate as _
import copy
from io import BytesIO
from typing import List, Union
from django.db import models
from django.http import HttpResponse
from django.db.models.fields import NOT_PROVIDED
from django.db.models.fields.files import FieldFile
from rest_framework import viewsets, status
from rest_framework.response import Response
from werkzeug.utils import secure_filename
from pumpwood_miscellaneous.storage import PumpWoodStorage
from pumpwood_communication import exceptions
from pumpwood_communication.microservices import PumpWoodMicroService
from pumpwood_djangoviews.rest import PumpwoodJSONRenderer
from pumpwood_djangoviews.query import filter_by_dict, aggregate_by_dict
from pumpwood_djangoviews.action import load_action_parameters
from pumpwood_djangoviews.aux.map_django_types import django_map
from pumpwood_djangoviews.serializers import (
    MicroserviceForeignKeyField, MicroserviceRelatedField,
    LocalForeignKeyField, LocalRelatedField, DynamicFieldsModelSerializer)


def save_serializer_instance(serializer_instance):
    """Save instant using serializer and raise if any validation error.

    Is is not valid acording to serializer validation, raise error.

    Args:
        serializer_instance:
            Serializer with an object to be saved.

    Returns:
        New object updated or created.

    Raises:
        PumpWoodObjectSavingException:
            'Error when validating fields when saving object'. Raise error if
            validation of serializer is not correct. It will return error
            dictonary at error payload.
    """
    is_valid = serializer_instance.is_valid()
    if is_valid:
        return serializer_instance.save()
    else:
        raise exceptions.PumpWoodObjectSavingException(
            message="Error when validating fields when saving object",
            payload=serializer_instance.errors)


class PumpWoodRestService(viewsets.ViewSet):
    """Basic View-Set for pumpwood rest end-points.

    Example:
    ```python
    from metabase.models import MetabaseDashboard
    from metabase.serializers import MetabaseDashboardSerializer
    from config import storage_object, microservice


    class RestMetabaseDashboard(PumpWoodRestService):
        endpoint_description = "Metabase Dashboard"
        notes = "Register and generate url to embed Metabase dashboards"

        # Django model that will be mapped to this end-point
        service_model = MetabaseDashboard

        # Serializer that will be used to dump model data
        serializer = MetabaseDashboardSerializer

        # PumpwoodStorage object that will be used to save and retrieve
        # file data from storage.
        storage_object = storage_object

        # PumpWoodMicroService object used to communicate with other
        # microservice if necessary. Ex: Trigger ETL Jobs on object
        # saving and update.
        microservice = microservice

        # Fields that will be considered as files and extensions that
        # will be accepted.
        file_fields = {
            'file': ['json', 'xlsx']
        }

        ###########################################################
        # Gui this information will be returned at retrieve_options
        # to help frontend correctly render app frontend.
        # Set field sets, grouping the fields and hiding those that
        # ar not listed on fieldsets
        gui_retrieve_fieldset = [{
                "name": "main",
                "fields": [
                    "status", "alias", "description", "notes",
                    "dimensions", "updated_by", "updated_at"]
            }, {
                "name": "embedding",
                "fields": [
                    "metabase_id", "auto_embedding", "object_model_class",
                    "object_pk"]
            }, {
                "name": "config",
                "fields": [
                    "expire_in_min", "default_theme",
                    "default_is_bordered", "default_is_titled"]
            }, {
                "name": "extra_info",
                "fields": ["extra_info"]
            }
        ]

        # This fields will be set as readonly if fill_options_validation
        # is called with query parameter `?user_type=gui`
        gui_readonly = ["updated_by_id", "updated_at", "extra_info"]

        # Indication how the object could be presented to user
        gui_verbose_field = '{pk} | {description}'
    ```
    """

    _view_type = "simple"
    renderer_classes = [PumpwoodJSONRenderer]

    #####################
    # Route information #
    endpoint_description: str = None
    """Description of the end-point, this information will be avaiable at
       `rest/pumpwood/endpoints/` for frontend. This information will be
       saved at KongRoute, it must be unique for all microservices"""
    dimensions: dict = {}
    """Dimensions associated with end-points. This information will be saved
       at KongRoute dimensions."""
    icon: str = None
    """Icon associated with model class. This information will be saved
       at KongRoute icon field."""
    #####################

    service_model: models.Model
    """Django model associated end-points will be made avaiable."""
    storage_object: PumpWoodStorage
    """PumpwoodStorage object that will be used to save and retrieve
       file data from storage."""
    microservice: PumpWoodMicroService = None
    """PumpWoodMicroService object used to communicate with other
       microservice if necessary. Ex: Trigger ETL Jobs on object
       saving and update."""
    trigger: bool = False
    """If should be called ELTTrigger at ETL microservice at saving, deleting
       and executing actions. Default value is False."""

    # List fields
    serializer: DynamicFieldsModelSerializer
    """Serializer that will be used to dump data on end-points."""
    file_fields = {}
    """File fields associated with model, it is a dictonary with keys as
       field keys and values as a list of accepted extensions."""

    # Front-end uses 50 as limit to check if all data have been fetched,
    # if change this parameter, be sure to update front-end list component.
    list_paginate_limit: int = 50
    """List end-point pagination default limit."""

    #######
    # Gui #
    gui_retrieve_fieldset: List[dict] = None
    """Retrieve field set to be passed to gui from `retrieve_view_options`.
       It is a list of dictonary with keys name for name of the viewset and
       fields for the fields that are associated.

       Example:
       ```python
       gui_retrieve_fieldset = [{
               "name": "main",
               "fields": [
                   "status", "alias", "description", "notes",
                   "dimensions", "updated_by", "updated_at"]
           }, {
               "name": "embedding",
               "fields": [
                   "metabase_id", "auto_embedding", "object_model_class",
                   "object_pk"]
           }, {
               "name": "config",
               "fields": [
                   "expire_in_min", "default_theme",
                   "default_is_bordered", "default_is_titled"]
           }, {
               "name": "extra_info",
               "fields": ["extra_info"]
           }
       ]
       ```
    """
    gui_verbose_field: str = 'pk'
    """Suggest verbose for object using information from object. It is set
       as python string format, default `pk`. Ex: `{pk} | {description}` will
       use information from `pk` and `description` keys."""
    gui_readonly: List[str] = []
    """Set readonly fields when calling with `user_type=gui` for
       `fill_options_validation` end-point."""
    #######

    ###############################
    # Gui attribute get functions #
    @classmethod
    def get_gui_retrieve_fieldset(cls) -> List[dict]:
        """Return gui_retrieve_fieldset attribute.

        This function can be overwriten to add custom funcionalities
        to get `gui_retrieve_fieldset` attribute.

        Returns:
            Return `gui_retrieve_fieldset` attribute.
        """
        return cls.gui_retrieve_fieldset

    @classmethod
    def get_gui_verbose_field(cls) -> str:
        """Return gui_verbose_field attribute.

        This function can be overwriten to add custom funcionalities
        to get `gui_verbose_field` attribute.

        Returns:
            Return `gui_verbose_field` attribute.
        """
        return cls.gui_verbose_field

    @classmethod
    def get_gui_readonly(cls) -> List[str]:
        """Return gui_readonly attribute.

        This function can be overwriten to add custom funcionalities
        to get `gui_readonly` attribute.

        Returns:
            Return `gui_readonly` attribute.
        """
        return cls.gui_readonly

    @classmethod
    def get_list_fields(cls):
        """Return list_fields from associated serializer.

        This function can be overwriten to add custom funcionalities
        to get `cls.serializer().get_list_fields()` data.

        Returns:
            Return list_fields for model.
        """
        serializer_obj = cls.serializer()
        return serializer_obj.get_list_fields()
    ########################

    @staticmethod
    def _allowed_extension(filename, allowed_extensions):
        extension = 'none'
        if '.' in filename:
            extension = filename.rsplit('.', 1)[1].lower()

        if "*" not in allowed_extensions:
            if extension not in allowed_extensions:
                return [(
                    "File {filename} with extension {extension} not " +
                    "allowed.\n Allowed extensions: {allowed_extensions}"
                ).format(filename=filename, extension=extension,
                         allowed_extensions=str(allowed_extensions))]
        return []

    def base_query(self, request, **kwargs):
        """Definition of an access filter to limit viewing of objects.

        ..: notes:
            As the queries on the service_model relies on this method,
            the query returned by this method will modify any other query on
            this view.

        Args:
            request:
                Django request object.
            **kwargs:
                Help when inheriting class.

        Returns:
            Returns a Django ORM query filtering the results according to
            user permitions if implemented. This function is used on retrieve
            and list end-points, limiting user access.
        """
        return self.service_model.objects.all()

    def list(self, request) -> List[dict]:
        """View function to list objects with pagination.

        Number of objects are limited by. To get next page, use
        exclude_dict['pk__in': [list of the received pks]] to get more
        objects.

        ..: notes:
            Models with deleted field will have objects with deleted=True
            excluded by default from results. To retrive these objects
            explicity define `exclude_dict` `{'deleted': None}` or
            `{'deleted': False}`.

        Use to limit the query .query.filter_by_dict function. Request
        expected parameters and query parameters are listed bellow:

        ###### Request payload data:
        - **filter_dict [dict] = {}:**
            Dictionary passed as `model.objects.filter(**filter_dict)`.<br>
        - **exclude_dict [dict] = {}:**
            Dictionary passed as
            `model.objects.exclude(**filter_dict)`.<br>
        - **order_by [dict] = []:**
            Dictionary passed as `model.objects.exclude(*order_by)`.<br>
        - **limit [int] = None:**
            Limit of the query result, if not set attribute
            `list_paginate_limit` will be used insted.<br>
        - **fields [List[str]] = []:**
            List of fields that should be returned on results objects.<br>
        - **default_fields [bool] = False:**
            If serializer `list_fields` should be used to filter the
            returned fields.<br>
        - **foreign_key_fields [bool] = False:**
            If foreign keys should be returned with object data.<br>

        ###### Request query data:
        No query data.

        Args:
            request: Django request object.

        Returns:
            Return the result of the query limited to
            `list_paginate_limit` attribute. Objects are serialized
            using `serializer` attribute.

        Raises:
            PumpWoodQueryException:
                Raise if any error when treating the request.
        """
        try:
            request_data = request.data
            limit = request_data.pop("limit", None)
            list_paginate_limit = limit or self.list_paginate_limit

            # Serializer parameters
            fields = request_data.pop("fields", None)
            default_fields = request_data.pop("default_fields", False)
            foreign_key_fields = request_data.pop("foreign_key_fields", False)

            ################################################################
            # Do not display deleted objects if not explicity set to display
            exclude_dict = request_data.get("exclude_dict") or {}
            if hasattr(self.service_model, 'deleted'):
                exclude_dict_keys = exclude_dict.keys()
                any_delete = False
                for key in exclude_dict_keys:
                    first = key.split("__")[0]
                    if first == "deleted":
                        any_delete = True
                        break
                if not any_delete:
                    exclude_dict["deleted"] = True
            ################################################################

            arg_dict = {'query_set': self.base_query(request=request)}
            arg_dict.update(request_data)
            query_set = filter_by_dict(**arg_dict)[:list_paginate_limit]

            return Response(self.serializer(
                query_set, many=True, fields=fields,
                foreign_key_fields=foreign_key_fields,
                default_fields=default_fields,
                context={'request': request}).data)
        except Exception as e:
            raise exceptions.PumpWoodQueryException(message=str(e))

    def list_without_pag(self, request):
        """View function to list objects **without** pagination.

        ..: notes::
            Models with deleted field will have objects with deleted=True
            excluded by default from results. To retrive these objects
            explicity define `exclude_dict` `{'deleted': None}` or
            `{'deleted': False}`.

        ..: warning::
            Be careful with the number of the objects that will be fetched!
            This end-point does not paginate data returning all information
            of query result.

        ###### Request payload data:
        - **filter_dict [dict] = {}:**
            Dictionary passed as `model.objects.filter(**filter_dict)`.<br>
        - **exclude_dict [dict] = {}:**
            Dictionary passed as
            `model.objects.exclude(**filter_dict)`.<br>
        - **order_by [dict] = []:**
            Dictionary passed as `model.objects.exclude(*order_by)`.<br>
        - **fields [List[str]] = []:**
            List of fields that should be returned on results objects.<br>
        - **default_fields [bool] = False:**
            If serializer `list_fields` should be used to filter the
            returned fields.<br>
        - **foreign_key_fields [bool] = False:**
            If foreign keys should be returned with object data.<br>

        ###### Request query data:
        No query data.

        Args:
            request: Django request object.

        Returns:
            Return the result of the query **without** pagination . Objects
            are serialized using `serializer` attribute.

        Raises:
            PumpWoodQueryException:
                Raise if any error when treating the request.
        """
        try:
            request_data = request.data

            # Serializer parameters
            fields = request_data.pop("fields", None)
            default_fields = request_data.pop("default_fields", False)
            foreign_key_fields = request_data.pop("foreign_key_fields", False)

            ################################################################
            # Do not display deleted objects if not explicity set to display
            exclude_dict = request_data.get("exclude_dict", {})
            if hasattr(self.service_model, 'deleted'):
                exclude_dict_keys = exclude_dict.keys()
                any_delete = False
                for key in exclude_dict_keys:
                    first = key.split("__")[0]
                    if first == "deleted":
                        any_delete = True
                        break
                if not any_delete:
                    exclude_dict["deleted"] = True
            ################################################################

            arg_dict = {'query_set': self.base_query(request=request)}
            arg_dict.update(request_data)

            query_set = filter_by_dict(**arg_dict)
            return Response(self.serializer(
                query_set, many=True, fields=fields,
                default_fields=default_fields,
                foreign_key_fields=foreign_key_fields,
                context={'request': request}).data)

        except TypeError as e:
            raise e
            raise exceptions.PumpWoodQueryException(
                message=str(e))

    def retrieve(self, request, pk=None) -> dict:
        """Retrieve view to return object with pk.

        Query parameters are loaded as json data, ex:
        `json.loads(request.query_params.get('fields', 'null'))`

        ###### Request payload data:
        GET request only, does not have payload.

        ###### Request query data:
        - **fields [List[str]] = None:** List of the fields that should be
            returned.
        - **foreign_key_fields [bool] = False:** If foreign key should be
            returned with object data.
        - **related_fields [bool] = False:** If related fields should be
            returned with object data.
        - **default_fields [bool] = False:** If only serializer list_fields
            should be returned.

        Args:
            request (pk):
                Django request.
            pk (int):
                Object pk to be retrieve.

        Returns:
            The representation of the object with pk dumped by
            self.serializer using arguments passed on query parameters.
        """
        ##########################
        # Get serializer options #
        fields = json.loads(
            request.query_params.get('fields', 'null'))
        foreign_key_fields = json.loads(
            request.query_params.get('foreign_key_fields', 'false'))
        related_fields = json.loads(
            request.query_params.get('related_fields', 'false'))
        default_fields = json.loads(
            request.query_params.get('default_fields', 'false'))
        ##########################

        obj = self.base_query(request=request).get(pk=pk)
        response_data = self.serializer(
            obj, many=False, fields=fields,
            foreign_key_fields=foreign_key_fields,
            related_fields=related_fields,
            default_fields=default_fields,
            context={'request': request}).data
        return Response(response_data)

    def retrieve_file(self, request, pk: int) -> bytes:
        """Read file without stream.

        .. warning::
            This end-point will read de file from storage and them return the
            request. Be carefull when retriving large files (greater than
            10Mb).

        ###### Request payload data:
        GET request only, does not have payload.

        ###### Request query data:
        - **file_field [str]:** File field to receive stream file.
            returned with object data.

        Args:
            request:
                Django request.
            pk (int):
                Pk of the object to save file field.

        Returns:
            Return a file associated with object pk, file field `file_field`
            read from storage.

        Raises:
            PumpWoodForbidden:
                '{field} must be set on file_fields dictionary.'. Indicates
                that the requested file field was not found on view
                `file_fields` attribute.
            PumpWoodForbidden:
                'storage_object not set'. Indicates that the `storage_object`
                attribute is not set at view. This view can not perform
                file operations.
            PumpWoodObjectDoesNotExist:
                'field [{}] is not set at object'. Indicates that requested
                file field is not set on object.
        """
        if self.storage_object is None:
            raise exceptions.PumpWoodForbidden(
                "storage_object not set")

        file_field = request.query_params.get('file-field', None)
        if file_field not in self.file_fields.keys():
            msg = (
                "file-field[{file_field}] must be set on file_fields "
                "dictionary")
            raise exceptions.PumpWoodForbidden(
                msg, payload={
                    'file_field': file_field})

        obj = self.base_query(request=request).get(id=pk)
        file_path = getattr(obj, file_field)
        if isinstance(file_path, FieldFile):
            file_path = file_path.name

        if not file_path:
            raise exceptions.PumpWoodObjectDoesNotExist(
                "file-field[{file_field}] is not set at object",
                payload={"file_field": file_field})
        file_data = self.storage_object.read_file(file_path)
        file_name = os.path.basename(file_path)

        response = HttpResponse(content=BytesIO(file_data["data"]))
        response['Content-Type'] = file_data["content_type"]
        response['Content-Disposition'] = \
            'attachment; filename=%s' % file_name
        return response

    def delete(self, request, pk=None) -> dict:
        """Delete view.

        .. notes::
            If model has deleted field, the default behaviour will set this
            field to True not deleting the object. To force deletion it is
            necessary to use query paramenter `force_delete=True`

        ###### Request payload data:
        GET request only, does not have payload.

        ###### Request query data:
        - **force_delete [bool] = False:** Force deletion of models that
            have `deleted` field. If False, object with deleted
            will not be deleted, but deleted will be set as True.

        Args:
            request:
                Django request.
            pk (int):
                Object pk to be retrieve.

        Returns:
            Return the object that was removed.
        """
        obj = self.base_query(request=request).get(pk=pk)
        force_delete = json.loads(request.query_params.get(
            'force_delete', 'false'))
        return_data = self.serializer(
            obj, many=False, context={'request': request}).data

        # If object has deleted field, set it to True if force_delete
        # parameter is not set, this will function for objects that
        # deletion is not a good pratice for keep data audit.
        if hasattr(obj, 'deleted') and not force_delete:
            obj.deleted = True
            obj.save()
        else:
            obj.delete()
        return Response(return_data, status=200)

    def delete_many(self, request) -> bool:
        """Delete many data using filter.

        .. warning::
            This action will delete all objects that satisfies the query
            filter_dict and exclude_dict. It will also delete objects with
            deleted fields. **THIS REQUEST CAN NOT BE UNDONE**.

        ###### Request payload data:
        GET request only, does not have payload.

        ###### Request query data:
        - **filter_dict [dict] = {}:**
            Dictionary passed as `model.objects.filter(**filter_dict)`.<br>
        - **exclude_dict [dict] = {}:**
            Dictionary passed as
            `model.objects.exclude(**filter_dict)`.<br>

        Args:
            request:
                Django request.

        Returns:
            True if operation has completed.

        Raises:
            PumpWoodObjectDeleteException:
                If any error raised when performing request.
        """
        try:
            arg_dict = {'query_set': self.base_query(request=request)}
            arg_dict.update(request.data)

            query_set = filter_by_dict(**arg_dict)
            query_set.delete()
            return Response(True, status=200)
        except Exception as e:
            raise exceptions.PumpWoodObjectDeleteException(
                message=str(e))

    def remove_file_field(self, request, pk: int) -> bool:
        """Remove file field.

        ###### Request payload data:
        GET request only, does not have payload.

        ###### Request query data:
        - **file_field [str]:**
            File field associated with a file that will be removed.<br>

        Args:
            request:
                Django request.
            pk (int):
                pk of the object.

        Returns:
            True if the object was removed.

        Raises:
            PumpWoodForbidden:
                'file_field must be set on self.file_fields dictionary.'.
                Indicates that `file_file` is not in file_fields keys of
                the view.
            PumpWoodObjectDoesNotExist:
                'field [{}] not found at object'. Indicates that file was not
                found on storage.
        """
        file_field = request.query_params.get('file-field', None)
        if file_field not in self.file_fields.keys():
            msg = (
                "file-field[file_field] must be set on " +
                "self.file_fields dictionary.")
            raise exceptions.PumpWoodForbidden(
                message=msg, payload={"file_field": file_field})
        obj = self.base_query(request=request).get(id=pk)

        is_file_field = hasattr(obj, file_field)
        if not is_file_field:
            msg = (
                "file-field[{file_field}] is not an attribute of the object")
            raise exceptions.PumpWoodObjectDoesNotExist(
                message=msg, payload={"file_field": file_field})

        file = getattr(obj, file_field)
        if file is None or file == "":
            msg = (
                "file[{file_field}] is not set on object")
            raise exceptions.PumpWoodObjectDoesNotExist(
                message=msg, payload={"file_field": file_field})

        file_path = file.name
        setattr(obj, file_field, None)
        obj.save()

        try:
            self.storage_object.delete_file(file_path)
            return Response(True)
        except Exception as e:
            raise exceptions.PumpWoodException(str(e))

    def save(self, request) -> dict:
        """Save and update object acording to request.data.

        Object will be updated if request.data['pk'] is not None.

        ###### Request payload data:
        Object to be saved. If a pk is set them the object will be updated,
        if pk is None or not set a new object will be created.

        ###### Request query data:
        No query parameters.

        Args:
            request:
                Django request.

        Returns:
            Serialized new/updated object.

        Raises:
            PumpWoodException:
                'Object model class diferent from {service_model} :
                {service_model}'. Indicates that the end-point and the
                model_class of the object are impatible.
            PumpWoodObjectSavingException:
                'Error when validating fields when saving object'. Indicates
                that there were error when validating object
                at the serializer. Error payload will have the fields with
                error as keys of the dictonary.
        """
        request_data: dict = None
        if "application/json" in request.content_type.lower():
            request_data = request.data
        else:
            request_data = request.data.dict()
            json_data = json.loads(request_data.pop("__json__", '{}'))
            request_data.update(json_data)

        data_pk = request_data.get('pk')
        saved_obj = None
        for field in self.file_fields.keys():
            request_data.pop(field, None)

        # update
        if data_pk:
            data_to_update = self.base_query(request=request).get(pk=data_pk)
            serializer = self.serializer(
                data_to_update, data=request_data,
                context={'request': request})
            saved_obj = save_serializer_instance(serializer)
            response_status = status.HTTP_200_OK
        # save
        else:
            serializer = self.serializer(
                data=request_data, context={'request': request})
            saved_obj = save_serializer_instance(serializer)
            response_status = status.HTTP_201_CREATED

        # Uploading files
        object_errors = {}
        file_save_time = datetime.datetime.utcnow().strftime(
            "%Y-%m-%dT%Hh%Mm%Ss")
        for field in self.file_fields.keys():
            field_errors = []
            if field in request.FILES:
                file = request.FILES[field]

                file_name = secure_filename(file.name)
                field_errors.extend(self._allowed_extension(
                    filename=file_name,
                    allowed_extensions=self.file_fields[field]))

                filename = "{}___{}___{}".format(
                    str(saved_obj.id).zfill(15),
                    file_save_time,
                    file_name)
                if len(field_errors) != 0:
                    object_errors[field] = field_errors
                else:
                    model_class = self.service_model.__name__.lower()
                    file_path = '{model_class}__{field}/'.format(
                        model_class=model_class, field=field)
                    storage_filepath = self.storage_object.write_file(
                        file_path=file_path, file_name=filename,
                        data=file.read(),
                        content_type=file.content_type,
                        if_exists='overwrite')
                    setattr(saved_obj, field, storage_filepath)

        if object_errors != {}:
            message = "error when saving object: " \
                if data_pk is None else "error when updating object: "
            payload = object_errors
            message_to_append = []
            for key, value in object_errors.items():
                message_to_append.append(key + ", " + str(value))
            message = message + "; ".join(message_to_append)
            raise exceptions.PumpWoodObjectSavingException(
                message=message, payload=payload)
        saved_obj.save()

        if hasattr(self, 'microservice') is not None and self.trigger:
            # Process ETLTrigger for the model class
            self.microservice.login()
            if data_pk is None:
                self.microservice.execute_action(
                    "ETLTrigger", action="process_triggers", parameters={
                        "model_class": self.service_model.__name__.lower(),
                        "type": "create",
                        "pk": None,
                        "action_name": None})
            else:
                self.microservice.execute_action(
                    "ETLTrigger", action="process_triggers", parameters={
                        "model_class": self.service_model.__name__.lower(),
                        "type": "update",
                        "pk": saved_obj.pk,
                        "action_name": None})

        # Overhead, serializando e deserializando o objecto
        return Response(
            self.serializer(saved_obj, context={'request': request}).data,
            status=response_status)

    def _get_actions(self):
        """Get all actions with action decorator.

        @private
        """
        # this import works here only
        import inspect
        function_dict = dict(inspect.getmembers(
            self.service_model, predicate=inspect.isfunction))
        method_dict = dict(inspect.getmembers(
            self.service_model, predicate=inspect.ismethod))
        method_dict.update(function_dict)
        actions = {
            name: func for name, func in method_dict.items()
            if getattr(func, 'is_action', False)}
        return actions

    def list_actions(self, request) -> List[dict]:
        """List model exposed actions.

        ###### Request payload data:
        No payload.

        ###### Request query data:
        No query parameters.

        Args:
            request: Django request.

        Returns:
            Return a list of dictonary with information of the avaiable
            actions for model class. Actions info object keys:
            - **action_name [str]:** Name of the function associated with
                action on model_class.
            - **action_name__verbose [str]:** Name of the function associated
                with action on model_class translates by Pumpwood I8s.
            - **doc_string [str]:** Doc string associated with function.
            - **info [str]:** Info for que action passed as argument at action
                function decorator.
            - **info__verbose [str]:** Info for que action passed as argument
                at action function decorator model_class translates by
                Pumpwood I8s.
            - **is_static_function [bool]:** Boolean value setting if function
                is classmethod or staticmethod (True), in this cases it is not
                associated with an object and aa pk should no be passed as
                argument.
            - **parameters [dict]:** Dictionary with paramenter as key and with
                keys:
                - **default_value [any]:** Default value for paramenter.
                - **many [bool]:** If the function parameter is many (list).
                - **required [bool]:** If the parameter is necessary to run the
                    function or optinal.
                - **type [str]:** Type of the paramenter that shoul be passed
                    to function.
                - **verbose_name [str]:** Parameter name translated using
                    Pumpwood I8s.
            - **return [dict]:** A dictionary with the type associated with
                function return. Keys:
                - **many [bool]:** If the return result is a list.
                - **type [str]:** Type of the return.
        """
        actions = self._get_actions()
        action_descriptions = []
        translation_tag_template = "{model_class}__action__{action}"
        model_class = self.service_model.__name__
        for name, action in actions.items():
            action_dict = action.action_object.to_dict()
            tag = translation_tag_template.format(
                model_class=model_class,
                action=action_dict["action_name"])

            #########################################################
            # Translate action_name and info to end-user at verbose #
            action_dict["action_name__verbose"] = _.t(
                sentence=action_dict["action_name"], tag=tag + "__action_name")
            action_dict["info__verbose"] = _.t(
                sentence=action_dict["info"], tag=tag + "__info")
            for key, item in action_dict["parameters"].items():
                item["verbose_name"] = _.t(
                    sentence=key, tag=tag + "__parameters")
            #########################################################
            action_descriptions.append(action_dict)

        return Response(action_descriptions)

    def execute_action(self, request, action_name, pk=None) -> dict:
        """Execute action over object or class using parameters.

        ###### Request payload data:
        Payload dictionary correspont to function parameters as key->value
        elements.

        ###### Request query data:
        No query parameters.

        Args:
            request:
                Django request.
            action_name (str):
                Action name.
            pk (pk):
                Of the object that will be used to run the action. For
                staticmethods and classmethods the object should not be
                passed as argument.

        Returns:
            Return a dictonary with keys:

        Raises:
            PumpWoodActionArgsException:
                'Action [{action}] at model [{class_name}] is not
                a classmethod and not pk provided.'. Indicates that the action
                is not a classmethod and the pk was not passed as function
                argument.
            PumpWoodActionArgsException:
                'Action [{action}] at model [{class_name}] is a
                classmethod and pk provided.'. Indicates that the action is
                a classmethod, but a pk was passed as argument.
            PumpWoodObjectDoesNotExist:
                'Requested object {service_model}[{pk}] not found.'.
                Indicates that the object with [pk] was not found on
                database.
            PumpWoodActionArgsException:
                'error when unserializing function arguments: [...]'.
                Indicates that it was not possible to unserialize objects
                passed as function arguments. Pumpwood used function tips
                types to convert the arguments on correct types before
                passing them to function.
        """
        parameters = request.data
        actions = self._get_actions()
        rest_action_names = list(actions.keys())

        if action_name not in rest_action_names:
            message = (
                "There is no method {action} in rest actions "
                "for {class_name}").format(
                    action=action_name,
                    class_name=self.service_model.__name__)
            raise exceptions.PumpWoodForbidden(
                message=message, payload={"action_name": action_name})

        action = getattr(self.service_model, action_name)
        if pk is None and not action.action_object.is_static_function:
            msg_template = (
                "Action [{action}] at model [{class_name}] is not "
                "a classmethod and not pk provided.")
            message = msg_template.format(
                action=action_name,
                class_name=self.service_model.__name__)
            raise exceptions.PumpWoodActionArgsException(
                message=message, payload={"action_name": action_name})

        if pk is not None and action.action_object.is_static_function:
            msg_template = (
                "Action [{action}] at model [{class_name}] is a"
                "classmethod and pk provided.")
            message = msg_template.format(
                action=action_name,
                class_name=self.service_model.__name__)
            raise exceptions.PumpWoodActionArgsException(
                message=message, payload={"action_name": action_name})

        object_dict = None
        action = None
        if pk is not None:
            model_object = self.base_query(request=request)\
                .filter(pk=pk).first()
            if model_object is None:
                message_template = (
                    "Requested object {service_model}[{pk}] not found.")
                temp_service_model = \
                    self.service_model.__name__
                message = message_template.format(
                    service_model=temp_service_model, pk=pk)
                raise exceptions.PumpWoodObjectDoesNotExist(
                    message=message, payload={
                        "service_model": temp_service_model, "pk": pk})

            action = getattr(model_object, action_name)
            object_dict = self.serializer(
                model_object, many=False, context={'request': request}).data
        else:
            action = getattr(self.service_model, action_name)

        loaded_parameters = load_action_parameters(action, parameters, request)
        result = action(**loaded_parameters)

        if hasattr(self, 'microservice') is not None and self.trigger:
            self.microservice.login()
            self.microservice.execute_action(
                "ETLTrigger", action="process_triggers", parameters={
                    "model_class": self.service_model.__name__.lower(),
                    "type": "action", "pk": pk, "action_name": action_name})

        return Response({
            'result': result, 'action': action_name,
            'parameters': parameters, 'object': object_dict})

    @classmethod
    def cls_fields_options(cls) -> dict:
        """Return field options using serializer.

        Args:
            No args.

        Returns:
            Return information for each column to render search filters on
            frontend. Each field will have:
            - **column [str]:** Name of the column associated with the
                field (same as the key).
            - **column__verbose [str]:** Name of the collumns translated
                using Pumpwood I8s.
            - **default [str]:** Defult value for column.
            - **extra_info [str]:** Extra information for the collumns
                can be used to pass information about foreign key or
                related fields.
            - **help_text [str]:** Help text associated with the collumn.
            - **help_text__verbose [str]:** Help text associated with the
                collumn translated using Pumpwood I8s.
            - **indexed [str]:** If this column is indexed.
            - **nullable [str]:** If this column is nullable.
            - **primary_key [str]:** If this column is part of the primary
                key of the table. This is use full for tables with
                composite pk.
            - **read_only [str]:** If this column is read-only on
                end-point. The results for this value may differ from
                fill_validation due to `gui_readonly`.
            - **type [str]:** Type of the column, will return Python types.
            - **unique [str]:** If this column has an unique restriction.
            - **in [str]:** If column type is options, this key will
                indicates the accepted values for this field. This element
                is a dictonary with keys:
                - **description:** Human readble value for option.
                - **description__verbose:** Human readble value for
                    option translated by Pumpwood I8s.
                - **value:** Value of the option that will be saved on
                    database, for save end-points use this value to
                    modify the object.
        """
        fields = cls.service_model._meta.get_fields()
        dict_fields = {}
        for f in fields:
            is_relation = getattr(f, "is_relation", False)
            primary_key = getattr(f, "primary_key", False)
            if not is_relation or primary_key:
                dict_fields[f.column] = f

        model_class = cls.service_model.__name__
        translation_tag_template = "{model_class}__fields__{field}"

        # Get read-only fields from serializer
        read_only_fields = getattr(cls.serializer.Meta, "read_only_fields", [])

        # Get field serializers
        serializer_fields = cls.serializer(
            foreign_key_fields=True, related_fields=True).fields

        # Get serializers associated with FKs and related models
        microservice_fk_dict = {}
        microservice_related_dict = {}

        all_info = {}
        primary_keys = []
        for field_name, field_serializer in serializer_fields.items():
            ################################################################
            # Do not create relations between models in search description #
            is_microservice_fk = isinstance(
                field_serializer, MicroserviceForeignKeyField)
            is_local_fk = isinstance(
                field_serializer, LocalForeignKeyField)
            if is_microservice_fk or is_local_fk:
                field_key = field_serializer.get_fields_options_key()
                microservice_fk_dict[field_key] = field_serializer

            is_microservice_related = isinstance(
                field_serializer, MicroserviceRelatedField)
            is_local_related = isinstance(
                field_serializer, LocalRelatedField)
            if is_microservice_related or is_local_related:
                field_key = field_serializer.get_fields_options_key()
                microservice_related_dict[field_key] = field_serializer

            f = dict_fields.get(field_serializer.source)
            if f is None:
                continue
            ################################################################

            column_info = {}

            # Getting correspondent simple type
            column_type = f.get_internal_type()
            python_type = django_map.get(column_type)
            if python_type is None:
                msg = (
                    "Type [{column_type}] not implemented in map dictionary "
                    "django type -> python type")
                raise NotImplementedError(
                    msg.format(column_type=column_type))

            # Getting default value
            default = None
            f_default = getattr(f, 'default', None)
            if f_default != NOT_PROVIDED and f_default is not None:
                if callable(f_default):
                    default = f_default()
                else:
                    default = f_default

            primary_key = getattr(f, "primary_key", False)
            help_text = str(getattr(f, "help_text", ""))
            db_index = getattr(f, "db_index", False)
            unique = getattr(f, "unique", False)

            tag = translation_tag_template.format(
                model_class=model_class, field=f.column)
            column__verbose = _.t(
                sentence=f.column, tag=tag + "__column")
            help_text__verbose = _.t(
                sentence=help_text, tag=tag + "__help_text")
            column_info = {
                'primary_key': primary_key,
                "column": f.column,
                "column__verbose": column__verbose,
                "help_text": help_text,
                "help_text__verbose": help_text__verbose,
                "type": python_type,
                "nullable": f.null,
                "default": default,
                "indexed": db_index or primary_key,
                "unique": unique,
                "read_only": (
                    (f.column in read_only_fields) or
                    (field_name == 'id')
                ), "extra_info": {}}

            # Get choice options if available
            choices = getattr(f, "choices", None)
            if choices is not None:
                column_info["type"] = "options"
                in_list = {}
                for choice in choices:
                    description = _.t(
                        sentence=choice[1], tag=tag + "__choices")
                    in_list[choice[0]] = {
                        "description": choice[1],
                        "description__verbose": description,
                        "value": choice[0]}
                column_info["in"] = in_list

            if f.column == "id":
                column_info["default"] = "#autoincrement#"
                column_info["doc_string"] = "Auto increment primary key"

            # Set auto-increment for primary keys
            if primary_key:
                primary_keys.append(column_info["column"])

            # Adjust type if file
            file_field = cls.file_fields.get(f.column)
            if file_field is not None:
                column_info["type"] = "file"
                column_info["extra_info"] = {
                    "permited_file_types": file_field}
            all_info[f.column] = column_info

        #################################
        # Adding primary key definition #
        if len(primary_keys) == 1:
            column = "pk"
            help_text = "table primary key"
            tag = translation_tag_template.format(
                model_class=model_class, field=column)
            column__verbose = _.t(
                sentence=column, tag=tag + "__column")
            help_text__verbose = _.t(
                sentence=help_text, tag=tag + "__help_text")

            all_info["pk"] = {
                "primary_key": True,
                "column": primary_keys,
                "column__verbose": column__verbose,
                "help_text": help_text,
                "help_text__verbose": help_text__verbose,
                "type": "#autoincrement#",
                "nullable": False,
                "read_only": True,
                "default": "#autoincrement#",
                "unique": True,
                "partition": None}
        else:
            column = "pk"
            help_text = "base64 encoded json dictionary"
            tag = translation_tag_template.format(
                model_class=model_class, field=column)
            help_text__verbose = _.t(
                sentence=help_text, tag=tag + "__help_text")
            column__verbose = [
                _.t(sentence=x, tag=tag + "__column")
                for x in cls._primary_keys]

            all_info["pk"] = {
                "primary_key": True,
                "column": primary_keys,
                "column__verbose": column__verbose,
                "help_text": help_text,
                "help_text__verbose": help_text__verbose,
                "type": "str",
                "nullable": False,
                "read_only": True,
                "default": None,
                "unique": True,
                # TODO: Add partition information
                "partition": None}

        #############################################
        # Adding field description for foreign keys #
        for key, item in microservice_fk_dict.items():
            column = getattr(cls.service_model, key, None)
            if column is None:
                msg = (
                    "Foreign Key [{key}] was not found as model_class "
                    "[{model_class}] fields")
                raise exceptions.PumpWoodOtherException(
                    message=msg,
                    payload={"key": key, "model_class": model_class})

            tag = translation_tag_template.format(
                model_class=model_class, field=key)

            primary_key = getattr(column.field, "primary_key", False)
            help_text = str(getattr(column.field, "help_text", ""))
            db_index = getattr(column.field, "db_index", False)
            unique = getattr(column.field, "unique", False)
            null = getattr(column.field, "null", False)

            # Getting default value
            default = None
            f_default = getattr(f, 'default', None)
            if f_default != NOT_PROVIDED and f_default is not None:
                if callable(f_default):
                    default = f_default()
                else:
                    default = f_default

            column__verbose = _.t(
                sentence=key, tag=tag + "__column")
            help_text__verbose = _.t(
                sentence=help_text, tag=tag + "__help_text")
            column_info = {
                'primary_key': primary_key,
                "column": key,
                'column__verbose': column__verbose,
                "help_text": help_text,
                'help_text__verbose': help_text__verbose,
                "type": "foreign_key",
                "nullable": null,
                "default": default,
                "indexed": db_index or primary_key,
                "unique": unique,
                "read_only": key in read_only_fields,
                "extra_info": item.to_dict()}
            all_info[key] = column_info

        #############################################
        # Adding field description for foreign keys #
        for key, item in microservice_related_dict.items():
            tag = translation_tag_template.format(
                model_class=model_class, field=key)
            help_text = getattr(item, 'help_text', '')

            column__verbose = _.t(
                sentence=key, tag=tag + "__column")
            help_text__verbose = _.t(
                sentence=help_text, tag=tag + "__help_text")
            column_info = {
                'primary_key': False,
                "column": key,
                'column__verbose': column__verbose,
                "help_text": help_text,
                'help_text__verbose': help_text__verbose,
                "type": "related_model",
                "nullable": True,
                "default": default,
                "indexed": False,
                "unique": False,
                "read_only": False,
                "extra_info": item.to_dict()}
            all_info[key] = column_info
        return all_info

    def search_options(self, request):
        """Return options to be used in list funciton.

        THIS END-POINT IS DEPRECTED
        """
        return Response(self.cls_fields_options())

    def fill_options(self, request):
        """Return options for object update acording its partial data.

        THIS END-POINT IS DEPRECTED
        """
        return Response(self.cls_fields_options())

    def list_view_options(self, request) -> dict:
        """Return information to render list views on frontend.

        ###### Request payload data:
        No payload data.

        ###### Request query data:
        No query parameters.

        Args:
            request: Django request.

        Returns:
            Return a dictionary with keys:
            - **list_fields[List[str]]:** Return a list of default list fields
                that should be redendered on list view.
            - **field_type [dict]:** Return information for each column to
                render search filters on frontend. Each field will have:
                - **column [str]:** Name of the column associated with the
                    field (same as the key).
                - **column__verbose [str]:** Name of the collumns translated
                    using Pumpwood I8s.
                - **default [str]:** Defult value for column.
                - **extra_info [str]:** Extra information for the collumns
                    can be used to pass information about foreign key or
                    related fields.
                - **help_text [str]:** Help text associated with the collumn.
                - **help_text__verbose [str]:** Help text associated with the
                    collumn translated using Pumpwood I8s.
                - **indexed [str]:** If this column is indexed.
                - **nullable [str]:** If this column is nullable.
                - **primary_key [str]:** If this column is part of the primary
                    key of the table. This is use full for tables with
                    composite pk.
                - **read_only [str]:** If this column is read-only on
                    end-point. The results for this value may differ from
                    fill_validation due to `gui_readonly`.
                - **type [str]:** Type of the column, will return Python types.
                - **unique [str]:** If this column has an unique restriction.
                - **in [str]:** If column type is options, this key will
                    indicates the accepted values for this field. This element
                    is a dictonary with keys:
                    - **description:** Human readble value for option.
                    - **description__verbose:** Human readble value for
                        option translated by Pumpwood I8s.
                    - **value:** Value of the option that will be saved on
                        database, for save end-points use this value to
                        modify the object.
        """
        list_fields = self.get_list_fields()
        fields_options = self.cls_fields_options()
        return Response({
            "default_list_fields": list_fields,
            "field_descriptions": fields_options})

    def retrieve_view_options(self, request) -> dict:
        """Return information to correctly create retrieve view.

        Field set are set using gui_retrieve_fieldset attribute of the
        class. It is used classes to define each fieldset.

        ###### Request payload data:
        No payload data.

        ###### Request query data:
        No query parameters.

        Args:
            request: Django request.

        Returns:
            Return a dictonary with information to render retrieve
            views on front-ends. Returns a dictonary with keys:
            - **fieldset [List[dict]]:** A list of dictionaries with
                information for rendering the retrieve page on frontend.
                - **fields [List[str]]:** List of fields to be rendered at
                    fieldset.
                - **name [str]:** Name of the fieldset.
                - **name__verbose [str]:** Name of the fieldset translated
                    using Pumpwood I8s.
            - **verbose_field [str]:** String that can be used to create
                user readble string at frontend.

        Example:
            ```python
            {'fieldset': [{
                'fields': [
                    'status', 'alias', 'description', 'notes', 'dimensions',
                    'updated_by', 'updated_at'],
                'name__verbose': 'main'
                'name': 'main'},
              {
                'fields': [
                    'metabase_id', 'auto_embedding',
                    'object_model_class', 'object_pk'],
                'name__verbose': 'embedding'
                'name': 'embedding'},
              {
                'fields': [
                    'expire_in_min', 'default_theme', 'default_is_bordered',
                    'default_is_titled'],
                'name__verbose': 'config'
                'name': 'config'},
              {
                'fields': ['extra_info'],
                'name__verbose': 'extra_info'
                'name': 'extra_info'
              }],
             'verbose_field': '{pk} | {description}'}
            ```
        """
        gui_retrieve_fieldset = self.get_gui_retrieve_fieldset()
        gui_verbose_field = self.get_gui_verbose_field()

        # If gui_retrieve_fieldset is not set return all columns
        # on the main tab
        if gui_retrieve_fieldset is None:
            fields_options = self.cls_fields_options()
            all_columns = set(fields_options.keys())
            all_columns = list(all_columns - {'pk', 'model_class'})
            all_columns.sort()
            return Response({
                "verbose_field": gui_verbose_field,
                "fieldset": {None: {"fields": all_columns}}})
        else:
            return_gui_retrieve_fieldset = copy.deepcopy(gui_retrieve_fieldset)
            model_class = self.service_model.__name__
            tag_template = "{model_class}__fieldset_name__{fieldset_name}"
            for fieldset in return_gui_retrieve_fieldset:
                fieldset_name = fieldset["name"]
                tag = tag_template.format(
                    model_class=model_class, fieldset_name=fieldset_name)
                name__verbose = _.t(sentence=fieldset_name, tag=tag)
                fieldset["name__verbose"] = name__verbose
            return Response({
                "verbose_field": gui_verbose_field,
                "fieldset": return_gui_retrieve_fieldset})

    def fill_options_validation(self, request) -> dict:
        """Return fill options for retrieve/save pages.

        It will validate partial data fill return update fill options and
        raise validation errors if necessary.

        ###### Request payload data:
        Partially filled data to be validated by the backend.

        ###### Request query data:
        - **user_type[str]:**
            Must be in ['api', 'gui']. It will return the options according
            to interface user is using. When requesting using 'gui',
            self.gui_readonly field will be setted as read-only.
        - **field [str]:**
            Set to validade an specific field. If not set all
            fields will be validated. Validation must be implemented.

        Args:
            request: Django request.

        Return [dict]:
            Return an dictonary with `field_descriptions` generated by
            `cls_fields_options` and `gui_readonly` indicating the fields
            that will be set as read-only if user_type='gui'
        """
        user_type: str = request.query_params.get('user_type', 'api')
        # field: str = request.query_params.get('field', 'field')
        # partial_data: dict = request.data

        gui_readonly = self.get_gui_readonly()
        fill_options = self.cls_fields_options()

        # If it is gui interface then set gui_readonly as read-only
        # this will limit fields that are not read-only but should not
        # be edited be the user
        if user_type == 'gui':
            for key, item in fill_options.items():
                if key in gui_readonly:
                    item["read_only"] = True
        return Response({
            "field_descriptions": fill_options,
            "gui_readonly": gui_readonly})

    def aggregate(self, request) -> dict:
        """Aggregate data from model class.

        User list parameters to filter and order query and apply aggregation
        over information.

        ###### Request payload data:
        `filter_dict`, `exclude_dict` and `order_by` parameters have same
        behaviour as list end-point.
        - **filter_dict [dict] = {}:**
            Dictionary passed as `model.objects.filter(**filter_dict)`.<br>
        - **exclude_dict [dict] = {}:**
            Dictionary passed as
            `model.objects.exclude(**filter_dict)`.<br>
        - **order_by [dict] = []:**
            Dictionary passed as `model.objects.exclude(*order_by)`.<br>
        - **format [{‘dict’, ‘list’, ‘series’, ‘split’, ‘tight’, ‘records’,
            ‘index’}]:** Format paramter to convert pandas DataFrame to
            dictonary (default `records`). This dictonary will be returned by
            the function.
        """
        try:
            request_data = request.data
            format_return = request_data.pop('format', 'records')

            ###############################################################
            # Do not display deleted objects if not explicit set to display
            exclude_dict = request_data.get("exclude_dict", {})
            if hasattr(self.service_model, 'deleted'):
                exclude_dict_keys = exclude_dict.keys()
                any_delete = False
                for key in exclude_dict_keys:
                    first = key.split("__")[0]
                    if first == "deleted":
                        any_delete = True
                        break
                if not any_delete:
                    exclude_dict["deleted"] = True

            arg_dict = {
                'query_set': self.base_query(request=request)}

            # Separate order_by list to be applied after the aggregation
            order_by = request_data.pop('order_by', [])
            arg_dict.update(request_data)
            query_set = filter_by_dict(**arg_dict)
            limit = request_data.get('limit')

            # Generate aggregation results
            group_by = request_data.get('group_by', [])
            agg = request_data.get('agg', {})

            # If limit is passed to query, limit the results
            aggregate_query = None
            if limit is None:
                aggregate_query = aggregate_by_dict(
                    query_set=query_set, group_by=group_by,
                    agg=agg, order_by=order_by)
            else:
                aggregate_query = aggregate_by_dict(
                    query_set=query_set, group_by=group_by,
                    agg=agg, order_by=order_by)[:limit]

            aggregate_results = pd.DataFrame(aggregate_query)
            return Response(aggregate_results.to_dict(format_return))

        except TypeError as e:
            raise exceptions.PumpWoodQueryException(
                message=str(e))


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
