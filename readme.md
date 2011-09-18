# django mongoadmin

This a drop in replacement for the django admin that works with monodb. It uses the django admin stuff wherever possible and can be used together with normal django models and a SQL database.

## Requirements

 * Django >= 1.3
 * mongoengine
 * django-mongoforms

## Usage

Add mongoadmin to `INSTALLED_APPS` settings

	INSTALLED_APPS = (
		...
    	'mongoadmin',
    	'django.contrib.admin',
		...
	)

Add mongoadmin to `urls.py`

	from django.contrib import admin
	admin.autodiscover()

	from mongoadmin import site

	urlpatterns = patterns('',
    	# Uncomment the next line to enable the admin:
    	url(r'^admin/', include(site.urls)),
	)

The `admin.py` for your app needs to use mongoadmin instead of django's admin:

	from mongoadmin import site, DocumentAdmin

	from app.models import AppDocument
	
	class AppDocumentAdmin(DocumentAdmin):
	    pass
	site.register(AppDocument, AppDocumentAdmin)
	
Now the document should appear as usual in django's admin.

## What works and doesn't work

django-mongoadmin currently only supports the most basic things and even they are not really tested.

Changelists only support basic listings you probably won't be able to use fieldlists and every other feature that django supports for changelists (search, etc.).

Inline admin objects are created automatically for embedded objects, but can't be defined manually for referenced objects. Although I haven't tested it, field widget can't be overwritten.

## TODO

 * highlight required fields

