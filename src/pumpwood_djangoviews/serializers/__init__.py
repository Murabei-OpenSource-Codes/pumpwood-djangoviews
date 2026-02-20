"""Module to implement custom serializers and fields."""
from .fields import (
    ClassNameField, LocalForeignKeyField, LocalRelatedField,
    MicroserviceForeignKeyField, MicroserviceRelatedField)
from .general import DynamicFieldsModelSerializer

__all__ = (
    DynamicFieldsModelSerializer,
    ClassNameField, LocalForeignKeyField, LocalRelatedField,
    MicroserviceForeignKeyField, MicroserviceRelatedField
)
