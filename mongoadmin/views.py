import operator

from django.utils.encoding import force_unicode, smart_str
from django.utils.translation import ugettext
from django.db import models
from django.core.exceptions import SuspiciousOperation
from django.contrib.admin.views.main import ChangeList, ALL_VAR, PAGE_VAR, IS_POPUP_VAR, TO_FIELD_VAR, ERROR_FLAG, SEARCH_VAR, ORDER_VAR, ORDER_TYPE_VAR
try:
    from django.contrib.admin.views.main import MAX_SHOW_ALL_ALLOWED
except ImportError:
    MAX_SHOW_ALL_ALLOWED = None
from django.contrib.admin.options import IncorrectLookupParameters
from django.core.paginator import InvalidPage


class DocumentChangeList(ChangeList):
    def __init__(self, request, model, list_display, list_display_links, list_filter, date_hierarchy, search_fields, list_select_related, list_per_page, list_editable, model_admin):
        self.model = model
        self.opts = model_admin.opts
        self.lookup_opts = self.opts
        self.root_query_set = model_admin.queryset(request)
        self.list_display = list_display
        self.list_display_links = list_display_links
        self.list_filter = list_filter
        self.date_hierarchy = date_hierarchy
        self.search_fields = search_fields
        self.list_select_related = list_select_related
        self.list_per_page = list_per_page
        self.model_admin = model_admin
        
        # Get search parameters from the query string.
        try:
            self.page_num = int(request.GET.get(PAGE_VAR, 0))
        except ValueError:
            self.page_num = 0
        self.show_all = ALL_VAR in request.GET
        self.is_popup = IS_POPUP_VAR in request.GET
        self.to_field = request.GET.get(TO_FIELD_VAR)
        self.params = dict(request.GET.items())
        if PAGE_VAR in self.params:
            del self.params[PAGE_VAR]
        if ERROR_FLAG in self.params:
            del self.params[ERROR_FLAG]

        if self.is_popup:
            self.list_editable = ()
        else:
            self.list_editable = list_editable
        self.order_field, self.order_type = self.get_ordering()
        self.query = request.GET.get(SEARCH_VAR, '')
        self.query_set = self.get_query_set()
        self.get_results(request)
        self.title = (self.is_popup and ugettext('Select %s') % force_unicode(self.opts.verbose_name) or ugettext('Select %s to change') % force_unicode(self.opts.verbose_name))
        
        try:
            self.filter_specs, self.has_filters = self.get_filters(request)
        except ValueError:
            print "FIXME: This is a workaround for Django 1.4 new list_filter"
            (self.filter_specs, self.has_filters, remaining_lookup_params,
             use_distinct) = self.get_filters(request)
             
        self.pk_attname = self.lookup_opts.pk_name
  
    def get_results(self, request):
        paginator = self.model_admin.get_paginator(request, self.query_set, self.list_per_page)
        # Get the number of objects, with admin filters applied.
        result_count = paginator.count

        # Get the total number of objects, with no admin filters applied.
        # Perform a slight optimization: Check to see whether any filters were
        # given. If not, use paginator.hits to calculate the number of objects,
        # because we've already done paginator.hits and the value is cached.
        #
        # NOT USED FOR MONGOENGINE
        # TODO: Implement for mongoengine
        #if not self.query_set.query.where:
        #    full_result_count = result_count
        #else:
        full_result_count = self.root_query_set.count()

        # Django <= 1.3 uses a module level constant
        # Django 1.4 uses a change list attribute
        # check what we have here 
        if hasattr(self, 'list_max_show_all'):
            can_show_all = result_count <= self.list_max_show_all
        else:
            can_show_all = result_count <= MAX_SHOW_ALL_ALLOWED
        multi_page = result_count > self.list_per_page

        # Get the list of objects to display on this page.
        if (self.show_all and can_show_all) or not multi_page:
            result_list = self.query_set
        else:
            try:
                result_list = paginator.page(self.page_num+1).object_list
            except InvalidPage:
                raise IncorrectLookupParameters

        self.result_count = result_count
        self.full_result_count = full_result_count
        self.result_list = result_list
        self.can_show_all = can_show_all
        self.multi_page = multi_page
        self.paginator = paginator

    def get_ordering(self):
        lookup_opts, params = self.lookup_opts, self.params
        # For ordering, first check the "ordering" parameter in the admin
        # options, then check the object's default ordering. If neither of
        # those exist, order descending by ID by default. Finally, look for
        # manually-specified ordering from the query string.
        ordering = self.model_admin.ordering or lookup_opts.ordering or ['-' + lookup_opts.id_field]

        if ordering[0].startswith('-'):
            order_field, order_type = ordering[0][1:], 'desc'
        else:
            order_field, order_type = ordering[0], 'asc'
        if ORDER_VAR in params:
            try:
                field_name = self.list_display[int(params[ORDER_VAR])]
                try:
                    f = lookup_opts.get_field(field_name)
                except models.FieldDoesNotExist:
                    # See whether field_name is a name of a non-field
                    # that allows sorting.
                    try:
                        if callable(field_name):
                            attr = field_name
                        elif hasattr(self.model_admin, field_name):
                            attr = getattr(self.model_admin, field_name)
                        else:
                            attr = getattr(self.model, field_name)
                        order_field = attr.admin_order_field
                    except AttributeError:
                        pass
                else:
                    order_field = f.name
            except (IndexError, ValueError):
                pass # Invalid ordering specified. Just use the default.
        if ORDER_TYPE_VAR in params and params[ORDER_TYPE_VAR] in ('asc', 'desc'):
            order_type = params[ORDER_TYPE_VAR]
        return order_field, order_type

      
    def get_query_set(self):
        use_distinct = False

        qs = self.root_query_set
        lookup_params = self.params.copy() # a dictionary of the query string
        for i in (ALL_VAR, ORDER_VAR, ORDER_TYPE_VAR, SEARCH_VAR, IS_POPUP_VAR, TO_FIELD_VAR):
            if i in lookup_params:
                del lookup_params[i]
        for key, value in lookup_params.items():
            if not isinstance(key, str):
                # 'key' will be used as a keyword argument later, so Python
                # requires it to be a string.
                del lookup_params[key]
                lookup_params[smart_str(key)] = value

            if not use_distinct:
                # Check if it's a relationship that might return more than one
                # instance
                field_name = key.split('__', 1)[0]
                try:
                    f = self.lookup_opts.get_field_by_name(field_name)[0]
                except models.FieldDoesNotExist:
                    raise IncorrectLookupParameters
                if hasattr(f, 'rel') and isinstance(f.rel, models.ManyToManyRel):
                    use_distinct = True

            # if key ends with __in, split parameter into separate values
            if key.endswith('__in'):
                value = value.split(',')
                lookup_params[key] = value

            # if key ends with __isnull, special case '' and false
            if key.endswith('__isnull'):
                if value.lower() in ('', 'false'):
                    value = False
                else:
                    value = True
                lookup_params[key] = value

            if not self.model_admin.lookup_allowed(key, value):
                raise SuspiciousOperation(
                    "Filtering by %s not allowed" % key
                )

        # Apply lookup parameters from the query string.
        try:
            qs = qs.filter(**lookup_params)
        # Naked except! Because we don't have any other way of validating "params".
        # They might be invalid if the keyword arguments are incorrect, or if the
        # values are not in the correct type, so we might get FieldError, ValueError,
        # ValicationError, or ? from a custom field that raises yet something else
        # when handed impossible data.
        except:
            raise IncorrectLookupParameters

        # Use select_related() if one of the list_display options is a field
        # with a relationship and the provided queryset doesn't already have
        # select_related defined.
        #
        # CURRENTLY NOT USED FOR MONGOENGINE!
        #if not qs.query.select_related:
        #    if self.list_select_related:
        #        qs = qs.select_related()
        #    else:
        #        for field_name in self.list_display:
        #            try:
        #                f = self.lookup_opts.get_field(field_name)
        #            except models.FieldDoesNotExist:
        #                pass
        #            else:
        #                if isinstance(f.rel, models.ManyToOneRel):
        #                    qs = qs.select_related()
        #                    break

        # Set ordering.
        if self.order_field:
            qs = qs.order_by('%s%s' % ((self.order_type == 'desc' and '-' or ''), self.order_field))

        # Apply keyword searches.
        def construct_search(field_name):
            if field_name.startswith('^'):
                return "%s__istartswith" % field_name[1:]
            elif field_name.startswith('='):
                return "%s__iexact" % field_name[1:]
            elif field_name.startswith('@'):
                return "%s__search" % field_name[1:]
            else:
                return "%s__icontains" % field_name

        if self.search_fields and self.query:
            orm_lookups = [construct_search(str(search_field))
                           for search_field in self.search_fields]
            for bit in self.query.split():
                or_queries = [models.Q(**{orm_lookup: bit})
                              for orm_lookup in orm_lookups]
                qs = qs.filter(reduce(operator.or_, or_queries))
            if not use_distinct:
                for search_spec in orm_lookups:
                    field_name = search_spec.split('__', 1)[0]
                    f = self.lookup_opts.get_field_by_name(field_name)[0]
                    if hasattr(f, 'rel') and isinstance(f.rel, models.ManyToManyRel):
                        use_distinct = True
                        break

        if use_distinct:
            return qs.distinct()
        else:
            return qs
    

