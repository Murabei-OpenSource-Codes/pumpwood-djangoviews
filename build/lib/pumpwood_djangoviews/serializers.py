"""Set base serializers for PumpWood systems."""
import os
import importlib
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
    """Serializer Field that returns model name."""

    def __init__(self, **kwargs):
        kwargs['read_only'] = True
        super(ClassNameField, self).__init__(**kwargs)

    def get_attribute(self, obj):
        """
        We pass the object instance onto `to_representation`,
        not just the field attribute.
        """
        return obj

    def to_representation(self, obj):
        """Serialize the object's class name."""
        suffix = os.getenv('ENDPOINT_SUFFIX', '')
        return suffix + obj.__class__.__name__

    def to_internal_value(self, data):
        """
        Retorna como uma string para a validação com o nome da
        Classe que o objeto se refere
        """
        return data


class CustomChoiceTypeField(serializers.Field):
    """
    Serializer field for ChoiceTypeField.

    Returns a tupple with both real value on [0] and get_{field_name}_display
    on [1]. to_internal_value uses only de first value os the tupple
    if a tupple, or just the value if not a tupple.
    """

    def __init__(self, field_name=None, **kwargs):
        self.field_name = field_name
        super(CustomChoiceTypeField, self).__init__(**kwargs)

    def bind(self, field_name, parent):
        # In order to enforce a consistent style, we error if a redundant
        # 'method_name' argument has been used. For example:
        # my_field = serializer.CharField(source='my_field')
        if self.field_name is None:
            self.field_name = field_name
        else:
            assert self.field_name != field_name, (
              "It is redundant to specify field_name when it is the same")
        super(CustomChoiceTypeField, self).bind(field_name, parent)

    def get_attribute(self, obj):
        """
        We pass the object instance onto `to_representation`,
        not just the field attribute.
        """
        return obj

    def to_representation(self, obj):
        display_method = 'get_{field_name}_display'.format(
            field_name=self.field_name)
        field_value = getattr(obj, self.field_name)
        if field_value is not None:
            method = getattr(obj, display_method)
            return [field_value, method()]
        else:
            return None

    def to_internal_value(self, data):
        # Pega como valor só o primeiro elemento do choice
        if type(data) == list:
            # Caso esteja retornando a dupla de valores [chave do banco,
            # descrição da opção]
            return data[0]
        else:
            # Caso esteja retornando só o valor da chave do banco
            return data


####################################
# Microservice related serializers #
class MicroserviceForeignKeyField(serializers.Field):
    """
    Serializer field for ForeignKey using microservice.

    Returns a tupple with both real value on [0] and get_{field_name}_display
    on [1]. to_internal_value uses only de first value os the tupple
    if a tupple, or just the value if not a tupple.
    """

    def __init__(self, source: str, microservice: PumpWoodMicroService,
                 model_class: str,  display_field: str, **kwargs):
        self.microservice = microservice
        self.model_class = model_class
        self.display_field = display_field

        # Set as read only and not required, changes on foreign key must be
        # done using id
        kwargs['required'] = False
        kwargs['read_only'] = True
        super(MicroserviceForeignKeyField, self).__init__(
            source=source, **kwargs)

    def get_fields_options_key(self):
        """Return key that will be used on fill options return."""
        return self.source

    def bind(self, field_name, parent):
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
        """
        We pass the object instance onto `to_representation`,
        not just the field attribute.
        """
        return obj

    def to_representation(self, obj):
        """Use microservice to get object at serialization."""
        self.microservice.login()

        object_pk = getattr(obj, self.source)
        # Return an empty object if object pk is None
        if object_pk is None:
            return {"model_class": self.model_class}

        object_data = self.microservice.list_one(
            model_class=self.model_class,
            pk=object_pk)
        object_data['__display_field__'] = object_data[self.display_field]
        return object_data

    def to_internal_value(self, data):
        raise NotImplementedError(
            "MicroserviceForeignKeyField are read-only")

    def to_dict(self):
        """Return a dict with values to be used on options end-point."""
        return {
            'model_class': self.model_class, 'many': False,
            'display_field': self.display_field,
            'object_field': self.field_name}


class MicroserviceRelatedField(serializers.Field):
    """
    Serializer field for related objects using microservice.

    It is an informational serializer to related models.
    """

    def __init__(self, microservice: PumpWoodMicroService,
                 model_class: str,  foreign_key: str,
                 pk_field: str = 'id', order_by: str = ["id"],
                 **kwargs):
        self.microservice = microservice
        self.model_class = model_class
        self.foreign_key = foreign_key
        self.pk_field = pk_field
        self.order_by = order_by

        # Force field not be necessary for saving object
        kwargs["required"] = False
        kwargs["read_only"] = False

        # Set as read only and not required, changes on foreign key must be
        # done using id
        super(MicroserviceRelatedField, self).__init__(**kwargs)

    def get_fields_options_key(self):
        """Return key that will be used on fill options return."""
        return self.source

    def bind(self, field_name, parent):
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
        """
        We pass the object instance onto `to_representation`,
        not just the field attribute.
        """
        return obj

    def to_representation(self, obj):
        """Use microservice to get object at serialization."""
        self.microservice.login()

        pk_field = getattr(obj, self.pk_field)
        return self.microservice.list_without_pag(
            model_class=self.model_class,
            filter_dict={self.foreign_key: pk_field},
            order_by=self.order_by)

    def to_internal_value(self, data):
        """Unserialize data from related objects as empty dictionary."""
        return {}

    def to_dict(self):
        """Return a dict with values to be used on options end-point."""
        return {
            'model_class': self.model_class, 'many': True,
            'pk_field': self.pk_field, 'order_by': self.order_by,
            'foreign_key': self.foreign_key}


