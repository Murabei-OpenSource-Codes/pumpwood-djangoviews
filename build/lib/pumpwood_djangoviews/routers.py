"""
Define defult Routers for Pumpwood systems.

Pumpwood end-points have defaults paths that are registered at the application.
The end-points are mapped using pumpwood-communication package to be
consumed by the client side.
"""
import os
from slugify import slugify
from django.urls import path
from rest_framework.routers import BaseRouter
from django.core.exceptions import ImproperlyConfigured
from pumpwood_djangoviews.views import (
    PumpWoodRestService, PumpWoodDataBaseRestService)


class PumpWoodRouter(BaseRouter):
    """Define a Router for PumpWoodRestService views.

    Router are used to define default end-points for Pumpwood for each
    model_class.

    Raises:
        ImproperlyConfigured:
            If a view different from PumpWoodRestService is used.

    Example:
        Example of url.py file at Pumpwood Auth package.
        ```python
        from urllib.parse import urljoin
        from django.urls import path
        from django.conf.urls import url
        from pumpwood_djangoviews.routers import PumpWoodRouter
        from pumpwood_djangoauth.config import storage_object, MEDIA_URL
        from pumpwood_djangoauth.metabase import views

        pumpwoodrouter = PumpWoodRouter()
        pumpwoodrouter.register(viewset=views.RestMetabaseDashboard)
        pumpwoodrouter.register(viewset=views.RestMetabaseDashboardParameter)

        urlpatterns = [
        ]

        urlpatterns += pumpwoodrouter.urls
        ```
    """

    def get_default_base_name(self, viewset):
        """Get model class name to create end-points."""
        return viewset.service_model.__name__

    def register(self, viewset):
        """Register view urls using the name of the models as path.

        Args:
            viewset: A view set from rest framework.

        Raises:
            ImproperlyConfigured:
                If view is not a PumpWoodRestService for PumpWoodRouter and
                PumpWoodDataBaseRestService for PumpWoodDataBaseRouter.
        """
        base_name = self.get_default_base_name(viewset)
        suffix = os.getenv('ENDPOINT_SUFFIX', '').lower()
        base_name = slugify(suffix + base_name)
        self.registry.append((viewset, base_name))

    def validate_view(self, viewset):
        """Validate if view is of correct type.

        Args:
            viewset: Rest framework view set, it must have inherited from
            PumpWoodRestService.

        Raises:
            ImproperlyConfigured:
                If view is not a PumpWoodRestService.
        """
        if PumpWoodRestService not in viewset.__bases__:
            raise ImproperlyConfigured(
                "PumpWoodRouter applied over a view that isn't a "
                "PumpWoodRestService")

    def get_registry_pattern(self, viewset, basename):
        """Register patterns for pumpwood end-points.

        Base name is set acording to Model name (model_class).

        Patterns registered:
        - `[POST] rest/{basename}/list/`: List end-point with pagination.
        - `[POST] rest/{basename}/list-without-pag/`: List end-point without
            pagination.
        - `[GET] rest/{basename}/retrieve/{pk}/`: Retrieve data for an
            [pk] object.
        - `[GET] rest/{basename}/retrieve-file/{pk}/`: Retrieve a file
            from [pk] object.
        - `[DELETE] rest/{basename}/remove-file-field/{pk}/`: Remove a
            file from [pk] object.
        - `[DELETE] rest/{basename}/delete/{pk}/`: Remove an object
            from database.
        - `[POST] rest/{basename}/delete/`: Remove all object acording to a
            query dictonary.
        - `[POST] rest/{basename}/save/`: Create/Update an object.
        - `[GET] rest/{basename}/actions/`: List all avaiable actions for
            model_class
        - `[POST] rest/{basename}/actions/{action_name}/{pk}/`: Execute an
            action over an object of pk.
        - `[POST] rest/{basename}/actions/{action_name}/`: Execute an
            action associated with a classmethod or staticmethod (not
            associated with an object).
        - `[GET,POST] rest/{basename}/options/`: Get request will return
            information about fields of model_class. POST can be used to
            parcial fill of the object. This end-point is DEPRECTED.
        - `[GET] rest/{basename}/list-options/`: Return information that can
            be used to render list pages.
        - `[GET,POST] rest/{basename}/retrieve-options/`: GET Return
            information that can be used to render retrieve pages. POST will
            validate parcial object information.
        - `[POST] rest/{basename}/aggregate/`: Return results for aggregation
            operation (group by).

        Returns:
            Return a list of URLs associated with model_class with Pumpwood
            end-points.

        @private
        """
        self.validate_view(viewset)

        resp_list = []
        ##############
        # Setting URLs
        # List
        url_list = 'rest/{basename}/list/'
        resp_list.append(
            path(
                url_list.format(basename=basename),
                viewset.as_view({'post': 'list'}),
                name='rest__{basename}__list'.format(basename=basename)))

        # List without pagination
        url_list_witout_pag = 'rest/{basename}/list-without-pag/'
        resp_list.append(
            path(
                url_list_witout_pag.format(basename=basename),
                viewset.as_view({'post': 'list_without_pag'}),
                name='rest__{basename}__list_without_pag'.format(
                     basename=basename)))

        # retrieve
        url_retrieve = 'rest/{basename}/retrieve/<int:pk>/'
        resp_list.append(
            path(
                url_retrieve.format(basename=basename),
                viewset.as_view({'get': 'retrieve', 'delete': 'delete'}),
                name='rest__{basename}__retrieve'.format(basename=basename)))

        # retrieve file
        url_retrieve = 'rest/{basename}/retrieve-file/<int:pk>/'
        resp_list.append(
            path(url_retrieve.format(basename=basename),
                 viewset.as_view({'get': 'retrieve_file'}),
                 name='rest__{basename}__retrieve_file'.format(
                    basename=basename)))

        # retrieve file
        url_retrieve = 'rest/{basename}/remove-file-field/<int:pk>/'
        resp_list.append(
            path(
                url_retrieve.format(basename=basename),
                viewset.as_view({'delete': 'remove_file_field'}),
                name='rest__{basename}__remove_file_field'.format(
                    basename=basename)))

        # delete
        url_delete = 'rest/{basename}/delete/<int:pk>/'
        resp_list.append(
            path(
                url_delete.format(basename=basename),
                viewset.as_view({'delete': 'delete'}),
                name='rest__{basename}__delete'.format(basename=basename)))

        url_delete = 'rest/{basename}/delete/'
        resp_list.append(
            path(
                url_delete.format(basename=basename),
                viewset.as_view({'post': 'delete_many'}),
                name='rest__{basename}__delete_many'.format(
                    basename=basename)))
        # save
        url_save = 'rest/{basename}/save/'
        resp_list.append(
            path(
                url_save.format(basename=basename),
                viewset.as_view({'post': 'save', 'put': 'save'}),
                name='rest__{basename}__save'.format(basename=basename)))

        # actions list
        url_actions_list = 'rest/{basename}/actions/'
        resp_list.append(
            path(
                url_actions_list.format(basename=basename),
                viewset.as_view({'get': 'list_actions'}),
                name='rest__{basename}__actions_list'.format(
                    basename=basename)))

        # actions run with object
        url_act_obj = (
            'rest/{basename}/actions/<str:action_name>/<int:pk>/')
        resp_list.append(
            path(
                url_act_obj.format(basename=basename), viewset.as_view({
                    'post': 'execute_action'}),
                name='rest__{basename}__actions_run'.format(
                    basename=basename)))

        # actions run with object
        url_act_static = 'rest/{basename}/actions/<str:action_name>/'
        resp_list.append(
            path(
                url_act_static.format(basename=basename), viewset.as_view(
                    {'post': 'execute_action'}),
                name='rest__{basename}__actions_run'.format(
                    basename=basename)))

        # options
        url_options = 'rest/{basename}/options/'
        resp_list.append(
            path(
                url_options.format(basename=basename),
                viewset.as_view({
                    'get': 'search_options', 'post': 'fill_options'}),
                name='rest__{basename}__options'.format(basename=basename)))

        url_options = 'rest/{basename}/list-options/'
        resp_list.append(
            path(
                url_options.format(basename=basename),
                viewset.as_view({
                    'get': 'list_view_options'}),
                name='rest__{basename}__list_options'.format(
                    basename=basename)))

        url_options = 'rest/{basename}/retrieve-options/'
        resp_list.append(
            path(
                url_options.format(basename=basename),
                viewset.as_view({
                    'get': 'retrieve_view_options',
                    'post': 'fill_options_validation'}),
                name='rest__{basename}__retrieve_options'.format(
                    basename=basename)))

        url_options = 'rest/{basename}/aggregate/'
        resp_list.append(
            path(
                url_options.format(basename=basename),
                viewset.as_view({
                    'post': 'aggregate'}),
                name='rest__{basename}aggregate'.format(
                    basename=basename)))

        # Return all end-points mapped
        return resp_list

    def get_urls(self):
        ret = []
        for viewset, basename in self.registry:
            ret.extend(self.get_registry_pattern(viewset, basename))
        return ret


