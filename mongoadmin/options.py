import collections
from functools import partial

from django import forms
from django.forms.models import modelform_defines_fields
from django.contrib.admin.options import ModelAdmin, InlineModelAdmin, get_ul_class
from django.contrib.admin import widgets
from django.contrib.admin.util import flatten_fieldsets
from django.core.exceptions import FieldError, ValidationError
from django.forms.formsets import DELETION_FIELD_NAME
from django.utils.translation import ugettext as _
from django.contrib.admin.util import NestedObjects
from django.utils.text import get_text_list

from mongoengine.fields import (DateTimeField, URLField, IntField, ListField, EmbeddedDocumentField,
                                ReferenceField, StringField, FileField, ImageField)

from mongodbforms.documents import documentform_factory, embeddedformset_factory, DocumentForm, EmbeddedDocumentFormSet, EmbeddedDocumentForm
from mongodbforms.util import load_field_generator, init_document_options

from mongoadmin.util import RelationWrapper, is_django_user_model
from mongoadmin.widgets import ReferenceRawIdWidget, MultiReferenceRawIdWidget

# Defaults for formfield_overrides. ModelAdmin subclasses can change this
# by adding to ModelAdmin.formfield_overrides.
FORMFIELD_FOR_DBFIELD_DEFAULTS = {
    DateTimeField: {
        'form_class': forms.SplitDateTimeField,
        'widget': widgets.AdminSplitDateTime
    },
    URLField:       {'widget': widgets.AdminURLFieldWidget},
    IntField:       {'widget': widgets.AdminIntegerFieldWidget},
    ImageField:     {'widget': widgets.AdminFileWidget},
    FileField:      {'widget': widgets.AdminFileWidget},
}

_fieldgenerator = load_field_generator()()


def formfield(field, form_class=None, **kwargs):
    """
    Returns a django.forms.Field instance for this database Field.
    """
    defaults = {'required': field.required}
    if field.default is not None:
        if isinstance(field.default, collections.Callable):
            defaults['initial'] = field.default()
            defaults['show_hidden_initial'] = True
        else:
            defaults['initial'] = field.default

    if field.choices is not None:
        # Many of the subclass-specific formfield arguments (min_value,
        # max_value) don't apply for choice fields, so be sure to only pass
        # the values that TypedChoiceField will understand.
        for k in list(kwargs.keys()):
            if k not in ('coerce', 'empty_value', 'choices', 'required',
                         'widget', 'label', 'initial', 'help_text',
                         'error_messages', 'show_hidden_initial'):
                del kwargs[k]

    defaults.update(kwargs)

    if form_class is not None:
        return form_class(**defaults)
    return _fieldgenerator.generate(field, **defaults)