##################################
# Local foreign keys serializers #
class LocalForeignKeyField(serializers.Field):
    """
    Serializer field for ForeignKey using microservice.

    Returns a tupple with both real value on [0] and get_{field_name}_display
    on [1]. to_internal_value uses only de first value os the tupple
    if a tupple, or just the value if not a tupple.
    """

    def __init__(self, serializer, display_field: str = None,
                 fields: list = None, **kwargs):
        # Avoid circular imports for related models and cache lazzy loaded
        # serializers
        self.serializer_cache = None
        self.serializer = serializer
        self.display_field = display_field
        self.fields = fields
        kwargs['read_only'] = True
        super(LocalForeignKeyField, self).__init__(**kwargs)

    def get_fields_options_key(self):
        """Return key that will be used on fill options return."""
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
            value, many=False, fields=self.fields).data
        display_field = data.get(self.display_field, None)
        data['__display_field__'] = display_field
        return data

    def to_dict(self):
        """Return a dict with values to be used on options end-point."""
        model = self.parent.Meta.model
        parent_field = getattr(model, self.source)
        model_class = parent_field.field.related_model.__name__
        return {
            'model_class': model_class, 'many': False,
            'display_field': self.display_field,
            'object_field': self.field_name}


class LocalRelatedField(serializers.Field):
    """
    Serializer field for related objects using microservice.

    It is an informational serializer to related models.
    """

    def __init__(self, serializer, order_by=["-id"], **kwargs):
        # Avoid circular imports for related models and cache lazzy loaded
        # serializers
        self.serializer_cache = None
        self.serializer = serializer
        self.order_by = order_by
        kwargs['read_only'] = True
        super(LocalRelatedField, self).__init__(**kwargs)

    def get_fields_options_key(self):
        """Return key that will be used on fill options return."""
        return self.source

    def to_representation(self, value):
        """Return all related data serialized."""
        print("value:", value)
        if self.serializer_cache is None:
            if type(self.serializer) is str:
                self.serializer_cache = _import_function_by_string(
                    self.serializer)
            else:
                self.serializer_cache = self.serializer
        return self.serializer_cache(
            value.order_by(*self.order_by).all(),
            many=True).data

    def to_dict(self):
        """Return a dict with values to be used on options end-point."""
        # Get information from related field
        model = self.parent.Meta.model
        parent_field = getattr(model, self.source)
        foreign_key = parent_field.field.column

        pk_field = parent_field.rel.target_field
        pk_field_return = \
            'pk' if pk_field.primary_key else pk_field.column

        model_class = parent_field.rel.related_model.__name__
        return {
            'model_class': model_class, 'many': True,
            "pk_field": pk_field_return, 'order_by': self.order_by,
            'foreign_key': foreign_key}


class CustomNestedSerializer(serializers.Field):
    """
    Uses the seriazlizer to create the object representation, but only uses
    its pk to get object to its internal value.
    """
    nested_serializer = None
    'Serializer to be used on the model'
    many = False
    'Tells if is a many relation or not'

    def __init__(self, nested_serializer, many, **kwargs):
        self.nested_serializer = nested_serializer
        self.many = many
        super(CustomNestedSerializer, self).__init__(**kwargs)

    def to_representation(self, value):
        return self.nested_serializer(value, many=self.many).data

    def to_internal_value(self, value):
        if self.many:
            pks = []
            for d in value:
                if d == 'None' or d is None:
                    return None
                else:
                    pks.append(d['pk'])
            return self.nested_serializer.Meta.model.objects.filter(pk__in=pks)
        else:
            if value == 'None' or value is None:
                return None
            else:
                return self.nested_serializer.Meta.model.objects.get(
                    pk=value['pk'])


def validator_check_for_pk(value):
    pk = value.get('pk')
    if pk is None:
        raise serializers.ValidationError(
            'Nested relations always need pk field')


def validator_check_for_pk_many(value):
    for value in values:
        pk = value.get('pk')
        if pk is None:
            raise serializers.ValidationError(
                'Nested relations always need pk field')


class DynamicFieldsModelSerializer(serializers.ModelSerializer):
    """A ModelSerializer with fields args in init."""

    def __init__(self, *args, **kwargs):
        # Don't pass the 'fields' arg up to the superclass
        fields = kwargs.pop('fields', None)
        foreign_key_fields = kwargs.pop('foreign_key_fields', False)
        related_fields = kwargs.pop('related_fields', False)
        many = kwargs.get("many", False)

        # Instantiate the superclass normally
        super(DynamicFieldsModelSerializer, self).__init__(*args, **kwargs)

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
                # Keep related only if user ask to keep them
                is_related_local = isinstance(item, LocalRelatedField)
                is_related_micro = isinstance(item, MicroserviceRelatedField)
                is_related = is_related_local or is_related_micro
                if (is_related and not related_fields) or many:
                    to_remove.append(key)
                    continue

                # Keep FK only if user ask for them
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
