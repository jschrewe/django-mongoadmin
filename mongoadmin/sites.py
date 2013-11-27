from django.contrib.admin import ModelAdmin
from django.db.models.base import ModelBase
from django.core.exceptions import ImproperlyConfigured
from django.conf import settings
from django.contrib.admin.sites import AdminSite, NotRegistered, AlreadyRegistered

from mongoengine.base import TopLevelDocumentMetaclass

from mongodbforms import init_document_options

from mongoadmin import DocumentAdmin

LOGIN_FORM_KEY = 'this_is_the_login_form'

class MongoAdminSite(AdminSite):
    """
    An AdminSite object encapsulates an instance of the Django admin application, ready
    to be hooked in to your URLconf. Models are registered with the AdminSite using the
    register() method, and the get_urls() method can then be used to access Django view
    functions that present a full admin interface for the collection of registered
    models.
    """
    def register(self, model_or_iterable, admin_class=None, **options):
        """
        Registers the given model(s) with the given admin class.

        The model(s) should be Model classes, not instances.

        If an admin class isn't given, it will use ModelAdmin (the default
        admin options). If keyword arguments are given -- e.g., list_display --
        they'll be applied as options to the admin class.

        If a model is already registered, this will raise AlreadyRegistered.

        If a model is abstract, this will raise ImproperlyConfigured.
        """
        if isinstance(model_or_iterable, ModelBase) and not admin_class:
            admin_class = ModelAdmin
            
        if isinstance(model_or_iterable, TopLevelDocumentMetaclass) and not admin_class:
            admin_class = DocumentAdmin

        # Don't import the humongous validation code unless required
        #if admin_class and settings.DEBUG:
        #    from mongoadmin.validation import validate
        #else:
        validate = lambda model, adminclass: None

        if isinstance(model_or_iterable, ModelBase) or \
                isinstance(model_or_iterable, TopLevelDocumentMetaclass):
            model_or_iterable = [model_or_iterable]

        for model in model_or_iterable:
            if isinstance(model, TopLevelDocumentMetaclass):
                init_document_options(model)
            
            if hasattr(model._meta, 'abstract') and model._meta.abstract:
                raise ImproperlyConfigured('The model %s is abstract, so it '
                      'cannot be registered with admin.' % model.__name__)

            if model in self._registry:
                raise AlreadyRegistered('The model %s is already registered' % model.__name__)

            # Ignore the registration if the model has been
            # swapped out.
            if model._meta.swapped:
                continue

            # If we got **options then dynamically construct a subclass of
            # admin_class with those **options.
            if options:
                # For reasons I don't quite understand, without a __module__
                # the created class appears to "live" in the wrong place,
                # which causes issues later on.
                options['__module__'] = __name__
                admin_class = type("%sAdmin" % model.__name__, (admin_class,), options)

            # Validate (which might be a no-op)
            validate(admin_class, model)

            # Instantiate the admin class to save in the registry
            self._registry[model] = admin_class(model, self)

    def unregister(self, model_or_iterable):
        """
        Unregisters the given model(s).

        If a model isn't already registered, this will raise NotRegistered.
        """
        if isinstance(model_or_iterable, ModelBase) or \
                isinstance(model_or_iterable, TopLevelDocumentMetaclass):
            model_or_iterable = [model_or_iterable]
        for model in model_or_iterable:
            if model not in self._registry:
                raise NotRegistered('The model %s is not registered' % model.__name__)
            del self._registry[model]


# This global object represents the default admin site, for the common case.
# You can instantiate AdminSite in your own code to create a custom admin site.
site = MongoAdminSite()