class MongoFormFieldMixin(object):

    def formfield_for_dbfield(self, db_field, **kwargs):
        """
        Hook for specifying the form Field instance for a given database Field
        instance.

        If kwargs are given, they're passed to the form Field's constructor.
        """
        request = kwargs.pop("request", None)

        # If the field specifies choices, we don't need to look for special
        # admin widgets - we just need to use a select widget of some kind.
        if db_field.choices is not None:
            return self.formfield_for_choice_field(db_field, request, **kwargs)

        if isinstance(db_field, ListField) and isinstance(db_field.field, ReferenceField):
            return self.formfield_for_reference_listfield(db_field, request, **kwargs)

        # handle RelatedFields
        if isinstance(db_field, ReferenceField):
            # For non-raw_id fields, wrap the widget with a wrapper that adds
            # extra HTML -- the "add other" interface -- to the end of the
            # rendered output. formfield can be None if it came from a
            # OneToOneField with parent_link=True or a M2M intermediary.
            form_field = self._get_formfield(db_field, **kwargs)
            if db_field.name not in self.raw_id_fields:
                related_modeladmin = self.admin_site._registry.get(
                    db_field.document_type)
                can_add_related = bool(related_modeladmin and
                                       related_modeladmin.has_add_permission(request))
                form_field.widget = widgets.RelatedFieldWidgetWrapper(
                    form_field.widget, RelationWrapper(
                        db_field.document_type), self.admin_site,
                    can_add_related=can_add_related)
                return form_field
            elif db_field.name in self.raw_id_fields:
                kwargs['widget'] = ReferenceRawIdWidget(
                    db_field.rel, self.admin_site)
                return self._get_formfield(db_field, **kwargs)

        if isinstance(db_field, StringField):
            if db_field.max_length is None:
                kwargs = dict(
                    {'widget': widgets.AdminTextareaWidget}, **kwargs)
            else:
                kwargs = dict(
                    {'widget': widgets.AdminTextInputWidget}, **kwargs)
            return self._get_formfield(db_field, **kwargs)

        # For any other type of field, just call its formfield() method.
        return self._get_formfield(db_field, **kwargs)

    def _get_formfield(self, db_field, **kwargs):
        """Return overridden formfield if exists, otherwise default formfield"""
        # If we've got overrides for the formfield defined, use 'em. **kwargs
        # passed to formfield_for_dbfield override the defaults.
        for klass in db_field.__class__.mro():
            if klass in self.formfield_overrides:
                kwargs.update(self.formfield_overrides[klass])
                break
        return formfield(db_field, **kwargs)

    def formfield_for_choice_field(self, db_field, request=None, **kwargs):
        """
        Get a form Field for a database Field that has declared choices.
        """
        # If the field is named as a radio_field, use a RadioSelect
        if db_field.name in self.radio_fields:
            # Avoid stomping on custom widget/choices arguments.
            if 'widget' not in kwargs:
                kwargs['widget'] = widgets.AdminRadioSelect(attrs={
                    'class': get_ul_class(self.radio_fields[db_field.name]),
                })
            if 'choices' not in kwargs:
                kwargs['choices'] = db_field.get_choices(
                    include_blank=db_field.blank,
                    blank_choice=[('', _('None'))]
                )
        return formfield(db_field, **kwargs)

    def formfield_for_reference_listfield(self, db_field, request=None, **kwargs):
        """
        Get a form Field for a ManyToManyField.
        """
        if db_field.name in self.raw_id_fields:
            kwargs['widget'] = MultiReferenceRawIdWidget(
                db_field.field.rel, self.admin_site)
            kwargs['help_text'] = ''
        elif db_field.name in (list(self.filter_vertical) + list(self.filter_horizontal)):
            kwargs['widget'] = widgets.FilteredSelectMultiple(
                forms.forms.pretty_name(db_field.name), (db_field.name in self.filter_vertical))

        return formfield(db_field, **kwargs)


