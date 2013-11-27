from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.db.models.fields import FieldDoesNotExist
from django.contrib.admin.util import get_fields_from_path, NotRelationField
from django.contrib.admin.validation import (check_type, check_isseq, check_isdict,
                                             get_field, BaseValidator)

from mongoengine import ListField, ReferenceField, DateTimeField

from mongodbforms import BaseDocumentForm, BaseDocumentFormSet

"""
Does basic ModelAdmin option validation. Calls custom validation
classmethod in the end if it is provided in cls. The signature of the
custom validation classmethod should be: def validate(cls, model).
"""

__all__ = ['MongoBaseValidator', 'MongoInlineValidator']


class MongoBaseValidator(BaseValidator):
    def validate(self, cls, model):
        for m in dir(self):
            if m.startswith('validate_'):
                getattr(self, m)(cls, model)

    def check_field_spec(self, cls, model, flds, label):
        """
        Validate the fields specification in `flds` from a ModelAdmin subclass
        `cls` for the `model` model. Use `label` for reporting problems to the user.

        The fields specification can be a ``fields`` option or a ``fields``
        sub-option from a ``fieldsets`` option component.
        """
        for fields in flds:
            # The entry in fields might be a tuple. If it is a standalone
            # field, make it into a tuple to make processing easier.
            if type(fields) != tuple:
                fields = (fields,)
            for field in fields:
                if field in cls.readonly_fields:
                    # Stuff can be put in fields that isn't actually a
                    # model field if it's in readonly_fields,
                    # readonly_fields will handle the validation of such
                    # things.
                    continue
                try:
                    model._meta.get_field(field)
                except models.FieldDoesNotExist:
                    # If we can't find a field on the model that matches, it could be an
                    # extra field on the form; nothing to check so move on to the next field.
                    continue

    def validate_raw_id_fields(self, cls, model):
        " Validate that raw_id_fields only contains field names that are listed on the model. "
        if hasattr(cls, 'raw_id_fields'):
            check_isseq(cls, 'raw_id_fields', cls.raw_id_fields)
            for idx, field in enumerate(cls.raw_id_fields):
                f = get_field(cls, model, 'raw_id_fields', field)
                if not is_relation(f):
                    raise ImproperlyConfigured("'%s.raw_id_fields[%d]', '%s' must "
                            "be either a ForeignKey or ManyToManyField."
                            % (cls.__name__, idx, field))

    def validate_form(self, cls, model):
        " Validate that form subclasses BaseModelForm. "
        if hasattr(cls, 'form') and not issubclass(cls.form, BaseDocumentForm):
            raise ImproperlyConfigured("%s.form does not inherit from "
                    "BaseModelForm." % cls.__name__)

    def validate_filter_vertical(self, cls, model):
        " Validate that filter_vertical is a sequence of field names. "
        if hasattr(cls, 'filter_vertical'):
            check_isseq(cls, 'filter_vertical', cls.filter_vertical)
            for idx, field in enumerate(cls.filter_vertical):
                f = get_field(cls, model, 'filter_vertical', field)
                if not is_multi_relation(f):
                    raise ImproperlyConfigured("'%s.filter_vertical[%d]' must be "
                        "a ManyToManyField." % (cls.__name__, idx))

    def validate_filter_horizontal(self, cls, model):
        " Validate that filter_horizontal is a sequence of field names. "
        if hasattr(cls, 'filter_horizontal'):
            check_isseq(cls, 'filter_horizontal', cls.filter_horizontal)
            for idx, field in enumerate(cls.filter_horizontal):
                f = get_field(cls, model, 'filter_horizontal', field)
                if not is_multi_relation(f):
                    raise ImproperlyConfigured("'%s.filter_horizontal[%d]' must be "
                        "a ManyToManyField." % (cls.__name__, idx))

    def validate_radio_fields(self, cls, model):
        " Validate that radio_fields is a dictionary of choice or foreign key fields. "
        from django.contrib.admin.options import HORIZONTAL, VERTICAL
        if hasattr(cls, 'radio_fields'):
            check_isdict(cls, 'radio_fields', cls.radio_fields)
            for field, val in cls.radio_fields.items():
                f = get_field(cls, model, 'radio_fields', field)
                if not (isinstance(f, ReferenceField) or f.choices):
                    raise ImproperlyConfigured("'%s.radio_fields['%s']' "
                            "is neither an instance of ForeignKey nor does "
                            "have choices set." % (cls.__name__, field))
                if not val in (HORIZONTAL, VERTICAL):
                    raise ImproperlyConfigured("'%s.radio_fields['%s']' "
                            "is neither admin.HORIZONTAL nor admin.VERTICAL."
                            % (cls.__name__, field))

    def validate_prepopulated_fields(self, cls, model):
        " Validate that prepopulated_fields if a dictionary  containing allowed field types. "
        # prepopulated_fields
        if hasattr(cls, 'prepopulated_fields'):
            check_isdict(cls, 'prepopulated_fields', cls.prepopulated_fields)
            for field, val in cls.prepopulated_fields.items():
                f = get_field(cls, model, 'prepopulated_fields', field)
                if isinstance(f, DateTimeField) or is_relation(f):
                    raise ImproperlyConfigured("'%s.prepopulated_fields['%s']' "
                            "is either a DateTimeField, ForeignKey or "
                            "ManyToManyField. This isn't allowed."
                            % (cls.__name__, field))
                check_isseq(cls, "prepopulated_fields['%s']" % field, val)
                for idx, f in enumerate(val):
                    get_field(cls, model, "prepopulated_fields['%s'][%d]" % (field, idx), f)


