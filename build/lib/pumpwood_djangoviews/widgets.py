import os
import copy
from django.forms import Select, FileField
from pumpwood_communication.microservices import PumpWoodMicroService
from pumpwood_communication.exceptions import PumpWoodException
from django.template.loader import get_template


class PumpWoodForeignKeySelect(Select):
    template_name = 'pumpwood_views/foreign_key_select.html'
    option_template_name = 'pumpwood_views/foreign_key_select_option.html'

    def __init__(self, model_class: str, microservice: PumpWoodMicroService,
                 description_field: str, pk_field: str = "pk",
                 filter_dict: dict = {}, exclude_dict: dict = {},
                 order_by: list = None, attrs=None,
                 widget_readonly: bool = False):
        """
        __init__.

        Args:
            model_class [str]: Model class to search for foreign keys
            microservice [PumpWoodMicroService]:
            description_field [str]: Field to return on dropdown options.

        Kwargs:
            pk_field [str] = "pk": Field to be use as primary key at related
                table.
            filter_dict [dict] = {}: Base filter_dict for query.
            exclude_dict [dict] = {}: Base exclude_dict for query.
            order_by [List[str]] = None: Base order_by list.
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
        # Set choices for microservice
        fk_descriptions = self.get_descriptions()
        self.choices = fk_descriptions
        return super().render(name, value, attrs, renderer)

    def get_context(self, name, value, attrs):
        attrs["readonly_select"] = self.widget_readonly
        context = super().get_context(name, value, attrs)
        return context

    def get_descriptions(self):
        self.microservice.login()
        optons_description = self.microservice.list_without_pag(
            model_class=self.model_class, order_by=[self.description_field],
            fields=[self.pk_field, self.description_field])

        final_result = [
            (r[self.pk_field], r[self.description_field])
            for r in optons_description]
        return final_result
