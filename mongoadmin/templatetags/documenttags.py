from django.template import Library

from django.contrib.admin.templatetags.admin_list import result_hidden_fields, ResultList, items_for_result
from django.contrib.admin.views.main import ORDER_VAR, ORDER_TYPE_VAR
from django.utils.safestring import mark_safe
from django.db.models.fields import FieldDoesNotExist

from mongodbforms.documentoptions import AdminOptions

from mongoadmin.util import label_for_field
from mongoadmin.util import patch_document

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
