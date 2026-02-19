"""Local field (Forening Key and Related) implementation."""
from .aux import _import_function_by_string
from rest_framework import serializers
from pumpwood_communication.cache import default_cache
from pumpwood_communication.type import (
    ForeignKeyColumnExtraInfo, RelatedColumnExtraInfo)


class LocalForeignKeyField(serializers.Field):
    """Serializer field for ForeignKey using database connection.

    This serializer will fetch object data from a database using a
    connection and converting to object using serializer.

    Serializer can be passed as python object or using a string to the path
    that will be lazy loaded when first fetch.

    ```python
    class SerializerPumpwoodMFAMethod(DynamicFieldsModelSerializer):
        pk = serializers.IntegerField(source='id', allow_null=True)
        model_class = ClassNameField()

        # ForeignKey
        user_id = serializers.IntegerField(allow_null=False, required=True)
        user = LocalForeignKeyField(
            serializer=(
                "pumpwood_djangoauth.registration." +
                "serializers.SerializerUser")
            display_field="username",
            fields=["pk", "username"])
    ```
    """

    serializer_cache: serializers.ModelSerializer
    """Serializer can be lazy loaded passing the path to avoid circular import,
       serializer_cache will cache serializer to remove necessity of importing
       the serializer at every request."""
    serializer: str | serializers.ModelSerializer
    """Serializer or string to serializer path that will be lazy loaded."""
    display_field: str
    """Display field that will be set to `__display_field__` key at the
       object."""
    fields: list[str]
    """Limit the return fields to fields set, if not set will return list
       default fields."""

    def __init__(self, serializer: str | serializers.ModelSerializer,
                 display_field: str = None, fields: list[str] = None,
                 request=None, **kwargs):
        """__init__.

        Args:
            serializer (Union[str, serializers.ModelSerializer]):
                Serializer can be lazy loaded passing the path to avoid
                circular import, serializer_cache will cache serializer to
                remove necessity of importing the serializer at every request.
            display_field (str):
                Display field that will be set to `__display_field__` key at
                the object.
            fields (list[str]):
                Limit the return fields to fields set, if not set will return
                list default fields.
            request:
                Django request to be passed as arguments for recursive
                serialization of related fields.
            **kwargs (dict):
                Other serializer arguments.
        """
        # Avoid circular imports for related models and cache lazzy loaded
        # serializers
        self.serializer_cache = None
        self.serializer = serializer
        self.display_field = display_field
        self.fields = fields
        kwargs['read_only'] = True
        super(LocalForeignKeyField, self).__init__(**kwargs)

    def get_fields_options_key(self):
        """Return key that will be used on fill options return.

        @private
        """
        model = self.parent.Meta.model
        parent_field = getattr(model, self.source)
        return parent_field.field.column

    def to_representation(self, value) -> dict:
        """Overwrite default representation to return serialized data."""
        # Get request to cache results
        if self.serializer_cache is None:
            if type(self.serializer) is str:
                self.serializer_cache = _import_function_by_string(
                    self.serializer)
            else:
                self.serializer_cache = self.serializer

        # Return an empty object if object pk is None
        model = self.parent.Meta.model
        parent_field = getattr(model, self.source)
        model_class = parent_field.field.related_model.__name__
        if value is None:
            return {"model_class": model_class}

        # Get data from cache from request if avaiable
        request = self.parent.context.get('request')
        hash_dict = {
            'context': 'pumpwood_djangoviews-local_pk_field',
            'user_id': request.user.id,
            'model_class': model_class,
            'object_pk': value.id,
            'fields': self.fields}
        cache_response = default_cache.get(hash_dict=hash_dict)
        # Return the cached data if avaliable
        if cache_response is not None:
            return cache_response

        # Retrieve data from the database
        object_data = self.serializer_cache(
            value, many=False, fields=self.fields,
            default_fields=True, context={'request': request}).data
        display_field = object_data.get(self.display_field, None)
        object_data['__display_field__'] = display_field

        # Set the cache for futher serializations on the request
        default_cache.set(hash_dict=hash_dict, value=object_data)
        return object_data

    def get_source_pk_fields(self) -> list[str]:
        """Return a list of source fields associated with FK.

        If will return the source pk and the complementary_source
        keys.

        Args:
            No Args.

        Returns:
            Return a list of the fields that are considered when retrieving
            a foreign key.
        """
        # Treat when complementary_source is not set
        model = self.parent.Meta.model
        source_id = model._meta.get_field(self.source).attname
        return [source_id]

    def to_dict(self) -> dict:
        """Return a dict with values to be used on options end-point.

        Returns:
            model_class [str]:
                Model class associated with foreign key.
            many [bool]:
                Return always False, only one object will be returned.
            display_field [str]:
                Object display_field will be returned as __display_field__
                key.
            object_field [str]:
                Will return the field associated with this serializer.
            fields [list[str]]:
                If not None will restrict the fields returned at object.
        """
        model = self.parent.Meta.model
        parent_field = getattr(model, self.source)
        source_keys = self.get_source_pk_fields()
        model_class_name = parent_field.field.related_model.__name__
        return ForeignKeyColumnExtraInfo(
            model_class=model_class_name,
            display_field=self.display_field,
            object_field=self.field_name,
            source_keys=source_keys)


