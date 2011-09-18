from django.template import Library

from django.contrib.admin.templatetags.admin_list import (result_hidden_fields, ResultList, items_for_result,
                                                          _boolean_icon)
from django.contrib.admin.views.main import ORDER_VAR, ORDER_TYPE_VAR, EMPTY_CHANGELIST_VALUE
from django.contrib.admin.util import lookup_field
from django.core.exceptions import ObjectDoesNotExist
from django.utils.safestring import mark_safe
from django.db.models.fields import FieldDoesNotExist
from django.utils.encoding import smart_unicode, force_unicode
from django.utils.html import escape, conditional_escape

from mongoengine import fields

from mongodbforms.documentoptions import AdminOptions

from mongoadmin.util import label_for_field
from mongoadmin.util import patch_document, display_for_field

register = Library()

def result_headers(cl):
    """
    Generates the list column headers.
    """
    lookup_opts = cl.lookup_opts

    for i, field_name in enumerate(cl.list_display):
        header, attr = label_for_field(field_name, cl.model,
            model_admin = cl.model_admin,
            return_attr = True
        )
        if attr:
            # if the field is the action checkbox: no sorting and special class
            if field_name == 'action_checkbox':
                yield {
                    "text": header,
                    "class_attrib": mark_safe(' class="action-checkbox-column"')
                } 
                continue

            # It is a non-field, but perhaps one that is sortable
            admin_order_field = getattr(attr, "admin_order_field", None)
            if not admin_order_field:
                yield {"text": header}
                continue


            # So this _is_ a sortable non-field.  Go to the yield
            # after the else clause.
        else:
            admin_order_field = None

        th_classes = []
        new_order_type = 'asc'
        if field_name == cl.order_field or admin_order_field == cl.order_field:
            th_classes.append('sorted %sending' % cl.order_type.lower())
            new_order_type = {'asc': 'desc', 'desc': 'asc'}[cl.order_type.lower()]

        yield {   
            "text": header,
            "sortable": True,
            "url": cl.get_query_string({ORDER_VAR: i, ORDER_TYPE_VAR: new_order_type}),
            "class_attrib": mark_safe(th_classes and ' class="%s"' % ' '.join(th_classes) or '')
        }

def items_for_result(cl, result, form):
    """
    Generates the actual list of data.
    """
    first = True 
    pk = cl.lookup_opts.pk.attname
    for field_name in cl.list_display:
        row_class = ''
        try:
            f, attr, value = lookup_field(field_name, result, cl.model_admin)
            print field_name
            print type(f)
        except (AttributeError, ObjectDoesNotExist):
            result_repr = EMPTY_CHANGELIST_VALUE
        else:
            if f is None:
                if field_name == u'action_checkbox':
                    row_class = ' class="action-checkbox"'
                allow_tags = getattr(attr, 'allow_tags', False)
                boolean = getattr(attr, 'boolean', False)
                if boolean:
                    allow_tags = True
                    result_repr = _boolean_icon(value)
                else:
                    result_repr = smart_unicode(value)
                # Strip HTML tags in the resulting text, except if the
                # function has an "allow_tags" attribute set to True.
                if not allow_tags:
                    result_repr = escape(result_repr)
                else:
                    result_repr = mark_safe(result_repr)
            else:
#                if isinstance(f.rel, models.ManyToOneRel):
#                    field_val = getattr(result, f.name)
#                    if field_val is None:
#                        result_repr = EMPTY_CHANGELIST_VALUE
#                    else:
#                        result_repr = escape(field_val)
#                else:
                if not hasattr(f, 'flatchoices'):
                    f.flatchoices = None
                result_repr = display_for_field(value, f)
                if isinstance(f, fields.DateTimeField):
                    row_class = ' class="nowrap"'
        if force_unicode(result_repr) == '':
            result_repr = mark_safe('&nbsp;')
        # If list_display_links not defined, add the link tag to the first field
        if (first and not cl.list_display_links) or field_name in cl.list_display_links:
            table_tag = {True:'th', False:'td'}[first]
            first = False
            url = cl.url_for_result(result)
            # Convert the pk to something that can be used in Javascript.
            # Problem cases are long ints (23L) and non-ASCII strings.
            if cl.to_field:
                attr = str(cl.to_field)
            else:
                attr = pk
            value = result.serializable_value(attr)
            result_id = repr(force_unicode(value))[1:]
            yield mark_safe(u'<%s%s><a href="%s"%s>%s</a></%s>' % \
                (table_tag, row_class, url, (cl.is_popup and ' onclick="opener.dismissRelatedLookupPopup(window, %s); return false;"' % result_id or ''), conditional_escape(result_repr), table_tag))
        else:
            # By default the fields come from ModelAdmin.list_editable, but if we pull
            # the fields out of the form instead of list_editable custom admins
            # can provide fields on a per request basis
            if (form and field_name in form.fields and not (
                    field_name == cl.model._meta.pk.name and
                        form[cl.model._meta.pk.name].is_hidden)):
                bf = form[field_name]
                result_repr = mark_safe(force_unicode(bf.errors) + force_unicode(bf))
            else:
                result_repr = conditional_escape(result_repr)
            yield mark_safe(u'<td%s>%s</td>' % (row_class, result_repr))
    if form and not form[cl.model._meta.pk.name].is_hidden:
        yield mark_safe(u'<td>%s</td>' % force_unicode(form[cl.model._meta.pk.name]))

def serializable_value(self, field_name):
    """
    Returns the value of the field name for this instance. If the field is
    a foreign key, returns the id value, instead of the object. If there's
    no Field object with this name on the model, the model attribute's
    value is returned directly.

    Used to serialize a field's value (in the serializer, or form output,
    for example). Normally, you would just access the attribute directly
    and not use this method.
    """
    if not hasattr(self, '_admin_opts'):
        self._admin_opts = AdminOptions(self)
    try:
        field = self._admin_opts.get_field_by_name(field_name)[0]
    except FieldDoesNotExist:
        return getattr(self, field_name)
    return getattr(self, field.name) 

def results(cl):
    if cl.formset:
        for res, form in zip(cl.result_list, cl.formset.forms):
            patch_document(serializable_value, res)
            yield ResultList(form, items_for_result(cl, res, form))
    else:
        for res in cl.result_list:
            patch_document(serializable_value, res)
            if not hasattr(res, '_admin_opts'):
                res._admin_opts = AdminOptions(res)
            res._meta = res._admin_opts
            yield ResultList(None, items_for_result(cl, res, None))


def document_result_list(cl):
    """
    Displays the headers and data list together
    """
    return {'cl': cl,
            'result_hidden_fields': list(result_hidden_fields(cl)),
            'result_headers': list(result_headers(cl)),
            'results': list(results(cl))}

result_list = register.inclusion_tag("admin/change_list_results.html")(document_result_list)
