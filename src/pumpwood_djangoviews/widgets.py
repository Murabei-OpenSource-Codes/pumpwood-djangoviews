import os
from django.forms import Select, FileField
from pumpwood_communication.microservices import PumpWoodMicroService
from pumpwood_communication.exceptions import PumpWoodException


class PumpWoodForeignKeySelect(Select):
    def __init__(self, model_class: str, microservice: PumpWoodMicroService,
                 description_field: str, pk_field: str = "pk",
                 filter_dict: dict = {}, exclude_dict: dict = {},
                 order_by: list = None):
        """
        __init__

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

        # If order by not set, order using self.description_field
        if order_by is None:
            order_by = [self.description_field]
        self.order_by = order_by

    def render(self, name, value, attrs=None, renderer=None):
        # Set choices for microservice
        self.choices = self.get_descriptions()
        return super().render(
            name=name, value=value, attrs=attrs,
            renderer=renderer)

    def get_descriptions(self):
        self.microservice.login()
        optons_description = self.microservice.list_without_pag(
            model_class=self.model_class, order_by=[self.description_field],
            fields=[self.pk_field, self.description_field])

        final_result = [
            (r[self.pk_field], r[self.description_field])
            for r in optons_description]
        return final_result