class PumpWoodDataBaseRouter(PumpWoodRouter):
    """
    Define a Router for PumpWoodDataBaseRestService views.

    Add some data routes to PumpWoodRouter.

    Patterns registered:
        - `[POST] rest/{basename}/pivot/`: Retrieve data according to
            query dictonary without deserializing using serializers (return
            the Pandas dataframe converted with to_dict([format])).
        - `[POST] rest/{basename}/bulk-save/`: Save many objects at same
            time, it can be used to upload large datasets.
    """

    def validate_view(self, viewset):
        if PumpWoodDataBaseRestService not in viewset.__bases__:
            msg = ("PumpWoodRouter applied over a view that isn't a "
                   "PumpWoodDataBaseRestService")
            raise ImproperlyConfigured(msg)

    def get_registry_pattern(self, viewset, basename):
        resp_list = super(PumpWoodDataBaseRouter, self).get_registry_pattern(
            viewset, basename)

        path_template = 'rest/{basename}/pivot/'
        resp_list.append(
            path(
                path_template.format(basename=basename),
                viewset.as_view({'post': 'pivot'}),
                name='rest__{basename}__pivot'.format(basename=basename)))

        path_template = 'rest/{basename}/bulk-save/'
        resp_list.append(
            path(
                path_template.format(basename=basename),
                viewset.as_view({'post': 'bulk_save'}),
                name='rest__{basename}__bulk_save'.format(basename=basename)))
        return resp_list
