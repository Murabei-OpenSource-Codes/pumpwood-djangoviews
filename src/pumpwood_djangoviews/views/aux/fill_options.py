"""Auxiliary logic for the fill_options end-point.

Extracts model and serializer metadata for frontend forms and search
filters. Field defaults are mapped to pumpwood-communication sentinel
objects and serialized as stable JSON markers (for example ``**now**``
for ``DateTimeField`` columns with ``auto_now`` or ``auto_now_add``).

Typical usage is through ``PumpWoodRestService.cls_fields_options`` or
the ``fill_options`` action, both delegating to ``AuxFillOptions.run``.
"""
import copy
import datetime
from dataclasses import dataclass
from typing import Literal, Any
from django.db import models
from django.utils import timezone
from rest_framework.fields import empty
from django.db.models.fields import NOT_PROVIDED

# Pumpwood imports
from pumpwood_i8n.singletons import pumpwood_i8n
from pumpwood_communication.cache import default_cache
from pumpwood_communication.type import (
    MISSING, AUTOINCREMENT, NOW, TODAY, PUMPWOOD_PK, ColumnInfo,
    ColumnExtraInfo, FileColumnExtraInfo, OptionsColumnExtraInfo,
    PumpwoodMissingType, PrimaryKeyExtraInfo, PumpwoodSentinel,
    PumpwoodDataclassMixin)
from pumpwood_djangoviews.config import INFO_CACHE_EXPIRATION
from pumpwood_djangoviews.serializers import (
    MicroserviceForeignKeyField, MicroserviceRelatedField,
    LocalForeignKeyField, LocalRelatedField)



@dataclass
class PumpwoodDjangoViewsFillOptionsCacheKey(PumpwoodDataclassMixin):
    """Cache key fields for fill_options responses."""

    model_class_name: str
    """Lowercase name of the service model class."""
    user_type: Literal['api', 'gui']
    """Audience that requested the metadata."""
    context: str = "pumpwood_djangoviews__fill_options"
    """Disk cache namespace for fill_options payloads."""


