import sys
import re
from mongokit import *
from copy import deepcopy
from django.db import models
from queryset import QuerySet
from django.db.models import signals
from pymongo.errors import OperationFailure 
from shortcut import connection, get_database
from mongokit.document import DocumentProperties, CallableMixin
from custom_types import MongoReference, DjangoReference, MongoList

model_names = []

class _PK(object):
    attname = '_id'

class _Meta(object):
    def __init__(self, model_name, verbose_name, verbose_name_plural,
                 module_name=None, 
                 app_label=None, 
                 ):
        self.model_name = model_name
        self.verbose_name = verbose_name and verbose_name or \
          re.sub('([a-z])([A-Z])', r'\1 \2', model_name)
        self.verbose_name_plural = verbose_name_plural or self.verbose_name + 's'
        self.module_name = module_name
        self.app_label = app_label
        self.pk = _PK() # needed for haystack

        #all_verbose_names.append(verbose_name)
        model_names.append((model_name, self.verbose_name))

    def __repr__(self):
        return "<Meta %s %r, %r>" % (self.model_name,
                                     self.verbose_name,
                                     self.verbose_name_plural)


class DjangoDocumentMetaClass(DocumentProperties):
    def __new__(cls, name, bases, attrs):
        new_class = super(DjangoDocumentMetaClass, cls).__new__(cls, name, bases, attrs)

        if CallableMixin in bases:
            # When you register models in the views for example it will register
            # all the models again but then they'll be subclasses of mongokit's
            # CallableMixin.
            # When this is the case we don't want to bother registering any
            # meta stuff about them so exit here
            return new_class

        meta = attrs.pop('Meta', None)

        if meta and getattr(meta, 'abstract', False):
            # No need to attach more meta crap
            return new_class

        verbose_name = meta and getattr(meta, 'verbose_name', None) or None
        verbose_name_plural = meta and getattr(meta, 'verbose_name_plural', None) or None
        meta = _Meta(name, verbose_name, verbose_name_plural)

        model_module = sys.modules[new_class.__module__]
        try:
            meta.app_label = model_module.__name__.split('.')[-2]
        except IndexError:
            meta.app_label = model_module.__name__

        new_class._meta = meta
        return new_class

class DjangoDocumentManager(object):
    
    model = None
    
    def using_col(self, col):
        if not isinstance(col, basestring):
            raise AttributeError("col must be instance of basestring")

        self.model.collection_name = col
        return self
    
    def change_db(self, db):
        if not isinstance(db, basestring):
            raise AttributeError("db must be instance of basestring")

        self.model.db_name = db
        return self
    
    def _to_mongo(self, kwargs):
        rst = {}
        for key in kwargs:
            value = kwargs[key]
            
            if key in ["id", "pk", "_id"]:
                if not isinstance(value, ObjectId):
                    value = ObjectId(value)
                rst["_id"] = value
                continue
                
            if isinstance(value, DjangoDocument):
                value = value.get_dbref()
        
            if isinstance(value, models.Model):
                value = DjangoReference(value)
            rst[key] = value
        return rst

#    @NormalizeId()            
    def find(self, **kwargs):
        return QuerySet(cursor=None, cls=self.model, spec=self._to_mongo(kwargs))

    def filter(self, **kwargs):
        return self.find(**kwargs)
    
    def all(self):
        return self.find()
    
    def get(self, **kwargs):
        return self.one(**kwargs)
    
    def values(self, *args):
        return self.find().values(*args)
    
    def values_list(self, *args, **kwargs):
        return self.find().values_list(*args, **kwargs)

#    @NormalizeId()
    def one(self, **kwargs):
        doc_cursor  = QuerySet(cursor=None, cls=self.model, spec=self._to_mongo(kwargs))
        count = doc_cursor.count()
        if count > 1:
            raise MultipleResultsFound("%s results found" % count)
        elif count == 1:
            return doc_cursor.next()
        return {}
    
    def count(self):
        return self.find().count()
    
    def order_by(self, *args, **kwargs):
        return self.find().order_by(*args, **kwargs)

    def update(self, **kwargs):
        document = kwargs.pop("set")
        #Lets extract the real kwargs
        ukwargs = {} 
        ukwargs["upsert"] = kwargs.pop("upsert", False)
        ukwargs["manipulate"] = kwargs.pop("manipulate", False)
        ukwargs["safe"] = kwargs.pop("safe", False)
        ukwargs["multi"] = kwargs.pop("multi", False)
        return self.model.get_collection().update(kwargs, document, **ukwargs)
    
    def create(self, **kwargs):
        obj = self.model(collection=self.model.get_collection())
        obj.generate_index()
        obj.update(self._to_mongo(kwargs))
        
        obj.save()           
        return obj
    
    def delete(self, **kwargs):
        if hasattr(self.model, "objects"):
            cursor = self.find(**kwargs)
            for obj in cursor:
                obj.delete()
        else:
            self.model.get_collection().remove(kwargs)

#    @NormalizeId()
    def get_or_create(self, *args, **kwargs):
        defaults = kwargs.pop("defaults", {})
        
        if not kwargs:
            raise AttributeError("At least 1 argument must be supplied")
        
        obj = self.model.get_collection().one(self._to_mongo(kwargs))
        created = False
        
        if obj:
            obj = self.one(**kwargs)
            obj.update(obj)
        
        if not obj:
            created = True
            kwargs.update(defaults)
            obj = self.create(**kwargs)
            
        return (obj, created)
    
