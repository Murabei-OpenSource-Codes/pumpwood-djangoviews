"""Define base serializer for pumpwood and custom fields."""
import os
import importlib
from typing import List, Union
from rest_framework import serializers
from pumpwood_communication.microservices import PumpWoodMicroService


def _import_function_by_string(module_function_string):
    """Help when importing a function using a string."""
    # Split the module and function names
    module_name, function_name = module_function_string.rsplit('.', 1)
    # Import the module
    module = importlib.import_module(module_name)
    # Retrieve the function
    func = getattr(module, function_name)
    return func


class ClassNameField(serializers.Field):
    """
    Serializer Field that returns model name.

    It is used as default at Pumpwood to `model_class` always returning
    model_class with objects.

    ```python
    class CustomSerializer(serializers.ModelSerializer):
        model_class = ClassNameField()
    ```
    """

    def __init__(self, **kwargs):
        """@private."""
        kwargs['read_only'] = True
        super(ClassNameField, self).__init__(**kwargs)

    def get_attribute(self, obj):
        """
        Pass the object instance onto `to_representation`.

        @private
        """
        return obj

    def to_representation(self, obj):
        """
        Serialize the object's class name.

        ENDPOINT_SUFFIX enviroment variable is DEPRECTED.
        @private
        """
        suffix = os.getenv('ENDPOINT_SUFFIX', '')
        return suffix + obj.__class__.__name__

    def to_internal_value(self, data):
        """
        Make no treatment of the income data.

        @private
        """
        return data


