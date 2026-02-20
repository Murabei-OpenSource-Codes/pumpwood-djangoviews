"""Module to implement custom fields on Pumpwood Views."""
from .general import ClassNameField
from .local import LocalForeignKeyField, LocalRelatedField
from .microservice import MicroserviceForeignKeyField, MicroserviceRelatedField

__all__ = [
    ClassNameField,
    LocalForeignKeyField, LocalRelatedField,
    MicroserviceForeignKeyField, MicroserviceRelatedField,
]
