from options import *

from mongoadmin.sites import site

from django.conf import settings

if getattr(settings, 'MONGOADMIN_OVERRIDE_ADMIN', False):
    import django.contrib.admin
    django.contrib.admin.site = site 