"""Create views using Pumpwood pattern."""
import os
import pandas as pd
import simplejson as json
import datetime
import pumpwood_djangoauth.i8n.translate as _
import copy
from io import BytesIO
from typing import List
from django.http import HttpResponse
from rest_framework import viewsets, status
from rest_framework.response import Response
from werkzeug.utils import secure_filename
from pumpwood_communication import exceptions
from django.db.models.fields import NOT_PROVIDED
from pumpwood_djangoviews.renderer import PumpwoodJSONRenderer
from pumpwood_djangoviews.query import filter_by_dict
from pumpwood_djangoviews.action import load_action_parameters
from pumpwood_djangoviews.aux.map_django_types import django_map
from django.db.models.fields.files import FieldFile


def save_serializer_instance(serializer_instance):
    is_valid = serializer_instance.is_valid()
    if is_valid:
        return serializer_instance.save()
    else:
        raise exceptions.PumpWoodException(
            message="Error when validating fields for saving object",
            payload=serializer_instance.errors)


class PumpWoodRestService(viewsets.ViewSet):
    """Basic View-Set for pumpwood rest end-points."""

    _view_type = "simple"
    renderer_classes = [PumpwoodJSONRenderer]

    #####################
    # Route information #
    endpoint_description = None
    dimensions = {}
    icon = None
    #####################

    service_model = None
    storage_object = None
    microservice = None
    trigger = False

    # List fields
    serializer = None
    foreign_keys = {}
    file_fields = {}

    # Front-end uses 50 as limit to check if all data have been fetched,
    # if change this parameter, be sure to update front-end list component.
    list_paginate_limit = 50

    #######
    # Gui #
    list_fields = None
    gui_retrieve_fieldset: dict = None
    gui_verbose_field: str = 'pk'
    gui_readonly: List[str] = []
    #######

    ########################
    # Get class attributes #
    def get_gui_retrieve_fieldset(self):
        """Return gui_retrieve_fieldset attribute."""
        # Set pk as verbose field if none is set
        return self.gui_retrieve_fieldset

    def get_gui_verbose_field(self):
        """Return gui_verbose_field attribute."""
        return self.gui_verbose_field

    def get_gui_readonly(self):
        """Return gui_readonly attribute."""
        return self.gui_readonly

    def get_list_fields(self):
        """Return list_fields attribute."""
        return self.list_fields
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

    def list(self, request):
        """
        View function to list objects with pagination.

        Number of objects are limited by
        settings.REST_FRAMEWORK['PAGINATE_BY']. To get next page, use
        exclude_dict['pk__in': [list of the received pks]] to get more
        objects.

        Use to limit the query .query.filter_by_dict function.

        :param request.data['filter_dict']: Dictionary passed as
                                            objects.filter(**filter_dict)
        :type request.data['filter_dict']: dict
        :param request.data['exclude_dict']: Dictionary passed as
                                             objects.exclude(**exclude_dict)
        :type request.data['exclude_dict']: dict
        :param request.data['order_by']: List passed as
                                             objects.order_by(*order_by)
        :type request.data['order_by']: list
        :return: A list of objects using list_serializer
        """
        try:
            request_data = request.data
            limit = request_data.pop("limit", None)
            list_paginate_limit = limit or self.list_paginate_limit

            fields = request_data.pop("fields", None)
            default_fields = request_data.pop("default_fields", False)

            # If field is set always return the requested fields.
            if fields is not None:
                list_fields = fields
            # default_fields is True, return the ones specified by
            # self.list_fields
            elif default_fields:
                list_fields = self.list_fields
            # If default_fields not set return all object fields.
            else:
                list_fields = None

            arg_dict = {'query_set': self.service_model.objects.all()}
            arg_dict.update(request_data)
            query_set = filter_by_dict(**arg_dict)[:list_paginate_limit]

            return Response(self.serializer(
                query_set, many=True, fields=list_fields).data)
        except TypeError as e:
            raise exceptions.PumpWoodQueryException(message=str(e))

    def list_without_pag(self, request):
        """List data without pagination.

        View function to list objects. Basicaley the same of list, but without
        limitation by settings.REST_FRAMEWORK['PAGINATE_BY'].

        :param request.data['filter_dict']: Dictionary passed as
                                            objects.filter(**filter_dict)
        :type request.data['filter_dict']: dict
        :param request.data['exclude_dict']: Dictionary passed as
                                             objects.exclude(**exclude_dict)
        :type request.data['exclude_dict']: dict
        :param request.data['order_by']: List passed as
            objects.order_by(*order_by)

        :type request.data['order_by']: list
        :return: A list of objects using list_serializer

        .. note::
            Be careful with the number of the objects that will be retrieved
        """
        try:
            request_data = request.data
            fields = request_data.pop("fields", None)
            default_fields = request_data.pop("default_fields", False)

            # If field is set always return the requested fields.
            if fields is not None:
                list_fields = fields
            # default_fields is True, return the ones specified by
            # self.list_fields
            elif default_fields:
                list_fields = self.list_fields
            # If default_fields not set return all object fields.
            else:
                list_fields = None

            arg_dict = {'query_set': self.service_model.objects.all()}
            arg_dict.update(request_data)

            query_set = filter_by_dict(**arg_dict)
            return Response(self.serializer(
                query_set, many=True, fields=list_fields).data)
        except TypeError as e:
            raise exceptions.PumpWoodQueryException(
                message=str(e))

    def retrieve(self, request, pk=None):
        """
        Retrieve view, uses the retrieve_serializer to return object with pk.

        :param int pk: Object pk to be retrieve
        :return: The representation of the object passed by
                 self.retrieve_serializer
        :rtype: dict
        """
        obj = self.service_model.objects.get(pk=pk)
        return Response(self.serializer(obj, many=False).data)

    def retrieve_file(self, request, pk: int):
        """
        Read file without stream.

        Args:
            pk (int): Pk of the object to save file field.
            file_field(str): File field to receive stream file.

        Returns:
            A stream of bytes with da file.
        """
        if self.storage_object is None:
            raise exceptions.PumpWoodForbidden(
                "storage_object not set")

        file_field = request.query_params.get('file-field', None)
        if file_field not in self.file_fields.keys():
            msg = (
                "'{file_field}' must be set on file_fields "
                "dictionary.").format(file_field=file_field)
            raise exceptions.PumpWoodForbidden(msg)
        obj = self.service_model.objects.get(id=pk)

        file_path = getattr(obj, file_field)
        if isinstance(file_path, FieldFile):
            file_path = file_path.name

        if not file_path:
            raise exceptions.PumpWoodObjectDoesNotExist(
                "field [{}] is not set at object".format(file_field))
        file_data = self.storage_object.read_file(file_path)
        file_name = os.path.basename(file_path)

        response = HttpResponse(content=BytesIO(file_data["data"]))
        response['Content-Type'] = file_data["content_type"]
        response['Content-Disposition'] = \
            'attachment; filename=%s' % file_name
        return response

    def delete(self, request, pk=None):
        """
        Delete view.

        :param int pk: Object pk to be retrieve
        """
        obj = self.service_model.objects.get(pk=pk)
        return_data = self.serializer(obj, many=False).data

        obj.delete()
        return Response(return_data, status=200)

    def delete_many(self, request):
        """
        Delete many data using filter.

        :param request.data['filter_dict']: Dictionary passed as
                                            objects.filter(**filter_dict)
        :type request.data['filter_dict']: dict
        :param request.data['exclude_dict']: Dictionary passed as
                                             objects.exclude(**exclude_dict)
        :type request.data['exclude_dict']: dict
        :return: True if delete is ok
        """
        try:
            arg_dict = {'query_set': self.service_model.objects.all()}
            arg_dict.update(request.data)

            query_set = filter_by_dict(**arg_dict)
            query_set.delete()
            return Response(True, status=200)
        except TypeError as e:
            raise exceptions.PumpWoodQueryException(
                message=str(e))

    def remove_file_field(self, request, pk: int) -> bool:
        """
        Remove file field.

        Args:
            pk (int): pk of the object.
        Kwargs:
            No kwargs for this function.
        Raises:
            PumpWoodForbidden: If file_file is not in file_fields keys of the
                view.
            PumpWoodException: Propagates exceptions from storage_objects.
        """
        file_field = request.query_params.get('file_field', None)
        if file_field not in self.file_fields.keys():
            raise exceptions.PumpWoodForbidden(
                "file_field must be set on self.file_fields dictionary.")
        obj = self.service_model.objects.get(id=pk)

        file = getattr(obj, file_field)
        if file is None:
            raise exceptions.PumpWoodObjectDoesNotExist(
                "field [{}] not found at object".format(file_field))
        else:
            file_path = file.name
        setattr(obj, file_field, None)
        obj.save()

        try:
            self.storage_object.delete_file(file_path)
            return Response(True)
        except Exception as e:
            raise exceptions.PumpWoodException(str(e))

    def save(self, request):
        """
        Save and update object acording to request.data.

        Object will be updated if request.data['pk'] is not None.

        :param dict request.data: Object representation as
            self.retrieve_serializer
        :raise PumpWoodException: 'Object model class diferent from
            {service_model} : {service_model}' request.data['service_model']
                not the same as self.service_model.__name__
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
            data_to_update = self.service_model.objects.get(pk=data_pk)
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
                        if_exists='overide')
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

        if self.microservice is not None and self.trigger:
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
            self.serializer(saved_obj).data, status=response_status)

    def get_actions(self):
        """Get all actions with action decorator."""
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

    def list_actions(self, request):
        """List model exposed actions."""
        actions = self.get_actions()
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

    def list_actions_with_objects(self, request):
        """List model exposed actions acording to selected objects."""
        actions = self.get_actions()
        action_descriptions = [
            action.action_object.description
            for name, action in actions.items()]
        return Response(action_descriptions)

    def execute_action(self, request, action_name, pk=None):
        """Execute action over object or class using parameters."""
        parameters = request.data
        actions = self.get_actions()
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
            model_object = self.service_model.objects.filter(pk=pk).first()
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
                model_object, many=False, fields=self.list_fields).data
        else:
            action = getattr(self.service_model, action_name)

        loaded_parameters = load_action_parameters(action, parameters, request)
        result = action(**loaded_parameters)

        if self.microservice is not None and self.trigger:
            self.microservice.login()
            self.microservice.execute_action(
                "ETLTrigger", action="process_triggers", parameters={
                    "model_class": self.service_model.__name__.lower(),
                    "type": "action", "pk": pk, "action_name": action_name})

        return Response({
            'result': result, 'action': action_name,
            'parameters': parameters, 'object': object_dict})

    @classmethod
    def cls_fields_options(cls):
        fields = cls.service_model._meta.get_fields()
        model_class = cls.service_model.__name__
        translation_tag_template = "{model_class}__fields__{field}"

        # Get read-only fields from serializer
        read_only_fields = getattr(cls.serializer.Meta, "read_only", [])

        all_info = {}
        for f in fields:
            column_info = {}

            ################################################################
            # Do not create relations between models in search description #
            is_relation = getattr(f, "is_relation", False)
            if is_relation:
                continue
            ################################################################

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

            column = None
            if primary_key:
                column = "pk"
            else:
                column = f.column

            tag = translation_tag_template.format(
                model_class=model_class, field=column)
            column__verbose = _.t(
                sentence=column, tag=tag + "__column")
            help_text__verbose = _.t(
                sentence=help_text, tag=tag + "__help_text")
            column_info = {
                'primary_key': primary_key,
                "column": column,
                "column__verbose": column__verbose,
                "help_text": help_text,
                "help_text__verbose": help_text__verbose,
                "type": python_type,
                "nullable": f.null,
                "default": default,
                "indexed": db_index or primary_key,
                "unique": unique,
                "read_only": column in read_only_fields,
                "extra_info": {}}

            # Get choice options if avaiable
            choices = getattr(f, "choices", None)
            if choices is not None:
                column_info["type"] = "options"
                in_list = []
                for choice in choices:
                    description = _.t(
                        sentence=choice[1], tag=tag + "__choices")
                    in_list.append({
                        "value": choice[0], "description": description})
                column_info["in"] = in_list

            # Set autoincrement for primary keys
            if primary_key:
                column_info["column"] = "pk"
                column_info["default"] = "#autoincrement#"
                column_info["doc_string"] = "object primary key"

            # Ajust type if file
            file_field = cls.file_fields.get(column)
            if file_field is not None:
                column_info["type"] = "file"
                column_info["permited_file_types"] = file_field
            all_info[column] = column_info

        #############################################
        # Adding field description for foreign keys #
        for key, item in cls.foreign_keys.items():
            if not isinstance(item, dict):
                msg = (
                    "View foreign_key items must be dictonary, view "
                    "of model [{model}] not correctly configured").format(
                        model=str(cls.service_model))
                raise Exception(msg)

            column = getattr(cls.service_model, key, None)
            many = item.get("many", False)

            # Tag for i8s translation
            tag = translation_tag_template.format(
                model_class=model_class, field=column)

            ######################################
            # Description for foreign key fields #
            if not many:
                if column is None:
                    msg = (
                        "Foreign Key incorrectly configured at Pumpwood View. "
                        "[{key}] not found on [{model}]").format(
                            key=key, model=str(cls.service_model))
                    raise Exception(msg)

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
                    "extra_info": copy.deepcopy(item)}
                all_info[key] = column_info

            ##################################
            # Description for related fields #
            else:
                help_text = key
                db_index = False
                unique = False
                null = False
                read_only = False

                # If column is present on django (related fields), use column
                # definition
                if column is not None:
                    primary_key = getattr(column.field, "primary_key", False)
                    help_text = str(getattr(column.field, "help_text", ""))
                    db_index = getattr(column.field, "db_index", False)
                    unique = getattr(column.field, "unique", False)
                    null = getattr(column.field, "null", False)

                # Check if in definition of foreign_key there is any
                # information to overide columns details
                help_text = item.get("help_text", help_text)
                db_index = item.get("db_index", db_index)
                unique = item.get("unique", unique)
                null = item.get("null", null)
                read_only = item.get("read_only", read_only)

                column__verbose = _.t(
                    sentence=key, tag=tag + "__column")
                help_text__verbose = _.t(
                    sentence=help_text, tag=tag + "__help_text")
                all_info[key] = {
                    "primary_key": False,
                    "column": key,
                    "column__verbose": column__verbose,
                    "help_text": help_text,
                    "help_text__verbose": help_text__verbose,
                    "type": "related_model",
                    "nullable": False,
                    "read_only": read_only,
                    "default": None,
                    "unique": False,
                    "extra_info": copy.deepcopy(item)}
        return all_info

    def search_options(self, request):
        """
        Return options to be used in list funciton.

        :return: Dictionary with options for list parameters
        :rtype: dict

        .. note::
            Must be implemented
        """
        return Response(self.cls_fields_options())

    def fill_options(self, request):
        """
        Return options for object update acording its partial data.

        :param dict request.data: Partial object data.
        :return: A dictionary with options for diferent objects values
        :rtype: dict

        .. note::
            Must be implemented
        """
        return Response(self.cls_fields_options())

    def list_view_options(self, request) -> dict:
        """
        Return information to render list views on frontend.

        Args:
            No args.
        Kwargs:
            No Kwargs.
        Return [dict]:
            Return a dictionary with keys:
            - list_fields[List[str]]: Return a list of fields that should be
                redendered on list view.
            - field_type [dict]: Return information for each column to
                render search filters on frontend.
        """
        list_fields = self.get_list_fields()
        fields_options = self.cls_fields_options()
        return Response({
            "default_list_fields": list_fields,
            "field_descriptions": fields_options})

    def retrieve_view_options(self, request) -> dict:
        """
        Return information to correctly create retrieve view.

        Field set are set using gui_retrieve_fieldset attribute of the
        class. It is used classes to define each fieldset.

        Args:
            No Args.
        Kwargs:
            No Kwargs.
        Return [dict]:
            Return a dictonary with information to render retrieve
            views on front-ends. Keys:
             - fieldset [dict]: A dictionary with inline tabs names as
                key and fields that will be redendered.

            Exemple:
            {
                "fieldset": {
                    "Nome da tab. 1": {
                        "fields": ["field1", "field2", "field3"]
                    },
                    "Nome da tab. 2": {
                        "fields": ["field1"]
                    }
                }
            }
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
            return {
                "verbose_field": gui_verbose_field,
                "fieldset": {
                    None: {
                        "fields": all_columns
                    }
                }
            }
        return Response({
            "verbose_field": gui_verbose_field,
            "fieldset": gui_retrieve_fieldset})

    def fill_options_validation(self, request) -> dict:
        """
        Return fill options for retrieve/save pages.

        It will validate partial data fill and return erros if necessary.

        Args:
            partial_data [dict]: Partially filled data to be validated by
                the backend.

        Kwargs:
            user_type[str]: Must be in ['api', 'gui']. It will return the
                options according to interface user is using. When requesting
                using gui, self.gui_readonly field will be setted as read-only.
            field [str]: Set to validade an specific field. If not set all
                fields will be validated.
        Return [dict]:
            Return a dictionary
        """
        user_type: str = request.query_params.get('user_type', 'api')
        field: str = request.query_params.get('field', 'field')
        partial_data = request.data

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