class LocalRelatedField(serializers.Field):
    """Serializer field for related objects using microservice.

    This serializer will fetch a list of objectsfrom a microservice using a
    microservice object at `list_without_pag` end-point. It will use
    serilializing object id to query for related object at destiny model
    class `foreign_key`.

    This field makes a call to the loadbalancer, caution when microservice
    calls the same microservice of origin or serialization might result on
    circular fetching.

    MicroserviceRelatedField are always set as `required=False` and
    `read_only=True`.

    Example of usage:
    ```python
    class UserSerializer(DynamicFieldsModelSerializer):
        pk = serializers.IntegerField(
            source='id', allow_null=True, required=False)
        model_class = ClassNameField()

        # Foreign Key
        # Will return the object data associated with updated_by_id at
        # updated_by key at the serialized object.
        api_permission_set = LocalRelatedField(
            serializer=(
                "pumpwood_djangoauth.api_permission."
                "serializers.SerializerPumpwoodPermissionPolicyUserM2M"),
            order_by=["-id"])
    """

    def __init__(self, serializer, order_by: list[str] = ["-id"],
                 fields: list[str] = None, **kwargs):
        """__init__.

        Args:
            serializer:
                Serializer class or string to path of the serializer class.
            order_by (list[str]): = ["-id"]
                Order by list to order the results of the related objects.
            fields (list[str]): = None
                Retrict or enforce de fields that will be retuned by the
                serializer. If None, only list fields will be returned.
            **kwargs (dict):
                Other arguments that will be passed to serializer.
        """
        if type(order_by) is not list:
            msg = ('order_by must be a list of strings. order_by={order_by}')\
                .format(order_by=order_by)
            raise AttributeError(msg)

        # Avoid circular imports for related models and cache lazzy loaded
        # serializers
        self.serializer_cache = None
        self.serializer = serializer
        self.order_by = order_by
        self.fields = fields

        # Force field not be necessary for saving object
        kwargs["required"] = False
        kwargs['read_only'] = True
        super(LocalRelatedField, self).__init__(**kwargs)

    def get_fields_options_key(self):
        """Return key that will be used on fill options return.

        @private
        """
        return self.source

    def to_representation(self, value):
        """Return all related data serialized.

        @private
        """
        if self.serializer_cache is None:
            if type(self.serializer) is str:
                self.serializer_cache = _import_function_by_string(
                    self.serializer)
            else:
                self.serializer_cache = self.serializer

        request = self.parent.context.get('request')
        return self.serializer_cache(
            value.order_by(*self.order_by).all(),
            many=True, default_fields=True, fields=self.fields,
            context={'request': request}).data

    def to_dict(self):
        """Return a dict with values to be used on options end-point.

        Returns:
            Return a dictonary with serialization of field information.
            - model_class [str]:
                Model class associated with related model.
            - many [bool]:
                Return always True indicating the user will receive a list
                of objects.
            - pk_field [str]:
                Pk field associated with origin model class that will be used
                to query related models at foreign_key.
            - foreign_key [str]:
                Foreign Key that will be used to fetch realated models using
                origin model foreign key.
            - order_by [list[str]]:
                List of fields to be used to order results from realted
                models.
            - fields [list[str]]:
                List of fields that will be returned by related model. If not
                set default list fields from related model will be used.
        """
        # Get information from related field
        model = self.parent.Meta.model
        parent_field = getattr(model, self.source)
        foreign_key = parent_field.field.column

        pk_field = parent_field.rel.target_field
        pk_field_return = \
            'pk' if pk_field.primary_key else pk_field.column

        model_class = parent_field.rel.related_model.__name__
        return RelatedColumnExtraInfo(
            model_class=model_class,
            pk_field=pk_field_return,
            foreign_key=foreign_key,
            complementary_foreign_key={},
            fields=self.fields,
            many=True)
