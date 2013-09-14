from .utils import has_rel_db, get_model_or_document

if has_rel_db():
    from django.contrib.contenttypes.models import ContentType, ContentTypeManager
else:
    from django.contrib.contenttypes.models import ContentTypeManager as DjangoContentTypeManager
    
    from mongoengine.queryset import QuerySet
    from mongoengine.django.auth import ContentType
    from mongoengine.base import get_document
    
    from mongodbforms import init_document_options
    from mongodbforms.documentoptions import patch_document
    
    
    class ContentTypeManager(DjangoContentTypeManager):
        def get_query_set(self):
            """Returns a new QuerySet object.  Subclasses can override this method
            to easily customize the behavior of the Manager.
            """
            return QuerySet(self.model, self.model._get_collection())
            
        def contribute_to_class(self, model, name):
            init_document_options(model)
            super(ContentTypeManager, self).contribute_to_class(model, name)
            
    def get_object_for_this_type(self, **kwargs):
        """
        Returns an object of this type for the keyword arguments given.
        Basically, this is a proxy around this object_type's get_object() model
        method. The ObjectNotExist exception, if thrown, will not be caught,
        so code that calls this method should catch it.
        """
        return self.model_class().objects.get(**kwargs)
        
    def model_class(self):
        return get_model_or_document(str(self.app_label), str(self.model))
    
    patch_document(get_object_for_this_type, ContentType, bound=False)
    patch_document(model_class, ContentType, bound=False)
    
    manager = ContentTypeManager()
    manager.contribute_to_class(ContentType, 'objects')
    
    try:
        from grappelli.templatetags import grp_tags
        grp_tags.ContentType = ContentType
    except ImportError:
        pass
    
    
    
    
    