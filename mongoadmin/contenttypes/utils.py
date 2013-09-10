import sys

from django.core.exceptions import ImproperlyConfigured
from django.contrib.contenttypes.models import ContentType
from django.db.models import get_model
from django.db import DatabaseError

from mongoengine.base.common import _document_registry

# if there is a relational db and we can load a content type
# object from it, we simply export Django's stuff and are done.
# Otherwise we roll our own (mostly) compatible version 
# using mongoengine.
try:
    ContentType.objects.all()[0]
    HAS_RELATIONAL_DB = True
except ImproperlyConfigured:
    # This assumes you use django.db.backends.dummy for now. 
    HAS_RELATIONAL_DB = False
except (DatabaseError, IndexError):
    # Chances are high that a db has been configured if
    # we get that exception. So we assume that a we have
    # a relational db
    HAS_RELATIONAL_DB = True
    
def get_model_or_document(app_label, model):
    if HAS_RELATIONAL_DB:
        return get_model(app_label, model, only_installed=False)
    else:
        # mongoengine's document registry is case sensitive
        # while all models are stored in lowercase in the
        # content types. So we can't use get_document.
        model = str(model).lower()
        possible_docs = [v for k, v in _document_registry.items() if k.lower() == model]
        if len(possible_docs) == 1:
            return possible_docs[0]
        if len(possible_docs) > 1:
            for doc in possible_docs:
                module = sys.modules[doc.__module__]
                doc_app_label = model_module.__name__.split('.')[-2]
                if doc_app_label.lower() == app_label.lower():
                    return doc
        return None