"""Module to aux fill_options end-point."""
import copy
import datetime
import pumpwood_djangoauth.i8n.translate as _
from django.db import models
from django.utils import timezone
from typing import Literal, Any
from rest_framework.fields import empty
from pumpwood_djangoviews.config import INFO_CACHE_TIMEOUT
from django.db.models.fields import NOT_PROVIDED
from pumpwood_communication.cache import default_cache
from pumpwood_djangoviews.serializers import (
    MicroserviceForeignKeyField, MicroserviceRelatedField,
    LocalForeignKeyField, LocalRelatedField)
from pumpwood_communication.type import (
    MISSING, AUTOINCREMENT, NOW, TODAY, PUMPWOOD_PK, ColumnInfo,
    ColumnExtraInfo, FileColumnExtraInfo, OptionsColumnExtraInfo,
    PumpwoodMissingType, PrimaryKeyExtraInfo)


class AuxFillOptions:
    """Help to extract information from fields on model class."""

    HASH_DICT = {
        "context": "pumpwood_djangoviews",
        "end-point": "cls_fields_options",
        "model_class": None}
    """Base of the hash dict."""

    TRANSLATION_TAG_TEMPLATE = "{model_class}__fields__{field}"
    """Translation tag for verbose fields."""

    @classmethod
    def run(cls, model_class: object, serializer,
            view_file_fields: dict = None,
            user_type: Literal['api', 'gui'] = 'api') -> dict[str, ColumnInfo]:
        """Extract the information."""
        model_class_name = cls.get_model_class_name(
            model_class=model_class)

        # Retrieve local cache if avaiable
        hash_dict = cls.get_hash_dict(
            model_class_name=model_class_name)
        cached_data = cls.fetch_cache(hash_dict=hash_dict)
        if cached_data is not None:
            return cached_data

        # Retrieve field information
        fields = cls.extract_non_relation_fields(
            model_class=model_class)

        # Retrieve serializer info
        serializer_info = cls.get_serializer_info(serializer=serializer)
        serializer_fields = serializer_info['serializer_fields']
        foreign_keys = serializer_info['foreign_keys']
        related_fields = serializer_info['related_fields']
        gui_readonly = serializer_info['gui_readonly']

        # Retrieve information from table fields
        column_data = {}
        key, column = list(fields.items())[-1]
        for key, column in fields.items():
            column_name = key
            temp_field = serializer_fields.get(column_name)
            info_dict = cls.create_field_info_dict(
                model_class_name=model_class_name,
                field_name=key,
                column=column,
                field_data=temp_field,
                view_file_fields=view_file_fields,
                foreign_keys=foreign_keys,
                gui_readonly=gui_readonly,
                user_type=user_type)
            column_data[column_name] = info_dict

        # Related models that will be returned with serialization
        for column_name, related_info in related_fields.items():
            temp_field = serializer_fields.get(column_name)
            info_dict = cls.create_related_field_info_dict(
                model_class_name=model_class_name,
                column_name=column_name,
                field_data=temp_field,
                related_info=related_info)
            column_data[column_name] = info_dict

        # Get table partitions from model class and create the definition
        # of the primary key data
        table_partitions = cls.get_table_partitions(
            model_class=model_class)
        info_dict = cls.create_pk_info_dict(
            model_class_name=model_class_name,
            column_data=column_data,
            table_partitions=table_partitions)
        column_data['pk'] = info_dict

        # Set diskcache to reduce calls
        cls.set_cache(hash_dict=hash_dict, data=column_data)
        return column_data

    @classmethod
    def extract_non_relation_fields(cls, model_class) -> dict:
        """Extract the information."""
        fields = model_class._meta.get_fields()
        dict_fields = {}
        for f in fields:
            if not f.auto_created or f.concrete:
                dict_fields[f.column] = f
        return dict_fields

    @classmethod
    def get_model_class_name(cls, model_class) -> str:
        """Return model_class name."""
        return model_class.__name__.lower()

    @classmethod
    def get_serializer_info(cls, serializer) -> dict:
        """Return information from serializer."""
        serializer_obj = serializer(
            foreign_key_fields=True, related_fields=True)
        serializer_fields = serializer_obj.fields

        non_microservice = {}
        microservice_fk = {}
        microservice_related = {}
        foreign_keys = serializer_obj.get_foreign_keys()
        related_fields = serializer_obj.get_related_fields()
        for key, field_serializer in serializer_fields.items():
            is_microservice_fk = isinstance(
                field_serializer, MicroserviceForeignKeyField)
            is_local_fk = isinstance(
                field_serializer, LocalForeignKeyField)
            is_microservice_related = isinstance(
                field_serializer, MicroserviceRelatedField)
            is_local_related = isinstance(
                field_serializer, LocalRelatedField)

            # Split the fields
            if is_microservice_fk or is_local_fk:
                microservice_fk[key] = field_serializer
            elif is_microservice_related or is_local_related:
                microservice_related[key] = field_serializer
            else:
                non_microservice[key] = field_serializer

        gui_readonly = getattr(serializer.Meta, 'gui_readonly', [])
        return {
            "serializer_fields": serializer_fields,
            "foreign_keys": foreign_keys,
            "related_fields": related_fields,
            "gui_readonly": gui_readonly
        }

    @classmethod
    def get_verbose_tag(cls, model_class_name: str, field_name: str) -> str:
        """Get verbose tag."""
        tag = cls.TRANSLATION_TAG_TEMPLATE.format(
            model_class=model_class_name,
            field=field_name)
        return tag

    @classmethod
    def get_hash_dict(cls, model_class_name: str) -> dict:
        """Get a base hash dict."""
        hash_dict = copy.deepcopy(cls.HASH_DICT)
        hash_dict['model_class'] = model_class_name
        return hash_dict

    @classmethod
    def fetch_cache(cls, hash_dict: str) -> dict[str, ColumnInfo] | None:
        """Fetch information about the fields from the local cache."""
        return default_cache.get(hash_dict=hash_dict)

    @classmethod
    def set_cache(cls, hash_dict: str, data: dict[str, ColumnInfo]) -> bool:
        """Set information about the fields at the local cache."""
        return default_cache.set(
            hash_dict=hash_dict, value=data,
            expire=INFO_CACHE_TIMEOUT)

    @classmethod
    def get_table_partitions(cls, model_class):
        """Get table partitions from mapper."""
        return getattr(model_class, 'table_partition', [])

    @classmethod
    def get_serializer_fields(cls, serializer):
        """Get serializer fields."""
        # Create serializer with FK and related to retrieve information
        serializer_obj = serializer(
            foreign_key_fields=True, related_fields=True)
        serializer_fields = serializer_obj.fields
        foreign_keys = serializer_obj.get_foreign_keys()
        related_fields = serializer_obj.get_related_fields()
        gui_readonly = serializer_obj.get_gui_readonly()
        return {
            'serializer_fields': serializer_fields,
            'foreign_keys': foreign_keys,
            'related_fields': related_fields,
            'gui_readonly': gui_readonly
        }

    @classmethod
    def get_nullable(cls, column, field_data) -> bool:
        """Get if column can be considered nullable."""
        if field_data is not None:
            return getattr(field_data, 'allow_null', False)
        return getattr(column, 'null', False)

    @classmethod
    def get_default(cls, column, field_data) -> Any | PumpwoodMissingType:
        """Get default value for the column."""
        #########################################################
        # Check if there is a default information at serializer #
        ser_field_default = MISSING
        if field_data is not None:
            # Custom attribute to help with calculated custom fields on
            # pumpwood
            pumpwood_read_only = getattr(
                field_data, 'pumpwood_read_only', False)
            ser_field_default = getattr(field_data, 'default')

            # If dump default is not vaiable
            if ser_field_default is empty:
                if pumpwood_read_only:
                    ser_field_default = getattr(
                        field_data, 'pumpwood_default', MISSING)
                else:
                    ser_field_default = MISSING

        # If a default is set on serializer level, use it
        if ser_field_default is not MISSING:
            return ser_field_default

        #########################
        # Auto increment fields #
        if column.auto_created:
            return AUTOINCREMENT

        #####################
        # Datetime/Date now #
        # For datetime types is is possible to set the defult value as
        # now using the field attribute
        is_auto = (
            getattr(column, 'auto_now_add', False) or
            getattr(column, 'auto_now', False))
        if is_auto:
            # 2. Check the class type to see if it's "Now" or "Today"
            if isinstance(column, models.DateTimeField):
                return NOW
            elif isinstance(column, models.DateField):
                return TODAY

        # Is is also possible to set defualt as a function
        is_now = column.default in [
            timezone.now, datetime.datetime.now]
        if is_now:
            return NOW

        is_today = column.default in [
            timezone.now, datetime.datetime.now]
        if is_today:
            return TODAY

        # Other cases use the value associated
        if column.has_default():
            return column.get_default()

        server_default = getattr(column, 'db_default', None)
        if server_default:
            if server_default is NOT_PROVIDED:
                return MISSING
            else:
                return getattr(server_default, 'value', str(server_default))
        return MISSING

    @classmethod
    def get_read_only(cls, column, field_data, gui_readonly,
                      user_type: str = 'api') -> bool:
        """Get read_only value for the column."""
        drf_read_only = getattr(
            field_data, 'read_only', False)
        pumpwood_read_only = getattr(
            field_data, 'pumpwood_read_only', False)
        model_read_only = not getattr(
            column, 'editable', True)
        read_only = drf_read_only or pumpwood_read_only or model_read_only

        if user_type == 'gui':
            read_only = read_only or (column.name in gui_readonly)
        return read_only

    @classmethod
    def get_type(cls, column_name, column, view_file_fields: dict,
                 foreign_keys: dict) -> str:
        """Get column type."""
        # Check for auxiliary data for more information
        temp_view_file_fields = view_file_fields or {}
        file_types = temp_view_file_fields.get(column.name)
        fk_data = foreign_keys.get(column_name)

        if getattr(column, 'choices', None):
            return "options"
        if file_types is not None:
            return "file"
        if fk_data is not None:
            return "foreign_key"

        is_str = isinstance(
            column,
            (models.CharField, models.TextField, models.SlugField))
        if is_str:
            return "str"
        is_int = isinstance(
            column,
            (models.IntegerField, models.AutoField, models.BigAutoField))
        if is_int:
            return "int"
        is_float = isinstance(
            column,
            (models.FloatField, models.DecimalField))
        if is_float:
            return "float"
        is_bool = isinstance(column, models.BooleanField)
        if is_bool:
            return "bool"
        is_date = isinstance(column, (models.DateField))
        if is_date:
            return "date"
        is_datetime = isinstance(
            column, (models.DateTimeField, models.TimeField))
        if is_datetime:
            return "datetime"
        is_dict = isinstance(column, models.JSONField)
        if is_dict:
            return "dict"

        internal_type = column.get_internal_type().lower()
        if internal_type == '':
            return 'int'
        else:
            return internal_type

    @classmethod
    def get_help_text(cls, column) -> bool:
        """Get help text."""
        if column.name == 'id':
            return AUTOINCREMENT.help_text()
        else:
            return str(getattr(column, 'help_text', ""))

    @classmethod
    def get_column_name_verbose(cls, verbose_tag, column_name) -> str:
        """Get column name verbose."""
        return _.t(sentence=column_name, tag=verbose_tag + "__column")

    @classmethod
    def get_help_text_verbose(cls, verbose_tag, help_text) -> str:
        """Get help text name verbose."""
        return _.t(sentence=help_text, tag=verbose_tag + "__help_text")

    @classmethod
    def get_column_name(cls, column) -> str:
        """Get column name verbose."""
        return column.name

    @classmethod
    def get_indexed(cls, column) -> str:
        """Get column name verbose."""
        is_indexed = getattr(column, 'db_index', False)
        return is_indexed

    @classmethod
    def get_primary_key(cls, column) -> bool:
        """Get primary key."""
        return getattr(column, 'primary_key', False)

    @classmethod
    def get_unique(cls, column) -> bool:
        """Get unique."""
        is_unique = getattr(column, 'unique', False)
        is_pk = getattr(column, 'primary_key', False)
        return is_unique or is_pk

    @classmethod
    def _build_options_data(cls, column, verbose_tag) -> dict:
        """Return the options associated with the field."""
        choices = getattr(column, 'choices', None)

        if choices:
            in_dict = {}
            for value, display_name in choices:
                key = str(value).lower()
                in_dict[key] = {
                    "value": value,
                    "description__verbose": _.t(
                        sentence=str(display_name),
                        tag=(verbose_tag + "__choice__" + key)),
                    "description": str(display_name)
                }
            return in_dict
        return MISSING

    @classmethod
    def get_in(cls, column, verbose_tag) -> bool:
        """Get unique."""
        return cls._build_options_data(column=column, verbose_tag=verbose_tag)

    @classmethod
    def get_extra_info(cls, column_name: str, type_str: str, column,
                       field_data, view_file_fields, foreign_keys,
                       verbose_tag) -> ColumnExtraInfo:
        """Get extra info for fields."""
        if type_str == 'foreign_key':
            foreign_key_field_data = foreign_keys.get(column_name)
            if foreign_key_field_data is not None:
                return foreign_key_field_data
            else:
                raise Exception("Something is not implemented correctly")

        if type_str == 'options':
            in_data = cls._build_options_data(
                column=column, verbose_tag=verbose_tag)
            return OptionsColumnExtraInfo(
                in_=in_data)

        if type_str == 'file':
            permited_file_types = view_file_fields.get(column.name)
            if permited_file_types is not None:
                return FileColumnExtraInfo(
                    permited_file_types=permited_file_types)
            else:
                raise Exception("Something is not implemented correctly")
        return {}

    @classmethod
    def get_primary_keys(cls, column_data) -> dict:
        """Get primary keys columns."""
        # Filter the columns that as marked as primary key
        return [
            key for key, item in column_data.items()
            if item['primary_key']]

    @classmethod
    def create_field_info_dict(cls, model_class_name, column, field_name: str,
                               field_data, view_file_fields, foreign_keys,
                               gui_readonly, user_type: str = 'api') -> dict:
        """Create field info dictonary."""
        column_name = field_name
        verbose_tag = cls.get_verbose_tag(
            model_class_name=model_class_name,
            field_name=field_name)

        # Extract information from column data
        nullable = cls.get_nullable(
            column=column, field_data=field_data)
        default = cls.get_default(
            column=column, field_data=field_data)
        read_only = cls.get_read_only(
            column=column, field_data=field_data,
            gui_readonly=gui_readonly, user_type=user_type)
        type_str = cls.get_type(
            column_name=column_name, column=column,
            view_file_fields=view_file_fields,
            foreign_keys=foreign_keys)
        help_text = cls.get_help_text(
            column=column)
        primary_key = cls.get_primary_key(
            column=column)
        unique = cls.get_unique(
            column=column)
        # Unique is an index in Postgres
        indexed = cls.get_indexed(
            column=column) or unique
        column_in = cls.get_in(
            column=column, verbose_tag=verbose_tag)

        # Create verbose information
        column__verbose = cls.get_column_name_verbose(
            column_name=column_name, verbose_tag=verbose_tag)
        help_text__verbose = cls.get_help_text_verbose(
            help_text=help_text, verbose_tag=verbose_tag)

        # Generate the extra-info data and create the column info
        extra_info = cls.get_extra_info(
            column_name=column_name, verbose_tag=verbose_tag,
            type_str=type_str, column=column, field_data=field_data,
            view_file_fields=view_file_fields,
            foreign_keys=foreign_keys)
        column_info = ColumnInfo(
            primary_key=primary_key, column=column_name,
            column__verbose=column__verbose, help_text=help_text,
            help_text__verbose=help_text__verbose, type_=type_str,
            nullable=nullable, read_only=read_only, unique=unique,
            extra_info=extra_info, in_=column_in, default=default,
            indexed=indexed)
        return column_info.to_dict()

    @classmethod
    def create_related_field_info_dict(cls, model_class_name, column_name,
                                       field_data, related_info) -> dict:
        """Create related field info dictonary."""
        verbose_tag = cls.get_verbose_tag(
            model_class_name=model_class_name,
            field_name=column_name)

        nullable = True
        default = MISSING
        read_only = field_data.read_only
        type_str = 'related_model'
        help_text = field_data.help_text
        column__verbose = cls.get_column_name_verbose(
            verbose_tag=verbose_tag, column_name=column_name)
        help_text__verbose = cls.get_help_text_verbose(
            verbose_tag=verbose_tag, help_text=help_text)
        primary_key = False
        unique = False
        column_in = MISSING
        extra_info = related_info
        column_info = ColumnInfo(
            primary_key=primary_key, column=column_name,
            column__verbose=column__verbose, help_text=help_text,
            help_text__verbose=help_text__verbose, type_=type_str,
            nullable=nullable, read_only=read_only, unique=unique,
            extra_info=extra_info, in_=column_in, default=default,
            indexed=False)
        return column_info.to_dict()

    @classmethod
    def create_pk_info_dict(cls, model_class_name: str,
                            table_partitions: list[str],
                            column_data: dict) -> dict:
        """Create primary key column information."""
        column_name = 'pk'
        verbose_tag = cls.get_verbose_tag(
            model_class_name=model_class_name,
            field_name=column_name)

        nullable = False
        default = MISSING
        read_only = False
        help_text = PUMPWOOD_PK.help_text()
        column__verbose = cls.get_column_name_verbose(
            column_name=column_name, verbose_tag=verbose_tag)
        help_text__verbose = cls.get_help_text_verbose(
            help_text=help_text, verbose_tag=verbose_tag)
        primary_key = False
        unique = True
        column_in = MISSING
        primary_keys = cls.get_primary_keys(
            column_data=column_data)
        type_str = PUMPWOOD_PK

        # Create columns information to be served at options
        extra_info = PrimaryKeyExtraInfo(
            columns=primary_keys,
            partition=table_partitions)
        column_info = ColumnInfo(
            primary_key=primary_key, column=column_name,
            column__verbose=column__verbose, help_text=help_text,
            help_text__verbose=help_text__verbose, type_=type_str,
            nullable=nullable, read_only=read_only, unique=unique,
            extra_info=extra_info, in_=column_in, default=default,
            indexed=True)
        return column_info.to_dict()
