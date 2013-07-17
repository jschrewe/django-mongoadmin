from django.utils.encoding import smart_str
try:
    from django.utils.encoding import force_text as force_unicode
except ImportError:
    from django.utils.encoding import force_unicode
try:
    from django.utils.encoding import smart_text as smart_unicode
except ImportError:
    try:
        from django.utils.encoding import smart_unicode
    except ImportError:
        from django.forms.util import smart_unicode
    
from django.forms.forms import pretty_name
from django.db.models.fields import FieldDoesNotExist
from django.utils import formats
from django.db.models.options import get_verbose_name

from mongoengine import fields

from mongodbforms.documentoptions import DocumentMetaWrapper
from mongodbforms.util import init_document_options
import collections

class RelationWrapper(object):
    """
    Wraps a document referenced from a ReferenceField with an Interface similiar to
    django's ForeignKeyField.rel 
    """
    def __init__(self, document):
        self.to = init_document_options(document)
        
def is_django_user_model(user):
    """
    Checks if a user model is compatible with Django's
    recent changes. Django requires User models to have 
    an int pk, so we check here if it has (mongoengine hasn't)
    """
    try:
        int(user.pk)
    except (ValueError, TypeError):
        return False
    return True

def label_for_field(name, model, model_admin=None, return_attr=False):
    attr = None
    model._meta = init_document_options(document)
    try:
        field = model._meta.get_field_by_name(name)[0]
        label = field.name.replace('_', ' ')
    except FieldDoesNotExist: 
        if name == "__unicode__":
            label = force_unicode(model._meta.verbose_name)
        elif name == "__str__":
            label = smart_str(model._meta.verbose_name)
        else:
            if isinstance(name, collections.Callable):
                attr = name
            elif model_admin is not None and hasattr(model_admin, name):
                attr = getattr(model_admin, name)
            elif hasattr(model, name):
                attr = getattr(model, name)
            else:
                message = "Unable to lookup '%s' on %s" % (name, model._meta.object_name)
                if model_admin:
                    message += " or %s" % (model_admin.__class__.__name__,)
                raise AttributeError(message)


            if hasattr(attr, "short_description"):
                label = attr.short_description
            elif isinstance(attr, collections.Callable):
                if attr.__name__ == "<lambda>":
                    label = "--"
                else:
                    label = pretty_name(attr.__name__)
            else:
                label = pretty_name(name)
    if return_attr:
        return (label, attr)
    else:
        return label

def display_for_field(value, field):
    from django.contrib.admin.templatetags.admin_list import _boolean_icon
    from django.contrib.admin.views.main import EMPTY_CHANGELIST_VALUE   

    if field.flatchoices:
        return dict(field.flatchoices).get(value, EMPTY_CHANGELIST_VALUE)
    # NullBooleanField needs special-case null-handling, so it comes
    # before the general null test.
    elif isinstance(field, fields.BooleanField):
        return _boolean_icon(value)
    elif value is None:
        return EMPTY_CHANGELIST_VALUE
    elif isinstance(field, fields.DateTimeField):
        return formats.localize(value)
    elif isinstance(field, fields.DecimalField):
        return formats.number_format(value, field.decimal_places)
    elif isinstance(field, fields.FloatField):
        return formats.number_format(value)
    else:
        return smart_unicode(value)
