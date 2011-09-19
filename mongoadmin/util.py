import new

from django.utils.encoding import force_unicode, smart_unicode, smart_str
from django.forms.forms import pretty_name
from django.db.models.fields import FieldDoesNotExist
from django.utils import formats
from django.db.models.options import get_verbose_name

from mongoengine import fields

from mongodbforms.documentoptions import AdminOptions

def patch_document(function, instance):
    setattr(instance, function.__name__, new.instancemethod(function, instance, instance.__class__))

def label_for_field(name, model, model_admin=None, return_attr=False):
    attr = None
    model._admin_opts = AdminOptions(model)
    try:
        field = model._admin_opts.get_field_by_name(name)[0]
    #if isinstance(field, RelatedObject):
    #    label = field.opts.verbose_name
    #else:
        label = field.name.replace('_', ' ')
    except FieldDoesNotExist: 
        if name == "__unicode__":
            label = force_unicode(model._admin_opts.verbose_name)
        elif name == "__str__":
            label = smart_str(model._admin_opts.verbose_name)
        else:
            if callable(name):
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
            elif callable(attr):
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