####################################
# Microservice related serializers #
class MicroserviceForeignKeyField(serializers.Field):
    """
    Serializer field for ForeignKey using microservice.

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
    fields: List[str]
    """List of the field that will be returned with foreign key object."""

    def __init__(self, source: str, microservice: PumpWoodMicroService,
                 model_class: str,  display_field: str = None,
                 fields: List[str] = None, **kwargs):
        """
        __init__.

        Args:
            source [str]:
                Source attribute that contains id value associated with
                a foreign key.
            microservice [PumpWoodMicroService]:
                PumpWoodMicroService object that will be used to fetch
                information of the object associated with foreign key id.
            model_class [str]:
                Model class that will be used to request information at
                with a retrieve.
            display_field [str]:
                Field that will be set as `__display_field__` at object
                dictonary.
            fields List [str]:
                List of the fields that should be returned at the object.
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
        """
        Return key that will be used on fill options return.

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
            assert self.field_name != field_name, (
              "It is redundant to specify field_name when it is the same")
        super(MicroserviceForeignKeyField, self).bind(field_name, parent)

    def get_attribute(self, obj):
        """@private."""
        return obj

    def to_representation(self, obj) -> dict:
        """
        Use microservice to get object at serialization.

        Args:
            obj: Model object to retrieve foreign key associated object.
        Returns:
            Return the object associated with foreign key.
        """
        self.microservice.login()

        object_pk = getattr(obj, self.source)
        # Return an empty object if object pk is None
        if object_pk is None:
            return {"model_class": self.model_class}

        object_data = self.microservice.retrieve(
            model_class=self.model_class, pk=object_pk,
            default_fields=True, fields=self.fields)
        object_data['__display_field__'] = object_data.get(self.display_field)
        return object_data

    def to_internal_value(self, data):
        """
        Raise error always, does not unserialize objects of this field.

        Raises:
            NotImplementedError:
                Always raise NotImplementedError if try to unserialize the
                object.
        """
        raise NotImplementedError(
            "MicroserviceForeignKeyField are read-only")

    def to_dict(self) -> dict:
        """
        Return a dict with values to be used on options end-point.

        Returns:
            Return a dictonary with information of the field. Keys associated:
            - **model_class [str]:** Model class associated with foreign key.
            - **many [str]:** If it will return a list of objects of one.
                Foreign Key serializer will always return one object.
            - **display_field [str]:** Display field that will be set to
                __display_field__ key on serialized object.
            - **fields [str]:** If set, fields that will be returned by
                serializer, if not set will return de default list fields.
            - **object_field [str]:** Name of the object field associated
                with the foreign key (this field).
        """
        return {
            'model_class': self.model_class,
            'many': False,
            'display_field': self.display_field,
            'fields': self.fields,
            'object_field': self.field_name}


class MicroserviceRelatedField(serializers.Field):
    """
    Serializer field for related objects using microservice.

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
    order_by: List[str]
    """Fields that will order related model results, reverse can be applied
       using "-" at the begging of field name. Ex: `['-created_at']`."""
    fields: List[str]
    """Fields that will be returned from related model, if not set default
       list fields will be returned."""

    def __init__(self, microservice: PumpWoodMicroService,
                 model_class: str,  foreign_key: str,
                 pk_field: str = 'id', order_by: str = ["id"],
                 fields: List[str] = None, **kwargs):
        """
        __init__.

        Args:
            microservice [PumpWoodMicroService]:
                PumpWoodMicroService object that is used on API calls.
            model_class [str]:
                Model class associated with related models.
            foreign_key [str]:
                Field associated with origin model class
                (actual.id->destiny.foreign_key).
            pk_field [str]:
                Actual object field that will be considered as a primary key
                to fetch destiny objects.
            order_by [str]:
                Fields that will order related model results, reverse can be
                applied using "-" at the begging of field name.
                Ex: `['-created_at']`.
            fields List[str]:
                Fields that will be returned from related model, if not set
                default list fields will be returned.
        """
        self.microservice = microservice
        self.model_class = model_class
        self.foreign_key = foreign_key
        self.pk_field = pk_field
        self.order_by = order_by
        self.fields = fields

        # Force field not be necessary for saving object
        kwargs["required"] = False
        kwargs["read_only"] = False

        # Set as read only and not required, changes on foreign key must be
        # done using id
        super(MicroserviceRelatedField, self).__init__(**kwargs)

    def get_fields_options_key(self):
        """
        Return key that will be used on fill options return.

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
            assert self.field_name != field_name, (
              "It is redundant to specify field_name when it is the same")
        super(MicroserviceRelatedField, self).bind(field_name, parent)

    def get_attribute(self, obj):
        """@private."""
        return obj

    def to_representation(self, obj) -> List[str]:
        """
        Use microservice to get object at serialization.

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
        """
        Unserialize data from related objects as empty dictionary.

        @private.
        """
        return {}

    def to_dict(self) -> dict:
        """
        Return a dict with values to be used on options end-point.

        Returns:
            model_class [str]:
                Associated with serializer arguments.
            many [bool]:
                Will always return True sinalizing that a list of objcts
                with realated information.
            pk_field [str]:
                Model pk associated with realated foreign key.
            foreign_key [str]:
                Forening key field associated with orgin model class.
            order_by [List[str]]:
                List of fields that will order the results.
        """
        return {
            'model_class': self.model_class, 'many': True,
            'pk_field': self.pk_field, 'order_by': self.order_by,
            'foreign_key': self.foreign_key, 'fields': self.fields}


