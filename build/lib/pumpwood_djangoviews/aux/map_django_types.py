"""Create a dictionary to map django columns with python types."""

django_map = {
    'BooleanField': 'bool',
    'NullBooleanField': 'bool',

    'DateField': 'date',
    'TimeField': 'time',
    'DateTimeField': 'datetime',

    'AutoField': 'int',
    'BigAutoField': 'int',
    'ForeignKey': 'int',

    'IntegerField': 'int',
    'BigIntegerField': 'int',
    'PositiveIntegerField': 'int',
    'SmallIntegerField': 'int',
    'PositiveSmallIntegerField': 'int',

    'DecimalField': 'float',
    'FloatField': 'float',

    'CharField': 'str',
    'TextField': 'str',
    'CommaSeparatedIntegerField': 'str',
    'EmailField': 'str',
    'FileField': 'str',
    'FilePathField': 'str',
    'BinaryField': 'bytes',
    'ImageField': 'str',
    'GenericIPAddressField': 'str',
    'SlugField': 'str',
    'URLField': 'str',
    'UUIDField': 'str',

    'JSONField': 'dict'
}
