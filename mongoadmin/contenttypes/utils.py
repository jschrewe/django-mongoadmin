import sys

from django.conf import settings
from django.db.models import get_model

from mongoengine.base.common import _document_registry

# if there is a relational db and we can load a content type
# object from it, we simply export Django's stuff and are done.
# Otherwise we roll our own (mostly) compatible version 
# using mongoengine.

def has_rel_db():
    if not getattr(settings, 'MONGOADMIN_CHECK_CONTENTTYPE', True):
        return True
    
    engine = settings.DATABASES.get('default', {}).get('ENGINE', 'django.db.backends.dummy')
    if engine.endswith('dummy'):
        return False
    return True
    
def get_model_or_document(app_label, model):
    if has_rel_db():
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
                doc_app_label = module.__name__.split('.')[-2]
                if doc_app_label.lower() == app_label.lower():
                    return doc
        return None