class ModelAdminValidator(BaseValidator):
    def validate_save_as(self, cls, model):
        " Validate save_as is a boolean. "
        check_type(cls, 'save_as', bool)

    def validate_save_on_top(self, cls, model):
        " Validate save_on_top is a boolean. "
        check_type(cls, 'save_on_top', bool)

    def validate_inlines(self, cls, model):
        " Validate inline model admin classes. "
        from django.contrib.admin.options import BaseModelAdmin
        if hasattr(cls, 'inlines'):
            check_isseq(cls, 'inlines', cls.inlines)
            for idx, inline in enumerate(cls.inlines):
                if not issubclass(inline, BaseModelAdmin):
                    raise ImproperlyConfigured("'%s.inlines[%d]' does not inherit "
                            "from BaseModelAdmin." % (cls.__name__, idx))
                if not inline.model:
                    raise ImproperlyConfigured("'model' is a required attribute "
                            "of '%s.inlines[%d]'." % (cls.__name__, idx))
                if not issubclass(inline.model, models.Model):
                    raise ImproperlyConfigured("'%s.inlines[%d].model' does not "
                            "inherit from models.Model." % (cls.__name__, idx))
                inline.validate(inline.model)
                self.check_inline(inline, model)

    def check_inline(self, cls, parent_model):
        " Validate inline class's fk field is not excluded. "
        pass
        #fk = _get_foreign_key(parent_model, cls.model, fk_name=cls.fk_name, can_fail=True)
        #if hasattr(cls, 'exclude') and cls.exclude:
        #    if fk and fk.name in cls.exclude:
        #        raise ImproperlyConfigured("%s cannot exclude the field "
        #                "'%s' - this is the foreign key to the parent model "
        #                "%s.%s." % (cls.__name__, fk.name, parent_model._meta.app_label, parent_model.__name__))

    def validate_list_display(self, cls, model):
        " Validate that list_display only contains fields or usable attributes. "
        if hasattr(cls, 'list_display'):
            check_isseq(cls, 'list_display', cls.list_display)
            for idx, field in enumerate(cls.list_display):
                if not callable(field):
                    if not hasattr(cls, field):
                        if not hasattr(model, field):
                            try:
                                model._meta.get_field(field)
                            except models.FieldDoesNotExist:
                                raise ImproperlyConfigured("%s.list_display[%d], %r is not a callable or an attribute of %r or found in the model %r."
                                    % (cls.__name__, idx, field, cls.__name__, model._meta.object_name))
                        else:
                            # getattr(model, field) could be an X_RelatedObjectsDescriptor
                            f = fetch_attr(cls, model, "list_display[%d]" % idx, field)
                            if is_multi_relation(f):
                                raise ImproperlyConfigured("'%s.list_display[%d]', '%s' is a ManyToManyField which is not supported."
                                    % (cls.__name__, idx, field))

    def validate_list_display_links(self, cls, model):
        " Validate that list_display_links either is None or a unique subset of list_display."
        if hasattr(cls, 'list_display_links'):
            if cls.list_display_links is None:
                return
            check_isseq(cls, 'list_display_links', cls.list_display_links)
            for idx, field in enumerate(cls.list_display_links):
                if field not in cls.list_display:
                    raise ImproperlyConfigured("'%s.list_display_links[%d]' "
                            "refers to '%s' which is not defined in 'list_display'."
                            % (cls.__name__, idx, field))

    def validate_list_filter(self, cls, model):
        """
        Validate that list_filter is a sequence of one of three options:
            1: 'field' - a basic field filter, possibly w/ relationships (eg, 'field__rel')
            2: ('field', SomeFieldListFilter) - a field-based list filter class
            3: SomeListFilter - a non-field list filter class
        """
        from django.contrib.admin import ListFilter, FieldListFilter
        if hasattr(cls, 'list_filter'):
            check_isseq(cls, 'list_filter', cls.list_filter)
            for idx, item in enumerate(cls.list_filter):
                if callable(item) and not isinstance(item, models.Field):
                    # If item is option 3, it should be a ListFilter...
                    if not issubclass(item, ListFilter):
                        raise ImproperlyConfigured("'%s.list_filter[%d]' is '%s'"
                                " which is not a descendant of ListFilter."
                                % (cls.__name__, idx, item.__name__))
                    # ...  but not a FieldListFilter.
                    if issubclass(item, FieldListFilter):
                        raise ImproperlyConfigured("'%s.list_filter[%d]' is '%s'"
                                " which is of type FieldListFilter but is not"
                                " associated with a field name."
                                % (cls.__name__, idx, item.__name__))
                else:
                    if isinstance(item, (tuple, list)):
                        # item is option #2
                        field, list_filter_class = item
                        if not issubclass(list_filter_class, FieldListFilter):
                            raise ImproperlyConfigured("'%s.list_filter[%d][1]'"
                                " is '%s' which is not of type FieldListFilter."
                                % (cls.__name__, idx, list_filter_class.__name__))
                    else:
                        # item is option #1
                        field = item
                    # Validate the field string
                    try:
                        get_fields_from_path(model, field)
                    except (NotRelationField, FieldDoesNotExist):
                        raise ImproperlyConfigured("'%s.list_filter[%d]' refers to '%s'"
                                " which does not refer to a Field."
                                % (cls.__name__, idx, field))

    def validate_list_select_related(self, cls, model):
        " Validate that list_select_related is a boolean, a list or a tuple. "
        list_select_related = getattr(cls, 'list_select_related', None)
        if list_select_related:
            types = (bool, tuple, list)
            if not isinstance(list_select_related, types):
                raise ImproperlyConfigured("'%s.list_select_related' should be "
                                           "either a bool, a tuple or a list" %
                                           cls.__name__)

    def validate_list_per_page(self, cls, model):
        " Validate that list_per_page is an integer. "
        check_type(cls, 'list_per_page', int)

    def validate_list_max_show_all(self, cls, model):
        " Validate that list_max_show_all is an integer. "
        check_type(cls, 'list_max_show_all', int)

    def validate_list_editable(self, cls, model):
        """
        Validate that list_editable is a sequence of editable fields from
        list_display without first element.
        """
        if hasattr(cls, 'list_editable') and cls.list_editable:
            check_isseq(cls, 'list_editable', cls.list_editable)
            for idx, field_name in enumerate(cls.list_editable):
                try:
                    field = model._meta.get_field_by_name(field_name)[0]
                except models.FieldDoesNotExist:
                    raise ImproperlyConfigured("'%s.list_editable[%d]' refers to a "
                        "field, '%s', not defined on %s.%s."
                        % (cls.__name__, idx, field_name, model._meta.app_label, model.__name__))
                if field_name not in cls.list_display:
                    raise ImproperlyConfigured("'%s.list_editable[%d]' refers to "
                        "'%s' which is not defined in 'list_display'."
                        % (cls.__name__, idx, field_name))
                if cls.list_display_links is not None:
                    if field_name in cls.list_display_links:
                        raise ImproperlyConfigured("'%s' cannot be in both '%s.list_editable'"
                            " and '%s.list_display_links'"
                            % (field_name, cls.__name__, cls.__name__))
                    if not cls.list_display_links and cls.list_display[0] in cls.list_editable:
                        raise ImproperlyConfigured("'%s.list_editable[%d]' refers to"
                            " the first field in list_display, '%s', which can't be"
                            " used unless list_display_links is set."
                            % (cls.__name__, idx, cls.list_display[0]))
                if not field.editable:
                    raise ImproperlyConfigured("'%s.list_editable[%d]' refers to a "
                        "field, '%s', which isn't editable through the admin."
                        % (cls.__name__, idx, field_name))

    def validate_search_fields(self, cls, model):
        " Validate search_fields is a sequence. "
        if hasattr(cls, 'search_fields'):
            check_isseq(cls, 'search_fields', cls.search_fields)

    def validate_date_hierarchy(self, cls, model):
        " Validate that date_hierarchy refers to DateField or DateTimeField. "
        if cls.date_hierarchy:
            f = get_field(cls, model, 'date_hierarchy', cls.date_hierarchy)
            if not isinstance(f, (models.DateField, models.DateTimeField)):
                raise ImproperlyConfigured("'%s.date_hierarchy is "
                        "neither an instance of DateField nor DateTimeField."
                        % cls.__name__)