class DocumentAdmin(MongoFormFieldMixin, ModelAdmin):
    change_list_template = "admin/change_document_list.html"
    form = DocumentForm

    _embedded_inlines = None

    def __init__(self, model, admin_site):
        super(DocumentAdmin, self).__init__(model, admin_site)

        self.inlines = self._find_embedded_inlines()

    def _find_embedded_inlines(self):
        emb_inlines = []
        exclude = self.exclude or []
        for name in self.model._fields_ordered:
            f = self.model._fields.get(name)
            if not (isinstance(f, ListField) and isinstance(getattr(f, 'field', None), EmbeddedDocumentField)) and not isinstance(f, EmbeddedDocumentField):
                continue
            # Should only reach here if there is an embedded document...
            if f.name in exclude:
                continue
            if hasattr(f, 'field') and f.field is not None:
                embedded_document = f.field.document_type
            elif hasattr(f, 'document_type'):
                embedded_document = f.document_type
            else:
                # For some reason we found an embedded field were either
                # the field attribute or the field's document type is None.
                # This shouldn't happen, but apparently does happen:
                # https://github.com/jschrewe/django-mongoadmin/issues/4
                # The solution for now is to ignore that field entirely.
                continue

            init_document_options(embedded_document)

            embedded_admin_base = EmbeddedStackedDocumentInline
            embedded_admin_name = "%sAdmin" % embedded_document.__name__
            inline_attrs = {
                'model': embedded_document,
                'parent_field_name': f.name,
            }
            # if f is an EmbeddedDocumentField set the maximum allowed form
            # instances to one
            if isinstance(f, EmbeddedDocumentField):
                inline_attrs['max_num'] = 1
            embedded_admin = type(
                embedded_admin_name, (embedded_admin_base,), inline_attrs
            )
            # check if there is an admin for the embedded document in
            # self.inlines. If there is, use this, else use default.
            for inline_class in self.inlines:
                if inline_class.document == embedded_document:
                    embedded_admin = inline_class
            emb_inlines.append(embedded_admin)

            if f.name not in exclude:
                exclude.append(f.name)

        # sort out the declared inlines. Embedded admins take a different
        # set of arguments for init and are stored seperately. So the
        # embedded stuff has to be removed from self.inlines here
        inlines = [i for i in self.inlines if i not in emb_inlines]

        self.exclude = exclude

        return inlines + emb_inlines

    def get_queryset(self, request):
        """
        Returns a QuerySet of all model instances that can be edited by the
        admin site. This is used by changelist_view.
        """
        qs = self.model.objects.clone()
        # TODO: this should be handled by some parameter to the ChangeList.
        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs

    def get_changelist(self, request, **kwargs):
        """
        Returns the ChangeList class for use on the changelist page.
        """
        from mongoadmin.views import DocumentChangeList
        return DocumentChangeList

    def get_object(self, request, object_id):
        """
        Returns an instance matching the primary key provided. ``None``  is
        returned if no match is found (or the object_id failed validation
        against the primary key field).
        """
        queryset = self.get_queryset(request)
        model = queryset._document
        try:
            object_id = model._meta.pk.to_python(object_id)
            return queryset.get(pk=object_id)
        except (model.DoesNotExist, ValidationError, ValueError):
            return None

    def get_form(self, request, obj=None, **kwargs):
        """
        Returns a Form class for use in the admin add view. This is used by
        add_view and change_view.
        """
        if 'fields' in kwargs:
            fields = kwargs.pop('fields')
        else:
            fields = flatten_fieldsets(self.get_fieldsets(request, obj))
        if self.exclude is None:
            exclude = []
        else:
            exclude = list(self.exclude)
        exclude.extend(self.get_readonly_fields(request, obj))
        if self.exclude is None and hasattr(self.form, '_meta') and self.form._meta.exclude:
            # Take the custom ModelForm's Meta.exclude into account only if the
            # ModelAdmin doesn't define its own.
            exclude.extend(self.form._meta.exclude)
        # if exclude is an empty list we pass None to be consistent with the
        # default on modelform_factory
        exclude = exclude or None
        defaults = {
            "form": self.form,
            "fields": fields,
            "exclude": exclude,
            "formfield_callback": partial(self.formfield_for_dbfield, request=request),
        }
        defaults.update(kwargs)

        if defaults['fields'] is None and not modelform_defines_fields(defaults['form']):
            defaults['fields'] = None

        try:
            return documentform_factory(self.model, **defaults)
        except FieldError as e:
            raise FieldError('%s. Check fields/fieldsets/exclude attributes of class %s.'
                             % (e, self.__class__.__name__))

    def save_related(self, request, form, formsets, change):
        """
        Given the ``HttpRequest``, the parent ``ModelForm`` instance, the
        list of inline formsets and a boolean value based on whether the
        parent is being added or changed, save the related objects to the
        database. Note that at this point save_form() and save_model() have
        already been called.
        """
        for formset in formsets:
            self.save_formset(request, form, formset, change=change)

    def log_addition(self, request, object):
        """
        Log that an object has been successfully added.

        The default implementation creates an admin LogEntry object.
        """
        if not is_django_user_model(request.user):
            return

        super(DocumentAdmin, self).log_addition(request=request, object=object)

    def log_change(self, request, object, message):
        """
        Log that an object has been successfully changed.

        The default implementation creates an admin LogEntry object.
        """
        if not is_django_user_model(request.user):
            return

        super(DocumentAdmin, self).log_change(
            request=request, object=object, message=message)

    def log_deletion(self, request, object, object_repr):
        """
        Log that an object has been successfully changed.

        The default implementation creates an admin LogEntry object.
        """
        if not is_django_user_model(request.user):
            return

        super(DocumentAdmin, self).log_deletion(
            request=request, object=object, object_repr=object_repr)


