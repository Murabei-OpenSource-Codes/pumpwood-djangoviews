"""
Define widgets that can be used on Django Admin.

Define widgets to be used in Django admin and map foreign key fields.
"""
from django.forms import Select
from typing import List
from pumpwood_communication.microservices import PumpWoodMicroService


class PumpWoodForeignKeySelect(Select):
    """Widget for Foreign Keys associated with other microservices."""

    template_name = 'pumpwood_views/foreign_key_select.html'
    option_template_name = 'pumpwood_views/foreign_key_select_option.html'

    microservice: PumpWoodMicroService
    """PumpWoodMicroService object to fetch information from
       foreign key field."""
    model_class: str
    """Model class to search for foreign keys."""
    description_field: str
    """Field to return on dropdown options."""
    pk_field: str
    """Field to be use as primary key at related table."""
    filter_dict: dict
    """Base filter_dict for query."""
    exclude_dict: dict
    """Base exclude_dict for query."""
    widget_readonly: bool
    """Define if the widget will be considered read-only."""
    order_by: List[str]
    """Base order_by list. If not set results will be ordered by
       description_field."""

    def __init__(self, model_class: str, microservice: PumpWoodMicroService,
                 description_field: str, pk_field: str = "pk",
                 filter_dict: dict = {}, exclude_dict: dict = {},
                 order_by: List[str] = None, attrs=None,
                 widget_readonly: bool = False):
        """__init__.

        Args:
            model_class (str):
                Model class to search for foreign keys.
            microservice (PumpWoodMicroService):
                PumpWoodMicroService object to fetch information from
                foreign key field.
            description_field (str):
                Field to return on dropdown options.
            pk_field (str):
                Field to be use as primary key at related table.
            filter_dict (dict):
                Base filter_dict for query.
            exclude_dict (dict):
                Base exclude_dict for query.
            order_by (List[str]):
                Base order_by list. If not set results will be ordered by
                description_field.
            attrs:
                attrs argument used on the widget.
            widget_readonly (bool):
                Define if the widget will be considered read-only.
        """
        super().__init__()
        self.microservice = microservice
        self.model_class = model_class
        self.description_field = description_field
        self.pk_field = pk_field
        self.filter_dict = filter_dict
        self.exclude_dict = exclude_dict
        self.widget_readonly = widget_readonly

        # If order by not set, order using self.description_field
        if order_by is None:
            order_by = [self.description_field]
        self.order_by = order_by
        super().__init__(attrs, choices=())

    def render(self, name, value, attrs=None, renderer=None):
        """Overwrite defult behaviour to set choices.

        Use `get_descriptions` functions to fetch objects from foreign key
        microservice and set them to choices at dropdown.
        """
        # Set choices for microservice
        fk_descriptions = self.get_descriptions()
        self.choices = fk_descriptions
        return super().render(name, value, attrs, renderer)

    def get_context(self, name, value, attrs):
        """Overwrite defult behaviour to set readonly_select.

        Use `widget_readonly` to set if field is read-only.
        """
        attrs["readonly_select"] = self.widget_readonly
        context = super().get_context(name, value, attrs)
        return context

    def get_descriptions(self) -> List:
        """Auxiliary function to fetch foreign key choices.

        Use `model_class` attribute to fetch information of the possible
        choices associated with foreign key.

        Returns:
            Returns a list of tuples with avaiable foreign key object as
            (object[self.pk_field], object[self.description_field]).
        """
        self.microservice.login()
        optons_description = self.microservice.list_without_pag(
            model_class=self.model_class, order_by=[self.description_field],
            fields=[self.pk_field, self.description_field])

        final_result = [
            (r[self.pk_field], r[self.description_field])
            for r in optons_description]
        return final_result