##################################
# Local foreign keys serializers #
class LocalForeignKeyField(serializers.Field):
    """
    Serializer field for ForeignKey using database connection.

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
    serializer: Union[str, serializers.ModelSerializer]
    """Serializer or string to serializer path that will be lazy loaded."""
    display_field: str
    """Display field that will be set to `__display_field__` key at the
       object."""
    fields: List[str]
    """Limit the return fields to fields set, if not set will return list
       default fields."""

    def __init__(self, serializer: Union[str, serializers.ModelSerializer],
                 display_field: str = None, fields: List[str] = None,
                 **kwargs):
        """
        __init__.

        Args:
            serializer Union[str, serializers.ModelSerializer]:
                Serializer can be lazy loaded passing the path to avoid
                circular import, serializer_cache will cache serializer to
                remove necessity of importing the serializer at every request.
            display_field [str]:
                Display field that will be set to `__display_field__` key at
                the object.
            fields List[str]:
                Limit the return fields to fields set, if not set will return
                list default fields.
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
        """
        Return key that will be used on fill options return.

        @private
        """
        model = self.parent.Meta.model
        parent_field = getattr(model, self.source)
        return parent_field.field.column

    def to_representation(self, value):
        if self.serializer_cache is None:
            if type(self.serializer) is str:
                self.serializer_cache = _import_function_by_string(
                    self.serializer)
            else:
                self.serializer_cache = self.serializer

        # Return an empty object if object pk is None
        if value is None:
            model = self.parent.Meta.model
            parent_field = getattr(model, self.source)
            model_class = parent_field.field.related_model.__name__
            return {"model_class": model_class}

        data = self.serializer_cache(
            value, many=False, fields=self.fields,
            default_fields=True).data
        display_field = data.get(self.display_field, None)
        data['__display_field__'] = display_field
        return data

    def to_dict(self) -> dict:
        """
        Return a dict with values to be used on options end-point.

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
            fields [List[str]]:
                If not None will restrict the fields returned at object.
        """
        model = self.parent.Meta.model
        parent_field = getattr(model, self.source)
        model_class = parent_field.field.related_model.__name__
        return {
            'model_class': model_class, 'many': False,
            'display_field': self.display_field,
            'object_field': self.field_name, 'fields': self.fields}


class LocalRelatedField(serializers.Field):
    """
    Serializer field for related objects using microservice.

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

    def __init__(self, serializer, order_by: List[str] = ["-id"],
                 fields: List[str] = None, **kwargs):
        # Avoid circular imports for related models and cache lazzy loaded
        # serializers
        self.serializer_cache = None
        self.serializer = serializer
        self.order_by = order_by
        self.fields = fields
        kwargs['read_only'] = True
        super(LocalRelatedField, self).__init__(**kwargs)

    def get_fields_options_key(self):
        """
        Return key that will be used on fill options return.

        @private
        """
        return self.source

    def to_representation(self, value):
        """
        Return all related data serialized.

        @private
        """
        if self.serializer_cache is None:
            if type(self.serializer) is str:
                self.serializer_cache = _import_function_by_string(
                    self.serializer)
            else:
                self.serializer_cache = self.serializer
        return self.serializer_cache(
            value.order_by(*self.order_by).all(),
            many=True, default_fields=True,
            fields=self.fields).data

    def to_dict(self):
        """
        Return a dict with values to be used on options end-point.

        Returns:
            model_class [str]:
                Model class associated with related model.
            many [bool]:
                Return always True indicating the user will receive a list
                of objects.
            pk_field [str]:
                Pk field associated with origin model class that will be used
                to query related models at foreign_key.
            foreign_key [str]:
                Foreign Key that will be used to fetch realated models using
                origin model foreign key.
            order_by [List[str]]:
                List of fields to be used to order results from realted
                models.
            fields [List[str]]:
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
        return {
            'model_class': model_class,
            'many': True,
            "pk_field": pk_field_return,
            'order_by': self.order_by,
            'fields': self.fields,
            'foreign_key': foreign_key}


