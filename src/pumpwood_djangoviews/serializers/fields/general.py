"""General fields used om Pumpwood Systems."""
from rest_framework import serializers


class ClassNameField(serializers.Field):
    """Serializer Field that returns model name.

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
        """Pass the object instance onto `to_representation`.

        @private
        """
        return obj

    def to_representation(self, obj):
        """Serialize the object's class name.

        ENDPOINT_SUFFIX enviroment variable is DEPRECTED.
        @private
        """
        return obj.__class__.__name__

    def to_internal_value(self, data):
        """Make no treatment of the income data.

        @private
        """
        return data
