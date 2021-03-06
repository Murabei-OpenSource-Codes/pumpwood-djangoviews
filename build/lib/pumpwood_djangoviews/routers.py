"""Define defult Routers for Pumpwood systems."""
import re
import os
from django.conf.urls import url
from django.core.exceptions import ImproperlyConfigured
from slugify import slugify
from rest_framework.routers import BaseRouter
from .views import PumpWoodRestService, PumpWoodDataBaseRestService
from .serve import serve_X_Accel_protected, serve_X_Accel_unprotected
from pumpwood_kong.kong_api import KongAPI


class PumpWoodRouter(BaseRouter):
    """
    Define a Router for PumpWoodRestService views.

    :raise ImproperlyConfigured: If a view different from
        PumpWoodRestService is used
    """

    def get_default_base_name(self, viewset):
        """."""
        return viewset.service_model.__name__

    def register(self, viewset):
        """
        Register view urls using the name of the models as path.

        Args:
            viewset: A view set from rest framework.
        """
        base_name = self.get_default_base_name(viewset)
        suffix = os.getenv('ENDPOINT_SUFFIX', '').lower()
        base_name = slugify(suffix + base_name)
        self.registry.append((viewset, base_name))

    def validate_view(self, viewset):
        """."""
        if PumpWoodRestService not in viewset.__bases__:
            raise ImproperlyConfigured(
                "PumpWoodRouter applied over a view that isn't a "
                "PumpWoodRestService")

    def get_registry_pattern(self, viewset, basename):
        """."""
        self.validate_view(viewset)

        resp_list = []
        ##############
        # Setting urls
        # List
        url_list = '^{basename}/list/$'
        resp_list.append(
            url(url_list.format(basename=basename),
                viewset.as_view({'post': 'list'}),
                name='rest__{basename}__list'.format(basename=basename)))

        # List without paginaiton
        url_list_witout_pag = '^{basename}/list-without-pag/$'
        resp_list.append(
            url(url_list_witout_pag.format(basename=basename),
                viewset.as_view({'post': 'list_without_pag'}),
                name='rest__{basename}__list_without_pag'.format(
                    basename=basename)))

        # retrive
        url_retrieve = '^{basename}/retrieve/(?P<pk>\d+)/$'
        resp_list.append(
            url(url_retrieve.format(basename=basename),
                viewset.as_view({'get': 'retrieve', 'delete': 'delete'}),
                name='rest__{basename}__retrieve'.format(basename=basename)))

        # retrive file
        url_retrieve = '^{basename}/retrieve-file/(?P<pk>\d+)/$'
        resp_list.append(
            url(url_retrieve.format(basename=basename),
                viewset.as_view({'get': 'retrieve_file'}),
                name='rest__{basename}__retrieve_file'.format(
                    basename=basename)))

        # retrive file
        url_retrieve = '^{basename}/remove-file-field/(?P<pk>\d+)/$'
        resp_list.append(
            url(url_retrieve.format(basename=basename),
                viewset.as_view({'delete': 'remove_file_field'}),
                name='rest__{basename}__remove_file_field'.format(
                    basename=basename)))

        # delete
        url_delete = '^{basename}/delete/(?P<pk>\d+)/$'
        resp_list.append(
            url(url_delete.format(basename=basename),
                viewset.as_view({'delete': 'delete'}),
                name='rest__{basename}__delete'.format(basename=basename)))

        url_delete = '^{basename}/delete/$'
        resp_list.append(
            url(url_delete.format(basename=basename),
                viewset.as_view({'post': 'delete_many'}),
                name='rest__{basename}__delete_many'.format(
                    basename=basename)))
        # save
        url_save = '^{basename}/save/$'
        resp_list.append(
            url(url_save.format(basename=basename),
                viewset.as_view({'post': 'save', 'put': 'save'}),
                name='rest__{basename}__save'.format(basename=basename)))

        # actions list
        url_actions_list = '^{basename}/actions/$'
        resp_list.append(
            url(url_actions_list.format(basename=basename),
                viewset.as_view({'get': 'list_actions'}),
                name='rest__{basename}__actions_list'.format(
                    basename=basename)))

        # actions run with object
        url_act_obj = '^{basename}/actions/(?P<action_name>\w+)/(?P<pk>\d+)/$'
        resp_list.append(
            url(
                url_act_obj.format(basename=basename), viewset.as_view({
                    'post': 'execute_action'}),
                name='rest__{basename}__actions_run'.format(
                    basename=basename)))

        # actions run with object
        url_act_static = '^{basename}/actions/(?P<action_name>\w+)/$'
        resp_list.append(
            url(
                url_act_static.format(basename=basename), viewset.as_view(
                    {'post': 'execute_action'}),
                name='rest__{basename}__actions_run'.format(
                    basename=basename)))

        # options
        url_options = '^{basename}/options/$'
        resp_list.append(
            url(url_options.format(basename=basename),
                viewset.as_view({
                    'get': 'search_options', 'post': 'fill_options'}),
                name='rest__{basename}__options'.format(basename=basename)))
        ##############
        return resp_list

    def get_urls(self):
        ret = []
        for viewset, basename in self.registry:
            ret.extend(self.get_registry_pattern(viewset, basename))
        return ret


class PumpWoodDataBaseRouter(PumpWoodRouter):
    """
    Define a Router for PumpWoodDataBaseRestService views

    :raise ImproperlyConfigured: If a view different from
        PumpWoodDataBaseRestService is used
    """
    def validate_view(self, viewset):
        if PumpWoodDataBaseRestService not in viewset.__bases__:
            msg = ("PumpWoodRouter applied over a view that isn't a "
                   "PumpWoodDataBaseRestService")
            raise ImproperlyConfigured(msg)

    def get_registry_pattern(self, viewset, basename):
        resp_list = super(PumpWoodDataBaseRouter, self).get_registry_pattern(
            viewset, basename)

        resp_list.append(
            url('^{basename}/pivot/$'.format(basename=basename),
                viewset.as_view({'post': 'pivot'}),
                name='rest__{basename}__pivot'.format(basename=basename)))

        resp_list.append(
            url('^{basename}/bulk-save/$'.format(basename=basename),
                viewset.as_view({'post': 'bulk_save'}),
                name='rest__{basename}__bulk_save'.format(basename=basename)))
        return resp_list


def url_serve_X_Accel_protected(prefix):
    return [
        url('^%s(?P<path>.*)$' % re.escape(prefix.lstrip('/')),
            view=serve_X_Accel_protected)]


def url_serve_X_Accel_unprotected(prefix):
    return [
        url('^%s(?P<path>.*)$' % re.escape(prefix.lstrip('/')),
            view=serve_X_Accel_unprotected)]
