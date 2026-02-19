"""Module for Microservice related field implementation."""
from rest_framework import serializers
from pumpwood_communication import exceptions
from pumpwood_communication.microservices import PumpWoodMicroService
from pumpwood_communication.type import (
    ForeignKeyColumnExtraInfo, RelatedColumnExtraInfo)


class MicroserviceForeignKeyField(serializers.Field):
    """Serializer field for ForeignKey using microservice.

    This serializer will fetch object data from a microservice using a
    microservice object.

    This field makes a call to the loadbalancer, caution when microservice
    calls the same microservice of origin or serialization might result on
    circular fetching.

    MicroserviceForeignKeyField are always set as `required=False` and
    `read_only=True`.

    Example of usage:
    ```python
    class MetabaseDashboardSerializer(DynamicFieldsModelSerializer):
        pk = serializers.IntegerField(
            source='id', allow_null=True, required=False)
        model_class = ClassNameField()

        # Foreign Key
        # Will return the object data associated with updated_by_id at
        # updated_by key at the serialized object.
        updated_by = MicroserviceForeignKeyField(
            model_class="User", source="updated_by_id",
            microservice=microservice, display_field='username')
    ```
    """

    microservice: PumpWoodMicroService
    """Microservice object that will make retrieve calls for foreign key
       object."""
    model_class: str
    """String setting the foreign key destiny model_class."""
    display_field: str
    """Set a display field to be returned as __display_field__ at foreign key
       object. This might help frontend rendering dropdown or other
       visualizations."""
    fields: list[str]
    """List of the field that will be returned with foreign key object."""

    def __init__(self, source: str, microservice: PumpWoodMicroService,
                 model_class: str, display_field: str = None,
                 fields: list[str] = None, request=None, **kwargs):
        """__init__.

        Args:
            source (str):
                Source attribute that contains id value associated with
                a foreign key.
            microservice (PumpWoodMicroService):
                PumpWoodMicroService object that will be used to fetch
                information of the object associated with foreign key id.
            model_class (str):
                Model class that will be used to request information at
                with a retrieve.
            display_field (str):
                Field that will be set as `__display_field__` at object
                dictonary.
            fields List (str):
                List of the fields that should be returned at the object.
            fields (list[str]):
                List fields that will be retuned at the serialization.
            request:
                Django request, passed a argument for recursive serialization
                of the object.
            **kwargs (dict):
                Other named arguments to be passed to field.
        """
        self.microservice = microservice
        self.model_class = model_class
        self.display_field = display_field
        self.fields = fields

        # Set as read only and not required, changes on foreign key must be
        # done using id
        kwargs['required'] = False
        kwargs['read_only'] = True
        super(MicroserviceForeignKeyField, self).__init__(
            source=source, **kwargs)

    def get_fields_options_key(self):
        """Return key that will be used on fill options return.

        @private
        """
        return self.source

    def bind(self, field_name, parent):
        """@private."""
        # In order to enforce a consistent style, we error if a redundant
        # 'method_name' argument has been used. For example:
        # my_field = serializer.CharField(source='my_field')
        if self.field_name is None:
            self.field_name = field_name
        else:
            if self.field_name == field_name:
                msg = (
                    "It is redundant to specify field_name when it "
                    "is the same")
                raise AttributeError(msg)

        super(MicroserviceForeignKeyField, self).bind(field_name, parent)

    def get_attribute(self, obj):
        """@private."""
        return obj

    def _microservice_retrieve(self, object_pk: int | str,
                               fields: list[str]) -> dict:
        """Retrieve data using microservice and cache results.

        Retrieve data using list one at the destination model_class, it
        will cache de results on request object to reduce processing time.

        Args:
            object_pk (Union[int, str]):
                Object primary key to retrieve information using
                microservice.
            fields (list[str]):
                Limit the fields that will be returned using microservice.
        """
        # Fetch data retrieved from microservice in same request, this
        # is usefull specially when using list end-points with forenging kes
        # request = self.parent.context.get('request')

        try:
            # Use disk cache to reduce calls to backend
            object_data = self.microservice.list_one(
                model_class=self.model_class, pk=object_pk,
                fields=self.fields, use_disk_cache=True)
        except exceptions.PumpWoodObjectDoesNotExist:
            return {
                "model_class": self.model_class,
                "__error__": 'PumpWoodObjectDoesNotExist'}

        if self.display_field is not None:
            if self.display_field not in object_data.keys():
                msg = (
                    "Serializer not correctly configured, it is not possible "
                    "to find display_field[{display_field}] at the object "
                    "of foreign_key[{foreign_key}] liked to "
                    "model_class[{model_class}]").format(
                        display_field=self.display_field,
                        foreign_key=self.name, model_class=self.model_class)
                raise exceptions.PumpWoodOtherException(
                    msg, payload={
                        "display_field": self.display_field,
                        "foreign_key": self.name,
                        "model_class": self.model_class})
            object_data['__display_field__'] = object_data[self.display_field]
        else:
            object_data['__display_field__'] = None
        return object_data

    def to_representation(self, obj) -> dict:
        """Use microservice to get object at serialization.

        Args:
            obj:
                Model object to retrieve foreign key associated object.

        Returns:
            Return the object associated with foreign key.
        """
        self.microservice.login()
        object_pk = getattr(obj, self.source)
        # Return an empty object if object pk is None
        if object_pk is None:
            return {"model_class": self.model_class}
        return self._microservice_retrieve(
            object_pk=object_pk, fields=self.fields)

    def to_internal_value(self, data):
        """Raise error always, does not unserialize objects of this field.

        Raises:
            NotImplementedError:
                Always raise NotImplementedError if try to unserialize the
                object.
        """
        raise NotImplementedError(
            "MicroserviceForeignKeyField are read-only")

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
        source_id = self.source
        return [source_id]

    def to_dict(self) -> dict:
        """Return a dict with values to be used on options end-point.

        Returns:
            Return a dictonary with information of the field. Keys associated:
            - **model_class [str]:** Model class associated with foreign key.
            - **many [str]:** If it will return a list of objects of one.
                Foreign Key serializer will always return one object.
            - **display_field [str]:** Display field that will be set to
                __display_field__ key on serialized object.
            - **fields [str]:**
                If set, fields that will be returned by serializer, if not set
                will return de default list fields.
            - **object_field [str]:**
                Name of the object field associated with the foreign key
                (this field).
        """
        source_keys = self.get_source_pk_fields()
        return ForeignKeyColumnExtraInfo(
            model_class=self.model_class,
            display_field=self.display_field,
            object_field=self.field_name,
            source_keys=source_keys)