class DjangoDocument(Document):
    use_autorefs = True
    skip_validation = True
    use_dot_notation = True
    structure = {}
    
    
    #Collection attrs
    collection_name=None
    capped_collection=False
    collection_max=None
    collection_size=None
    
    connection = connection
    
    # This allow us to use Document.objects.change_db('new_db')
    # Note that change_db is different from using_db. change_db uses 
    # the same connection but changes the db.
    db_name = get_database(connection).name
    
    #custom authorized types
    authorized_types = Document.authorized_types + [ MongoReference, DjangoReference, MongoList]
    
    class Meta:
        abstract = True

    __metaclass__ = DjangoDocumentMetaClass

    objects = DjangoDocumentManager
   
    def __init__(self, *args, **kwargs):
        super(DjangoDocument, self).__init__(*args, **kwargs)
        self.__collection = kwargs.pop("collection", None)
 
    ## XX Are these needed?
    def _get_pk_val(self, meta=None):
        if not meta:
            meta = self._meta
        #return str(getattr(self, meta.pk.attname))
        return str(self[meta.pk.attname])
    def _set_pk_val(self, value):
        raise ValueError("You can't set the ObjectId")
    pk = property(_get_pk_val, _set_pk_val)
    ##
    
    def __getattribute__(self, key):
        """
        Nothing useful for now.
        """
        if key in "collection" and self.__dict__.get(key) is None:
            return self.__collection or self.get_collection()
        if key in "db" and self.__dict__.get(key) is None:
            return self.get_database()
        if key in "connection" and self.__dict__.get(key) is None:
            return self.get_database().connection
        
        return super(DjangoDocument, self).__getattribute__(key)
    
    def __setattr__(self, key, value):
        """
        Converts value to MongoReference for those 
        classes referencing themselves in the structure.
        
        Converts value to DjangoReference for those 
        classes referencing django Models. 
        
        Arguments:
        - key: The key to update
        - value: The value to set.
        """
        if value and key in self.structure and self.structure[key] == MongoReference:
            value = value.get_dbref()
        
        if isinstance(value, models.Model):
            value = DjangoReference(value)
        
        super(DjangoDocument, self).__setattr__(key, value)            
    
    def __getattr__(self, key):
        """
        If the value is an instance of DBRef we query for an object
        of type self.__class__.__name__ with id equal to the DBRef id.
        
        Arguments:
        - key: The key to update
        """
        if key in ["id", "pk"]:
            key = (key.replace("id", "_id")).replace("pk", "_id")
            
        if key in ["collection", "db", "connection"]:
            return self.__getattribute__(key)
        
        val = super(DjangoDocument, self).__getattr__(key)
        
        if key == "_id": return val
        
        if issubclass(self.structure[key], DjangoReference) and val:
            if not key in self._cached_objs or not self._cached_objs[key]:
                self._cached_objs[key] = val.django_class.objects.get(pk=val.pk)
                return self._cached_objs[key]
            return self._cached_objs[key]
        
        if key in self.structure and self.structure[key] is MongoList and not isinstance(val, MongoList):
            if not key in self._cached_objs:
                self._cached_objs[key] = MongoList(val)
                return self._cached_objs[key]
            return self._cached_objs[key]
        
        if isinstance(val, DBRef) or isinstance(val, MongoReference):
            col = self.connection[val.database][val.collection]
            doc = col[self.__class__.__name__].find_one({'_id':val.id})
            if doc is None:
                raise AutoReferenceError()
            return doc
        
        return val
    
    def delete(self):
        signals.pre_delete.send(sender=self.__class__, instance=self)
        super(DjangoDocument, self).delete()
        signals.post_delete.send(sender=self.__class__, instance=self)

    def save(self, *args, **kwargs):
        signals.pre_save.send(sender=self.__class__, instance=self)
    
        _id_before = '_id' in self and self['_id'] or None
        super(DjangoDocument, self).save(*args, **kwargs)
        _id_after = '_id' in self and self['_id'] or None

        signals.post_save.send(sender=self.__class__, instance=self,
                               created=bool(not _id_before and _id_after))
        
    @classmethod
    def get_database(cls):
        return get_database(connection)
    
    @classmethod
    def get_collection(cls):
        """
        This is an aweful way to manage capped collections...
        """
        
        kwargs = {}
        if cls.capped_collection:
            kwargs["capped"] = True
        if  cls.collection_max:
            kwargs["max"] = cls.collection_max
        if  cls.collection_size:
            kwargs["size"] = cls.collection_size
        try:
            return Collection(cls.get_database(), cls.collection_name, **kwargs)
        except OperationFailure:
            return getattr(cls.get_database(), cls.collection_name)
        
    def get_dbref(self):
        assert '_id' in self, "You must specify an '_id' for using this method"
        return MongoReference(self)
    
    def __deepcopy__(self, memo={}):
        to_copy=dict(self)
        obj = self.__class__(doc=deepcopy(to_copy, memo), gen_skel=False, collection=self.collection)
        obj.__dict__ = self.__dict__.copy()
        return obj