class DynamicFieldsModelSerializer(serializers.ModelSerializer):
    """
    A ModelSerializer that change fields returned on serialization.

    This serializer make possible to change the serialization fields acording
    to arguments that are passed on serializer instanciation.

    #### Default list fields
    Attribute `list_fields` set the default fields that will be returned
    if `default_fields=True` argument is set.

    #### Usage with foreign key
    Foreign keys can be returned both for many=True and also many=False
    serializations passing `foreign_key_fields=True` argument.

    #### Usage with related objects
    Serialization of many objects will not return related models serializers (
    MicroserviceRelatedField, LocalRelatedField). This behaviour will overide
    related_fields argumment, even if set as related_fields=True.

    Related Models serizalization is an expensive request at backend, should
    be used only for `many=False` serialization (one object).

    #### Usage with fields argument
    All fields set on fields argument will be returned dispite beeing
    foreign key or related and arguments `related_fields=False`,
    `foreign_key_fields=False`.

    Examples:
        ```python
        from serializers import SerializerCompany


        # Defining serializer for User object
        class SerializerUser(DynamicFieldsModelSerializer):
            pk = serializers.IntegerField(source='id', allow_null=True)
            model_class = ClassNameField()

            # ForeignKey
            api_permission_set = LocalRelatedField(
                serializer=(
                    "pumpwood_djangoauth.api_permission."
                    "serializers.SerializerPumpwoodPermissionPolicyUserM2M"),
                order_by=["-id"])
            api_permission_group_set = LocalRelatedField(
                serializer=(
                    "pumpwood_djangoauth.api_permission."
                    "serializers.SerializerPumpwoodPermissionUserGroupM2M"),
                order_by=["-id"])
            company = LocalRelatedField(serializer=SerializerCompany)

            class Meta:
                model = User
                fields = (
                    'pk', 'model_class', 'username', 'email', 'first_name',
                    'last_name', 'last_login', 'date_joined', 'is_active',
                    'is_staff', 'is_superuser', 'mfa_method_set',
                    'api_permission_set', 'api_permission_group_set',
                    'company')
                list_fields = [
                    "pk", "model_class", 'is_active', 'is_superuser',
                    'is_staff', 'username', 'email', 'last_login']
                read_only = ('last_login', 'date_joined')


        # Query for User objects
        all_users = User.objects.all()

        # Create a serializer that will return just ['pk', 'username']
        # fields when dumping the objects.
        user_data = UserDynamicFieldsModelSerializer(
            all_users, many=True, fields=['pk', 'description'],
            foreign_key_fields=False, related_fields=False,
            default_fields=False)

        # Return all fields except for foreign key and related models.
        # ['pk', 'model_class', 'username', 'email', 'first_name',
        #  'last_name', 'last_login', 'date_joined', 'is_active',
        #  'is_staff', 'is_superuser']
        user_data = UserDynamicFieldsModelSerializer(
            all_users, many=True, fields=['pk', 'description'],
            foreign_key_fields=False, related_fields=False,
            default_fields=False).data

        # Return all fields including foreign key and except related models
        # (serializing many=True).
        # ['pk', 'model_class', 'username', 'email', 'first_name',
        #  'last_name', 'last_login', 'date_joined', 'is_active',
        #  'is_staff', 'is_superuser', 'company']
        user_data = UserDynamicFieldsModelSerializer(
            all_users, many=True, fields=None,
            foreign_key_fields=True,
            # related_fields=True will be ignored for many=True
            related_fields=True,
            default_fields=False).data

        # Return fields set as default list fields
        # ["pk", "model_class", 'is_active', 'is_superuser',
        #  'is_staff', 'username', 'email', 'last_login']
        user_data = UserDynamicFieldsModelSerializer(
            all_users, many=True, fields=['pk', 'description'],
            foreign_key_fields=False, related_fields=False,
            default_fields=True).data

        # Return all fields including foreign key and related for one
        # object
        # ['pk', 'model_class', 'username', 'email', 'first_name',
        #  'last_name', 'last_login', 'date_joined', 'is_active',
        #  'is_staff', 'is_superuser', 'mfa_method_set',
        #  'api_permission_set', 'api_permission_group_set',
        #  'company']
        user_data = UserDynamicFieldsModelSerializer(
            all_users[0], many=False, fields=None,
            foreign_key_fields=True, related_fields=True,
            default_fields=False).data

        # Return all fields, but foreign key and related for one
        # object
        # ['pk', 'model_class', 'username', 'email', 'first_name',
        #  'last_name', 'last_login', 'date_joined', 'is_active',
        #  'is_staff', 'is_superuser']
        user_data = UserDynamicFieldsModelSerializer(
            all_users[0], many=False, fields=None,
            foreign_key_fields=False, related_fields=False,
            default_fields=False).data
        ```
    """

    model_class = ClassNameField()
    """Always `model_class` associated with object for all Pumpwood objects.
       Set default ClassNameField() for this field"""

    def __init__(self, *args, **kwargs):
        """
        __init__.

        Extend ModelSerializer from rest framework.

        Args:
            fields [List[str]]:
                It is set internaly as `None` using the kwargs. List
                the fields that should be dumped.
            default_fields [bool]:
                It is set internaly as `False` using the kwargs. Set if only
                default list fields set on `Meta.list_fields` should be
                dumped.
            foreign_key_fields [bool]:
                It is set internaly as `False` using the kwargs. Set if foreign
                keys should be retuned.
            related_fields [bool]:
                It is set internaly as `False` using the kwargs. Set if related
                models should be retuned (only at many=False serializations).
        """
        # Don't pass the 'fields' arg up to the superclass
        many = kwargs.get("many", False)

        # Extract custom fields
        fields = kwargs.pop("fields", None)
        default_fields = kwargs.pop("default_fields", False)
        foreign_key_fields = kwargs.pop("foreign_key_fields", False)
        related_fields = kwargs.pop("related_fields", False)

        # Instantiate the superclass normally
        super(DynamicFieldsModelSerializer, self).__init__(*args, **kwargs)

        # default_fields is True, return the ones specified by
        # Meta.list_fields
        if default_fields and fields is None:
            fields = self.get_list_fields()
        ##########################

        # Remove fields that are not on fields and are fk related to reduce #
        # requests to other microservices
        to_remove = []
        for key, item in self.fields.items():
            # If field are set then use fields that were sent by user to make
            # serialization
            if fields is not None:
                if key not in fields:
                    to_remove.append(key)
            else:
                ##############################################
                # Keep related only if user ask to keep them #
                is_related_local = isinstance(item, LocalRelatedField)
                is_related_micro = isinstance(item, MicroserviceRelatedField)
                is_related = is_related_local or is_related_micro
                if (is_related and not related_fields) or many:
                    to_remove.append(key)
                    continue

                #####################################
                # Keep FK only if user ask for them #
                is_foreign_key_local = isinstance(
                    item, LocalForeignKeyField)
                is_foreign_key_micro = isinstance(
                    item, MicroserviceForeignKeyField)
                is_foreign_key = is_foreign_key_local or is_foreign_key_micro
                if (is_foreign_key and not foreign_key_fields):
                    to_remove.append(key)
                    continue

        for field_name in to_remove:
            self.fields.pop(field_name)

    def get_list_fields(self) -> List[str]:
        """
        Get list fields from serializer.

        Default behaviour is to extract `list_fields` from Meta class.

        This method can be overwriten for custom behaviour.

        Args:
            No Args.
        Returns:
            Default fields to be used at default_fields=True
            serializations.
        """
        list_fields = getattr(self.Meta, 'list_fields', None)
        if list_fields is None:
            return list(self.fields.keys())
        return list_fields

    def get_foreign_keys(self) -> dict:
        """
        Return a dictonary with all foreign_key fields.

        This methods is used at fill_options end-point to correctly treat
        foreign keys.

        Returns:
            Return a dictionary with field name as keys and relation
            information as value.
        """
        return_dict = {}
        for field_name, field in self.fields.items():
            is_micro_fk = isinstance(field, MicroserviceForeignKeyField)
            if is_micro_fk:
                return_dict[field.source] = field.to_dict()
        return return_dict

    def get_related_fields(self):
        """
        Return a dictionary with all related fields (M2M).

        This methods is used at fill_options end-point to correctly treat
        related fields.

        Returns:
            Return a dictionary with field name as keys and relation
            information as value.
        """
        return_dict = {}
        for field_name, field in self.fields.items():
            is_micro_rel = isinstance(field, MicroserviceRelatedField)
            if is_micro_rel:
                return_dict[field.name] = field.to_dict()
        return return_dict
