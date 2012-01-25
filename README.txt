django mongoadmin
=================

This a drop in replacement for the django admin that works with monodb.
It uses the django admin stuff wherever possible and can be used
together with normal django models and a SQL database.

Requirements
------------

-  Django >= 1.3
-  `mongoengine <http://mongoengine.org/>`_
-  `django-mongodbforms <https://github.com/jschrewe/django-mongodbforms>`_

Usage
-----

Add mongoadmin to ``INSTALLED_APPS`` settings

::

    INSTALLED_APPS = (
        ...
        'mongoadmin',
        'django.contrib.admin',
        ...
    )

Add mongoadmin to ``urls.py``

::

    from django.contrib import admin
    admin.autodiscover()

    from mongoadmin import site

    urlpatterns = patterns('',
        # Uncomment the next line to enable the admin:
        url(r'^admin/', include(site.urls)),
    )

The ``admin.py`` for your app needs to use mongoadmin instead of
django's admin:

::

    from mongoadmin import site, DocumentAdmin

    from app.models import AppDocument

    class AppDocumentAdmin(DocumentAdmin):
        pass
    site.register(AppDocument, AppDocumentAdmin)

Now the document should appear as usual in django's admin.

Using third party apps with mongoadmin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To use third party apps (i.e. apps that register their admin classes in
django.contrib.admin.site) with mongoadmin you have to add
``MONGOADMIN_OVERRIDE_ADMIN = True`` to your settings file. This
overrides the django admin site with mongoadmin's admin site.

What works and doesn't work
---------------------------

django-mongoadmin currently only supports the most basic things and even
they are not really tested.
