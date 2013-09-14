from django.contrib.admin.widgets import ForeignKeyRawIdWidget, ManyToManyRawIdWidget
from django.utils.html import escape
from django.utils.text import Truncator

class ReferenceRawIdWidget(ForeignKeyRawIdWidget):
    """
    A Widget for displaying ReferenceFields in the "raw_id" interface rather than
    in a <select> box.
    """
    def render(self, name, value, attrs=None):
        if attrs is None:
            attrs = {}
        if 'style' not in attrs:
            attrs['style'] = 'width:30em;'
        return super(ReferenceRawIdWidget, self).render(name=name, value=value, attrs=attrs)
    
    def url_parameters(self):
        #from django.contrib.admin.views.main import TO_FIELD_VAR
        params = self.base_url_parameters()
        # There are no reverse relations in mongo. Still need to figure out what
        # the url param does though.
        #params.update({TO_FIELD_VAR: self.rel.get_related_field().name})
        return params

    def label_for_value(self, value):
        #key = self.rel.get_related_field().name
        try:
            obj = self.rel.to.objects().get(**{'pk': value})
            return '&nbsp;<strong>%s</strong>' % escape(Truncator(obj).words(14, truncate='...'))
        except (ValueError, self.rel.to.DoesNotExist):
            return ''
            
class MultiReferenceRawIdWidget(ManyToManyRawIdWidget):
    def render(self, name, value, attrs=None):
        if attrs is None:
            attrs = {}
        if 'style' not in attrs:
            attrs['style'] = 'width:40em;'
        return super(MultiReferenceRawIdWidget, self).render(name=name, value=value, attrs=attrs)
        
        