class MicroserviceRelatedField(serializers.Field):
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
        dashboard_set = MicroserviceRelatedField(
            model_class="Dashboard", foreign_key:="updated_by_id",
            pk_field='pk', order_by=["-created_at"],
            fields=["pk", "model_class", "description", "type"])
    ```
    """

    microservice: PumpWoodMicroService
    """PumpWoodMicroService object that is used on API calls."""
    model_class: str
    """Model class associated with related models."""
    foreign_key: str
    """Field associated with origin model class
       (actual.id->destiny.foreign_key)."""
    pk_field: str
    """Actual object field that will be considered as a primary key to fetch
       destiny objects."""
    order_by: list[str]
    """Fields that will order related model results, reverse can be applied
       using "-" at the begging of field name. Ex: `['-created_at']`."""
    fields: list[str]
    """Fields that will be returned from related model, if not set default
       list fields will be returned."""

    def __init__(self, microservice: PumpWoodMicroService,
                 model_class: str, foreign_key: str,
                 pk_field: str = 'id', order_by: str = ["id"],
                 fields: list[str] = None, **kwargs):
        """__init__.

        Args:
            microservice (PumpWoodMicroService):
                PumpWoodMicroService object that is used on API calls.
            model_class (str):
                Model class associated with related models.
            foreign_key (str):
                Field associated with origin model class
                (actual.id->destiny.foreign_key).
            pk_field (str):
                Actual object field that will be considered as a primary key
                to fetch destiny objects.
            order_by (str):
                Fields that will order related model results, reverse can be
                applied using "-" at the begging of field name.
                Ex: `['-created_at']`.
            fields (list[str]):
                Fields that will be returned from related model, if not set
                default list fields will be returned.
            help_text (str):
                Help text associated with related field.
            **kwargs:
                Other keywords for field.
        """
        if type(order_by) is not list:
            msg = ('order_by must be a list of strings. order_by={order_by}')\
                .format(order_by=order_by)
            raise AttributeError(msg)

        self.microservice = microservice
        self.model_class = model_class
        self.foreign_key = foreign_key
        self.pk_field = pk_field
        self.order_by = order_by
        self.fields = fields

        # Force field not be necessary for saving object
        kwargs["required"] = False
        kwargs["read_only"] = True

        # Set as read only and not required, changes on foreign key must be
        # done using id
        super(MicroserviceRelatedField, self).__init__(**kwargs)

    def get_fields_options_key(self):
        """Return key that will be used on fill options return.

        @private
        """
        return self.source

    def bind(self, field_name, parent):
        """@private."""
        # In order to enforce a consistent style, we error if a redundant
        # 'method_name' argument has been used. For example:
        # my_field = serializer.CharField(source='my_field')
        if self.field_name is None:
            self.field_name = field_name
        else:
            if self.field_name == field_name:
                msg = (
                    "It is redundant to specify field_name when it "
                    "is the same")
                raise AttributeError(msg)
        super(MicroserviceRelatedField, self).bind(field_name, parent)

    def get_attribute(self, obj):
        """@private."""
        return obj

    def to_representation(self, obj) -> list[str]:
        """Use microservice to get object at serialization.

        @private.
        """
        self.microservice.login()
        pk_field = getattr(obj, self.pk_field)
        return self.microservice.list_without_pag(
            model_class=self.model_class,
            filter_dict={self.foreign_key: pk_field},
            default_fields=True, fields=self.fields,
            order_by=self.order_by)

    def to_internal_value(self, data):
        """Unserialize data from related objects as empty dictionary.

        @private.
        """
        return {}

    def to_dict(self) -> dict:
        """Return a dict with values to be used on options end-point.

        Returns:
            A dictionary with serialized object.
            - model_class (str):
                Associated with serializer arguments.
            - many (bool):
                Will always return True sinalizing that a list of objcts
                with realated information.
            - pk_field (str):
                Model pk associated with realated foreign key.
            - foreign_key (str):
                Forening key field associated with orgin model class.
            - order_by (list[str]):
                List of fields that will order the results.
        """
        return RelatedColumnExtraInfo(
            model_class=self.model_class,
            pk_field=self.pk_field,
            foreign_key=self.foreign_key,
            complementary_foreign_key={},
            fields=self.fields,
            many=True)
