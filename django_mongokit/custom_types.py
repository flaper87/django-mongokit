import pickle
from mongokit import *
from copy import deepcopy
from django.db import models
from mongokit import Document
from shortcut import connection
from pymongo.dbref import DBRef

class MongoReference(DBRef):
    def __init__(self, obj):
        super(MongoReference, self).__init__(database=obj.db.name,
                                             collection=obj.collection.name,
                                             id=obj._id)
        self._doc = obj
        self.obj_class = obj.__class__
        self.connection = obj.connection
        
    def __deepcopy__(self, memo={}):
        obj = self.__class__(deepcopy(self._doc, memo))
        return obj

class DjangoReference(dict):
    def __init__(self, obj, *args, **kwargs):
        super(DjangoReference, self).__init__(*args, **kwargs)
        
        if isinstance(obj, dict):
            self.update(obj)
            return
        
        self["django_class"] = pickle.dumps(obj.__class__)
        self["pk"] = obj.pk
    
    def __setattr__(self, key, value):
        """
        Arguments:
        - key: The key to update
        - value: The value to set.
        """
        if key == "django_class": 
            value = pickle.dumps(value)
            return
        
        super(DjangoReference, self).__getitem__(key, value)
        
    def __getattr__(self, key):
        """
        If the value is an instance of DBRef we query for an object
        of type self.__class__.__name__ with id equal to the DBRef id.
        
        Arguments:
        - key: The key to update
        """
        try: 
            val = super(DjangoReference, self).__getitem__(key)
            
            if key == "django_class": 
                return pickle.loads(str(val)) 
            return val
        except:
            return self.__getattribute__(key)

        
class MongoList(list):
    def append(self, item):
        if isinstance(item, models.Model):
            item =  DjangoReference(item)
        elif isinstance(item, Document):
            item =  MongoReference(item)
            
        super(MongoList, self).append(item)
        
    def add(self, item):
        self.append(item)
        
    def all(self):
        return self
        
    def __iter__(self, *args, **kwargs):
        for val in super(MongoList, self).__iter__(*args, **kwargs):
            if ("django_class" in val and "pk" in val):
                if not isinstance(val, DjangoReference):
                    val = DjangoReference(val)
                yield val.django_class.objects.get(pk=val.pk)
                continue
            
            if isinstance(val, DBRef) or isinstance(val, MongoReference):
                col = connection[val.database][val.collection]
                doc = col.one({'_id':val.id})
                if doc is None:
                    raise AutoReferenceError()
                yield val.obj_class(doc, collection=col)
                continue
            yield val