class PumpWoodDataBaseRestService(PumpWoodRestService):
    """This view extends PumpWoodRestService, including pivot function."""

    _view_type = "data"

    model_variables = []
    """Specify which model variables will be returned in pivot. Line index are
       the model_variables - columns (function pivot parameter) itens."""
    expected_cols_bulk_save = []
    """Set the collumns needed at bulk_save."""

    def pivot(self, request):
        """
        Pivot QuerySet data acording to columns selected, and filters passed.

        :param request.data['filter_dict']: Dictionary passed as
            objects.filter(**filter_dict)
        :type request.data['filter_dict']: dict
        :param request.data['exclude_dict']: Dictionary passed as
            objects.exclude(**exclude_dict)
        :type request.data['exclude_dict']: dict
        :param request.data['order_by']: List passed as
            objects.order_by(*order_by)
        :type request.data['order_by']: list
        :param request.data['columns']: Variables to be used as pivot collumns
        :type request.data['columns']: list
        :param request.data['format']: Format used in
            pandas.DataFrame().to_dict()
        :type request.data['columns']: str

        :return: Return database data pivoted acording to columns parameter
        :rtyoe: panas.Dataframe converted to disctionary
        """
        if self.model_variables is None:
            msg = "Pivot is not avaiable, set model_variables at view"
            raise exceptions.PumpWoodException(msg)

        columns = request.data.get('columns', [])
        format = request.data.get('format', 'list')
        model_variables = request.data.get('variables')
        show_deleted = request.data.get('show_deleted', False)
        model_variables = model_variables or self.model_variables

        if type(columns) != list:
            raise exceptions.PumpWoodException(
                'Columns must be a list of elements.')
        if len(set(columns) - set(model_variables)) != 0:
            raise exceptions.PumpWoodException(
                'Column chosen as pivot is not at model variables')

        index = list(set(model_variables) - set(columns))
        filter_dict = request.data.get('filter_dict', {})
        exclude_dict = request.data.get('exclude_dict', {})
        order_by = request.data.get('order_by', {})

        if hasattr(self.service_model, 'deleted'):
            if not show_deleted:
                filter_dict["deleted"] = False

        arg_dict = {'query_set': self.service_model.objects.all(),
                    'filter_dict': filter_dict,
                    'exclude_dict': exclude_dict,
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
                raise exceptions.PumpWoodException(
                    "'value' column not at melted data, it is not possible"
                    " to pivot dataframe.")

            pivoted_table = pd.pivot_table(
                melted_data, values='value', index=index,
                columns=columns, aggfunc=lambda x: tuple(x)[0])

            return Response(
                pivoted_table.reset_index().to_dict(format))

    def bulk_save(self, request):
        """
        Bulk save data.

        Args:
            data_to_save(list): List of dictionaries which must have
                                self.expected_cols_bulk_save.
        Return:
            dict: ['saved_count']: total of saved objects.
        """
        data_to_save = request.data
        if data_to_save is None:
            raise exceptions.PumpWoodException(
                'Post payload must have data_to_save key.')

        if len(self.expected_cols_bulk_save) == 0:
            msg = (
                "Bulk save not avaiable. Set expected_cols_bulk_save on "
                "PumpWoodDataBaseRestService View to habilitate funciton.")
            raise exceptions.PumpWoodException(msg)

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
            template = 'Expected columns and data columns do not match:' + \
                '\nExpected columns:{expected}' + \
                '\nData columns:{data_cols}'
            raise exceptions.PumpWoodException(template.format(
                expected=set(self.expected_cols_bulk_save),
                data_cols=pd_data_cols,))