class MongoInlineValidator(MongoBaseValidator):
    def validate_fk_name(self, cls, model):
        " Validate that fk_name refers to a ForeignKey. "
        if cls.fk_name:  # default value is None
            f = get_field(cls, model, 'fk_name', cls.fk_name)
            if not isinstance(f, ReferenceField):
                raise ImproperlyConfigured("'%s.fk_name is not an instance of "
                        "models.ForeignKey." % cls.__name__)

    def validate_extra(self, cls, model):
        " Validate that extra is an integer. "
        check_type(cls, 'extra', int)

    def validate_max_num(self, cls, model):
        " Validate that max_num is an integer. "
        check_type(cls, 'max_num', int)

    def validate_formset(self, cls, model):
        " Validate formset is a subclass of BaseModelFormSet. "
        if hasattr(cls, 'formset') and not issubclass(cls.formset, BaseDocumentFormSet):
            raise ImproperlyConfigured("'%s.formset' does not inherit from "
                    "BaseModelFormSet." % cls.__name__)


def is_relation(field):
    if isinstance(field, ReferenceField) or is_multi_relation(field):
        return True
    return False

    
def is_multi_relation(field):
    if isinstance(field, ListField) and isinstance(field.field, ReferenceField):
        return True
    return False


def fetch_attr(cls, model, label, field):
    try:
        return model._meta.get_field(field)
    except models.FieldDoesNotExist:
        pass
    try:
        return getattr(model, field)
    except AttributeError:
        raise ImproperlyConfigured("'%s.%s' refers to '%s' that is neither a field, method or property of model '%s.%s'."
            % (cls.__name__, label, field, model._meta.app_label, model.__name__))