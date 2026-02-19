"""Define base serializer for pumpwood and custom fields."""
from rest_framework import serializers
from pumpwood_djangoviews.serializers.fields import (
    ClassNameField,
    LocalForeignKeyField, LocalRelatedField,
    MicroserviceForeignKeyField, MicroserviceRelatedField,
)


class DynamicFieldsModelSerializer(serializers.ModelSerializer):
    """A ModelSerializer that change fields returned on serialization.

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
        """__init__.

        Extend ModelSerializer from rest framework.

        Args:
            fields (list[str]):
                It is set internaly as `None` using the kwargs. List
                the fields that should be dumped.
            default_fields (bool):
                It is set internaly as `False` using the kwargs. Set if only
                default list fields set on `Meta.list_fields` should be
                dumped.
            foreign_key_fields (bool):
                It is set internaly as `False` using the kwargs. Set if foreign
                keys should be retuned.
            related_fields (bool):
                It is set internaly as `False` using the kwargs. Set if related
                models should be retuned (only at many=False serializations).
            *args:
                Serializer arguments.
            **kwargs:
                Serializer named arguments.
        """
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
                if (is_related and not related_fields):
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

    def get_list_fields(self) -> list[str]:
        """Get list fields from serializer.

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
        """Return a dictonary with all foreign_key fields.

        This methods is used at fill_options end-point to correctly treat
        foreign keys.

        Returns:
            Return a dictionary with field name as keys and relation
            information as value.
        """
        return_dict = {}
        for field_name, field in self.fields.items():
            target_types = (MicroserviceForeignKeyField, LocalForeignKeyField)
            is_foreign_key = isinstance(field, target_types)
            if is_foreign_key:
                # Use the fist source which msut be the main fk associated
                # with the id from the other model class
                info_object = field.to_dict()
                return_dict[info_object.source_keys[0]] = info_object
        return return_dict

    def get_related_fields(self):
        """Return a dictionary with all related fields (M2M).

        This methods is used at fill_options end-point to correctly treat
        related fields.

        Returns:
            Return a dictionary with field name as keys and relation
            information as value.
        """
        return_dict = {}
        for field_name, field in self.fields.items():
            target_types = (MicroserviceRelatedField, LocalRelatedField)
            is_related = isinstance(field, target_types)
            if is_related:
                return_dict[field_name] = field.to_dict()
        return return_dict
