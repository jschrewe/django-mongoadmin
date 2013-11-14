import django.contrib.admin.templatetags.log

from mongoadmin.util import is_django_user_model

class AdminLogNode(django.template.Node):
    def __init__(self, limit, varname, user):
        self.limit, self.varname, self.user = limit, varname, user

    def __repr__(self):
        return "<GetAdminLog Node>"

    def render(self, context):
        if not is_django_user_model(self.user):
            context[self.varname] = None
        elif self.user is None:
            context[self.varname] = LogEntry.objects.all().select_related('content_type', 'user')[:self.limit]
        else:
            user_id = self.user
            if not user_id.isdigit():
                user_id = context[self.user].pk
            context[self.varname] = LogEntry.objects.filter(user__pk__exact=user_id).select_related('content_type', 'user')[:int(self.limit)]
        return ''

django.contrib.admin.templatetags.log.AdminLogNode = AdminLogNode