class AuxFillOptions:
    """Build fill_options metadata from a model and its serializer.

    Produces one ``ColumnInfo`` entry per column, including type,
    nullability, read-only flags, choices, foreign-key extra data,
    and defaults resolved to ``pumpwood_communication`` sentinels when
    the Django field uses auto timestamps, auto increment, or has no
    default value.
    """

    HASH_DICT = {
        "context": "pumpwood_djangoviews",
        "end-point": "cls_fields_options",
        "model_class": None}
    """Base hash dict template for legacy fill_options cache keys."""

    TRANSLATION_TAG_TEMPLATE = "{model_class}__fields__{field}"
    """Format string for i8n tags on column metadata."""

    @classmethod
    def run(cls, model_class: object, serializer,
            view_file_fields: dict = None,
            user_type: Literal['api', 'gui'] = 'api'
            ) -> dict[str, ColumnInfo]:
        """Build the fill_options payload for a service model.

        Results are cached under a model-specific hash to reduce repeated
        serializer introspection. Each column is converted with
        ``ColumnInfo.to_dict()``, which replaces sentinel objects with
        their JSON marker strings.

        Args:
            model_class (object):
                Django model class exposed by the view service.
            serializer (type):
                ``DynamicFieldsModelSerializer`` subclass for the model.
            view_file_fields (dict | None):
                Allowed upload types keyed by model field name.
            user_type (Literal['api', 'gui']):
                When ``gui``, ``Meta.gui_readonly`` marks fields read-only.

        Returns:
            dict[str, ColumnInfo]:
                Column metadata keyed by field name, including ``pk``.
        """
        model_class_name = cls.get_model_class_name(
            model_class=model_class)
        hash_dict = PumpwoodDjangoViewsFillOptionsCacheKey(
            model_class_name=model_class_name,
            user_type=user_type)

        # Retrieve local cache if avaiable
        cached_data = default_cache.get(hash_dict=hash_dict)
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
        default_cache.set(
            hash_dict=hash_dict, value=column_data,
            expire=INFO_CACHE_EXPIRATION)
        return column_data

    @classmethod
    def extract_non_relation_fields(cls, model_class) -> dict:
        """Return concrete model fields keyed by database column name.

        Args:
            model_class (type):
                Django model class exposed by the view service.

        Returns:
            dict:
                Mapping of column name to ``Field`` instances.
        """
        fields = model_class._meta.get_fields()
        dict_fields = {}
        for f in fields:
            if not f.auto_created or f.concrete:
                dict_fields[f.column] = f
        return dict_fields

    @classmethod
    def get_model_class_name(cls, model_class) -> str:
        """Return the lowercase model class name used in cache keys.

        Args:
            model_class (type):
                Django model class exposed by the view service.

        Returns:
            str:
                Lowercase ``__name__`` of the model class.
        """
        return model_class.__name__.lower()

    @classmethod
    def get_serializer_info(cls, serializer) -> dict:
        """Inspect serializer fields and relation metadata.

        Args:
            serializer (type):
                ``DynamicFieldsModelSerializer`` subclass for the model.

        Returns:
            dict:
                Keys are ``serializer_fields``, ``foreign_keys``,
                ``related_fields``, and ``gui_readonly``.
        """
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
        """Build the i8n tag prefix for a model field.

        Args:
            model_class_name (str):
                Lowercase model class name.
            field_name (str):
                Model or serializer field name.

        Returns:
            str:
                Tag used by ``pumpwood_i8n`` for verbose labels.
        """
        tag = cls.TRANSLATION_TAG_TEMPLATE.format(
            model_class=model_class_name,
            field=field_name)
        return tag

    @classmethod
    def get_hash_dict(cls, model_class_name: str) -> dict:
        """Return a copy of ``HASH_DICT`` bound to a model class.

        Args:
            model_class_name (str):
                Lowercase model class name.

        Returns:
            dict:
                Hash dict with ``model_class`` set for cache lookup.
        """
        hash_dict = copy.deepcopy(cls.HASH_DICT)
        hash_dict['model_class'] = model_class_name
        return hash_dict

    @classmethod
    def fetch_cache(cls, hash_dict: dict) -> dict[str, ColumnInfo] | None:
        """Read fill_options payload from the local disk cache.

        Args:
            hash_dict (dict):
                Cache hash dict produced by ``get_hash_dict``.

        Returns:
            dict[str, ColumnInfo] | None:
                Cached column metadata, or ``None`` on cache miss.
        """
        return default_cache.get(hash_dict=hash_dict)

    @classmethod
    def set_cache(cls, hash_dict: dict,
                  data: dict[str, ColumnInfo]) -> bool:
        """Store fill_options payload in the local disk cache.

        Args:
            hash_dict (dict):
                Cache hash dict produced by ``get_hash_dict``.
            data (dict[str, ColumnInfo]):
                Column metadata keyed by field name.

        Returns:
            bool:
                ``True`` when the value was stored successfully.
        """
        return default_cache.set(
            hash_dict=hash_dict, value=data,
            expire=INFO_CACHE_EXPIRATION)

    @classmethod
    def get_table_partitions(cls, model_class):
        """Return partition column names declared on the model.

        Args:
            model_class (type):
                Django model class exposed by the view service.

        Returns:
            list:
                Value of ``table_partition`` when set, else ``[]``.
        """
        return getattr(model_class, 'table_partition', [])

    @classmethod
    def get_serializer_fields(cls, serializer):
        """Return serializer fields and relation maps.

        Args:
            serializer (type):
                ``DynamicFieldsModelSerializer`` subclass for the model.

        Returns:
            dict:
                Keys are ``serializer_fields``, ``foreign_keys``,
                ``related_fields``, and ``gui_readonly``.
        """
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
        """Return whether the column accepts null values.

        Serializer ``allow_null`` takes precedence over the model field.

        Args:
            column (Field):
                Django model field instance.
            field_data (Field | None):
                Matching DRF serializer field, if present.

        Returns:
            bool:
                ``True`` when null values are allowed.
        """
        if field_data is not None:
            return getattr(field_data, 'allow_null', False)
        return getattr(column, 'null', False)

    @classmethod
    def _unwrap_default(cls, default):
        """Unwrap nested DRF default wrapper objects.

        Args:
            default (Any):
                Default value from serializer or model field.

        Returns:
            Any:
                Inner default after unwrapping known DRF containers.
        """
        if default is empty or default is MISSING:
            return default
        seen = set()
        while True:
            marker = id(default)
            if marker in seen:
                break
            seen.add(marker)
            inner = getattr(default, 'default', empty)
            if inner is empty or inner is default:
                break
            if not hasattr(default, 'default'):
                break
            default = inner
        return default

    @classmethod
    def _resolve_datetime_sentinel(cls, column):
        """Return NOW or TODAY for auto_now model fields.

        Args:
            column (models.Field):
                Django model field.

        Returns:
            PumpwoodSentinel | None:
                Sentinel when field uses auto timestamp semantics.
        """
        is_auto = (
            getattr(column, 'auto_now_add', False) or
            getattr(column, 'auto_now', False))
        if not is_auto:
            return None
        if isinstance(column, models.DateTimeField):
            return NOW
        if isinstance(column, models.DateField):
            return TODAY
        return None

    @classmethod
    def _normalize_now_today_callable(cls, default, column=None):
        """Map now/today callables to pumpwood sentinels.

        Args:
            default (callable):
                Callable default from serializer or model field.
            column (Field):
                Django model field associated with the default.

        Returns:
            PumpwoodSentinel | None:
                Sentinel when default represents now or today.
        """
        if default in (timezone.now, datetime.datetime.now):
            if isinstance(column, models.DateField):
                if not isinstance(column, models.DateTimeField):
                    return TODAY
            return NOW
        if default is datetime.date.today:
            return TODAY
        name = getattr(default, '__name__', None)
        if name == 'now':
            if isinstance(column, models.DateField):
                if not isinstance(column, models.DateTimeField):
                    return TODAY
            return NOW
        if name == 'today':
            return TODAY
        return None

    @classmethod
    def _normalize_callable_default(cls, default, column=None):
        """Convert callable defaults to JSON-safe sentinel values.

        Args:
            default (callable):
                Callable default from serializer or model field.
            column (Field):
                Django model field associated with the default.

        Returns:
            PumpwoodSentinel | Any:
                Sentinel value or evaluated default.
        """
        default = cls._unwrap_default(default)
        if isinstance(default, PumpwoodSentinel):
            return default
        if not callable(default):
            return default

        sentinel = cls._normalize_now_today_callable(
            default, column=column)
        if sentinel is not None:
            return sentinel

        name = getattr(default, '__name__', None)
        try:
            return default()
        except TypeError:
            return name or repr(default)

    @classmethod
    def get_default(cls, column, field_data) -> Any | PumpwoodMissingType:
        """Resolve the default value for a model column.

        Django auto fields and timestamp defaults are returned as
        pumpwood sentinels (``NOW``, ``TODAY``, ``AUTOINCREMENT``,
        ``MISSING``) so ``ColumnInfo.to_dict()`` emits stable JSON
        markers such as ``**now**``.

        Resolution order:
        1. ``AUTOINCREMENT`` for auto-created primary key columns.
        2. ``NOW`` or ``TODAY`` when ``auto_now`` or ``auto_now_add``
           is set on the model field, before serializer defaults.
        3. Serializer ``default`` or ``pumpwood_default`` when set.
        4. Callable or static ``default`` on the model field.
        5. ``db_default`` when present, otherwise ``MISSING``.

        Args:
            column (Field):
                Django model field instance.
            field_data (Field | None):
                Matching DRF serializer field, if present.

        Returns:
            PumpwoodSentinel | Any:
                Sentinel object or concrete default value.
        """
        #########################################################
        # Check if there is a default information at serializer #
        ser_field_default = MISSING
        if field_data is not None:
            # Custom attribute to help with calculated custom fields on
            # pumpwood
            pumpwood_read_only = getattr(
                field_data, 'pumpwood_read_only', False)
            ser_field_default = cls._unwrap_default(
                getattr(field_data, 'default'))

            # If dump default is not vaiable
            if ser_field_default is empty:
                if pumpwood_read_only:
                    ser_field_default = getattr(
                        field_data, 'pumpwood_default', MISSING)
                else:
                    ser_field_default = MISSING

        #########################
        # Auto increment fields #
        if column.auto_created:
            return AUTOINCREMENT

        #####################
        # Datetime/Date now #
        # Model auto_now flags take precedence over serializer defaults.
        auto_sentinel = cls._resolve_datetime_sentinel(column=column)
        if auto_sentinel is not None:
            return auto_sentinel

        # If a default is set on serializer level, use it
        if ser_field_default is not MISSING:
            if callable(ser_field_default) and ser_field_default is not empty:
                return cls._normalize_callable_default(
                    ser_field_default, column=column)
            return ser_field_default

        # It is also possible to set default as a function
        if column.has_default() and callable(column.default):
            return cls._normalize_callable_default(
                column.default, column=column)

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
        """Return whether the column is read-only for the client.

        Args:
            column (Field):
                Django model field instance.
            field_data (Field | None):
                Matching DRF serializer field, if present.
            gui_readonly (list[str]):
                Field names marked read-only for GUI clients.
            user_type (str):
                ``gui`` also applies ``gui_readonly`` restrictions.

        Returns:
            bool:
                ``True`` when the field must not be edited.
        """
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
        """Map a model column to the Pumpwood fill_options type string.

        Args:
            column_name (str):
                Model field name.
            column (Field):
                Django model field instance.
            view_file_fields (dict):
                Allowed upload MIME types keyed by field name.
            foreign_keys (dict):
                Foreign-key metadata from the serializer.

        Returns:
            str:
                Pumpwood type such as ``str``, ``foreign_key``, or
                ``options``.
        """
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
    def get_help_text(cls, column) -> str:
        """Return help text for a model column.

        Args:
            column (Field):
                Django model field instance.

        Returns:
            str:
                Field help text, or the auto-increment help text for
                ``id``.
        """
        if column.name == 'id':
            return AUTOINCREMENT.help_text()
        else:
            return str(getattr(column, 'help_text', ""))

    @classmethod
    def get_column_name_verbose(cls, verbose_tag: str,
                                column_name: str) -> str:
        """Return translated column label for the frontend.

        Args:
            verbose_tag (str):
                i8n tag prefix for the field.
            column_name (str):
                Raw column name used as translation sentence.

        Returns:
            str:
                Translated column label.
        """
        sentence = column_name
        tag = verbose_tag + "__column"
        return pumpwood_i8n.t(sentence=sentence, tag=tag)

    @classmethod
    def get_help_text_verbose(cls, verbose_tag, help_text) -> str:
        """Return translated help text for the frontend.

        Args:
            verbose_tag (str):
                i8n tag prefix for the field.
            help_text (str):
                Raw help text used as translation sentence.

        Returns:
            str:
                Translated help text.
        """
        sentence = help_text
        tag = verbose_tag + "__help_text"
        return pumpwood_i8n.t(sentence=sentence, tag=tag)

    @classmethod
    def get_column_name(cls, column) -> str:
        """Return the database column name.

        Args:
            column (Field):
                Django model field instance.

        Returns:
            str:
                ``column.name`` value.
        """
        return column.name

    @classmethod
    def get_indexed(cls, column) -> bool:
        """Return whether the column has a database index.

        Args:
            column (Field):
                Django model field instance.

        Returns:
            bool:
                Value of ``db_index`` when present.
        """
        is_indexed = getattr(column, 'db_index', False)
        return is_indexed

    @classmethod
    def get_primary_key(cls, column) -> bool:
        """Return whether the column is a primary key.

        Args:
            column (Field):
                Django model field instance.

        Returns:
            bool:
                ``True`` when ``primary_key`` is set on the field.
        """
        return getattr(column, 'primary_key', False)

    @classmethod
    def get_unique(cls, column) -> bool:
        """Return whether the column is unique.

        Primary key columns are treated as unique.

        Args:
            column (Field):
                Django model field instance.

        Returns:
            bool:
                ``True`` when the field is unique or a primary key.
        """
        is_unique = getattr(column, 'unique', False)
        is_pk = getattr(column, 'primary_key', False)
        return is_unique or is_pk

    @classmethod
    def _build_options_data(cls, column, verbose_tag) -> dict:
        """Build choice metadata for options-type columns.

        Args:
            column (Field):
                Django model field with ``choices`` defined.
            verbose_tag (str):
                i8n tag prefix for the field.

        Returns:
            dict | PumpwoodMissingType:
                Choice map keyed by lowercase value, or ``MISSING``
                when the field has no choices.
        """
        choices = getattr(column, 'choices', None)
        if choices:
            in_dict = {}
            for value, display_name in choices:
                key = str(value).lower()
                description = str(display_name)
                tag = verbose_tag + "__choice__" + key
                description__verbose = pumpwood_i8n.t(
                    sentence=description, tag=tag)
                in_dict[key] = {
                    "value": value,
                    "description__verbose": description__verbose,
                    "description": description}
            return in_dict
        return MISSING

    @classmethod
    def get_in(cls, column, verbose_tag) -> dict:
        """Return serialized choices for an options-type column.

        Args:
            column (Field):
                Django model field instance.
            verbose_tag (str):
                i8n tag prefix for the field.

        Returns:
            dict | PumpwoodMissingType:
                Choice metadata from ``_build_options_data``.
        """
        return cls._build_options_data(
            column=column, verbose_tag=verbose_tag)

    @classmethod
    def get_extra_info(cls, column_name: str, type_str: str, column,
                       field_data, view_file_fields, foreign_keys,
                       verbose_tag) -> ColumnExtraInfo:
        """Build type-specific extra metadata for a column.

        Args:
            column_name (str):
                Model field name.
            type_str (str):
                Pumpwood fill_options type string.
            column (Field):
                Django model field instance.
            field_data (Field | None):
                Matching DRF serializer field, if present.
            view_file_fields (dict):
                Allowed upload MIME types keyed by field name.
            foreign_keys (dict):
                Foreign-key metadata from the serializer.
            verbose_tag (str):
                i8n tag prefix for the field.

        Returns:
            ColumnExtraInfo:
                Foreign-key, options, file, or empty extra info.

        Raises:
            Exception:
                When foreign-key or file metadata is missing for the
                declared column type.
        """
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
    def get_primary_keys(cls, column_data) -> list[str]:
        """Return names of columns marked as primary keys.

        Args:
            column_data (dict):
                Serialized column metadata keyed by field name.

        Returns:
            list[str]:
                Field names whose metadata has ``primary_key`` set.
        """
        # Filter the columns that as marked as primary key
        return [
            key for key, item in column_data.items()
            if item['primary_key']]

    @classmethod
    def create_field_info_dict(cls, model_class_name, column, field_name: str,
                               field_data, view_file_fields, foreign_keys,
                               gui_readonly, user_type: str = 'api'
                               ) -> dict:
        """Build serialized ``ColumnInfo`` for one model field.

        Args:
            model_class_name (str):
                Lowercase model class name.
            column (Field):
                Django model field instance.
            field_name (str):
                Model field name.
            field_data (Field | None):
                Matching DRF serializer field, if present.
            view_file_fields (dict):
                Allowed upload MIME types keyed by field name.
            foreign_keys (dict):
                Foreign-key metadata from the serializer.
            gui_readonly (list[str]):
                Field names marked read-only for GUI clients.
            user_type (str):
                ``gui`` also applies ``gui_readonly`` restrictions.

        Returns:
            dict:
                Serialized ``ColumnInfo`` payload for the field.
        """
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
        """Build serialized ``ColumnInfo`` for a related-model field.

        Args:
            model_class_name (str):
                Lowercase model class name.
            column_name (str):
                Related serializer field name.
            field_data (Field):
                DRF serializer field for the relation.
            related_info (dict):
                Related-model metadata from the serializer.

        Returns:
            dict:
                Serialized ``ColumnInfo`` payload with type
                ``related_model``.
        """
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
        """Build serialized ``ColumnInfo`` for the synthetic ``pk`` field.

        Args:
            model_class_name (str):
                Lowercase model class name.
            table_partitions (list[str]):
                Partition column names from the model.
            column_data (dict):
                Serialized metadata for non-related model fields.

        Returns:
            dict:
                Serialized ``ColumnInfo`` payload for ``pk``.
        """
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