class EmbeddedInlineAdmin(MongoFormFieldMixin, InlineModelAdmin):
    parent_field_name = None
    formset = EmbeddedDocumentFormSet
    form = EmbeddedDocumentForm

    def get_queryset(self, request):
        """
        Returns a QuerySet of all model instances that can be edited by the
        admin site. This is used by changelist_view.
        """
        return getattr(self.parent_model, self.parent_field_name, [])

    def get_formset(self, request, obj=None, **kwargs):
        """Returns a BaseInlineFormSet class for use in admin add/change views."""

        if 'fields' in kwargs:
            fields = kwargs.pop('fields')
        else:
            fields = flatten_fieldsets(self.get_fieldsets(request, obj))
        if self.exclude is None:
            exclude = []
        else:
            exclude = list(self.exclude)
        exclude.extend(self.get_readonly_fields(request, obj))
        if self.exclude is None and hasattr(self.form, '_meta') and self.form._meta.exclude:
            # Take the custom ModelForm's Meta.exclude into account only if the
            # InlineModelAdmin doesn't define its own.
            exclude.extend(self.form._meta.exclude)
        # if exclude is an empty list we use None, since that's the actual
        # default
        exclude = exclude or None
        can_delete = self.can_delete and self.has_delete_permission(request, obj)
        defaults = {
            "form": self.form,
            "formset": self.formset,
            "embedded_name": self.parent_field_name,
            "fields": fields,
            "exclude": exclude,
            "formfield_callback": partial(self.formfield_for_dbfield, request=request),
            "extra": self.get_extra(request, obj, **kwargs),
            "max_num": self.get_max_num(request, obj, **kwargs),
            "can_delete": can_delete,
        }

        defaults.update(kwargs)
        base_model_form = defaults['form']

        class DeleteProtectedModelForm(base_model_form):

            def hand_clean_DELETE(self):
                """
                We don't validate the 'DELETE' field itself because on
                templates it's not rendered using the field information, but
                just using a generic "deletion_field" of the InlineModelAdmin.
                """
                if self.cleaned_data.get(DELETION_FIELD_NAME, False):
                    collector = NestedObjects()
                    collector.collect([self.instance])
                    if collector.protected:
                        objs = []
                        for p in collector.protected:
                            objs.append(
                                # Translators: Model verbose name and instance
                                # representation, suitable to be an item in a
                                # list
                                _('%(class_name)s %(instance)s') % {
                                    'class_name': p._meta.verbose_name,
                                    'instance': p}
                            )
                        params = {'class_name': self._meta.model._meta.verbose_name,
                                  'instance': self.instance,
                                  'related_objects': get_text_list(objs, _('and'))}
                        msg = _("Deleting %(class_name)s %(instance)s would require "
                                "deleting the following protected related objects: "
                                "%(related_objects)s")
                        raise ValidationError(
                            msg, code='deleting_protected', params=params)

            def is_valid(self):
                result = super(DeleteProtectedModelForm, self).is_valid()
                self.hand_clean_DELETE()
                return result

        defaults['form'] = DeleteProtectedModelForm

        if defaults['fields'] is None and not modelform_defines_fields(defaults['form']):
            defaults['fields'] = None

        return embeddedformset_factory(self.model, self.parent_model, **defaults)


class EmbeddedStackedDocumentInline(EmbeddedInlineAdmin):
    template = 'admin/edit_inline/stacked.html'


class EmbeddedTabularDocumentInline(EmbeddedInlineAdmin):
    template = 'admin/edit_inline/tabular.html'
