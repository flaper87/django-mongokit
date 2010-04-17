
import re
from mongokit import ObjectId
from errors import DatabaseError

class QuerySet(object):
    def __init__(self, cursor=None, cls=None, spec={}):
        self._cursor = cursor
        self._collection = cls.get_collection()
        self._db = self._collection.database
        self._class_object = cls        
        self._spec_cache = {}
        self._spec = {}
        
        self._fields = {}
        self._fields_cache = {}
        
        self._filter(spec)
        
    def _get_query_spec(self, parameters):
        """ 
        Convert django.db.models.sql.where.WhereNode tree 
        to query dict for MongoDB "find" collection method.
        """
        spec = {}
        for key in parameters:
            res = {}
            params = parameters[key]
            
            if not "__" in key:
                spec.update({key : params})
                continue
            
            parent_negated = "__not__" in key
            final_key = key.replace("__not__", "__")
            field_name, lookup_type  = final_key.split("__")
            if field_name in ["id", "pk"]:
                field_name = "_id"
                params = [isinstance(par, basestring) and ObjectId(par) or par for par in params]
            if lookup_type == "exact":
                if parent_negated:
                    res = {field_name: {"$not": params}}
                else:
                    res = {field_name: params}
            elif lookup_type == "icontains":
                par_re = re.compile("%s" % re.escape(params), re.I)
                if parent_negated:
                    res = {field_name: {"$not": par_re}}
                else:
                    res = {field_name: par_re}
            elif lookup_type == "iexact":
                par_re = re.compile("^%s$" % re.escape(params), re.I)
                if parent_negated:
                    res = {field_name: {"$not": par_re}}
                else:
                    res = {field_name: par_re}
            elif lookup_type == "startswith":
                par_re = re.compile("^%s" % re.escape(params), re.I)
                if parent_negated:
                    res = {field_name: {"$not": par_re}}
                else:
                    res = {field_name: par_re}
            elif lookup_type == "endswith":
                par_re = re.compile(".*%s$" % re.escape(params), re.I)
                if parent_negated:
                    res = {field_name: {"$not": par_re}}
                else:
                    res = {field_name: par_re}
            elif lookup_type == "gt":
                res = {field_name:{parent_negated and "$lte" or "$gt":params}}
            elif lookup_type == "gte":
                res = {field_name:{parent_negated and "$lt" or "$gte":params}}
            elif lookup_type == "lt":
                res = {field_name:{parent_negated and "$gte" or "$lt":params}}
            elif lookup_type == "lte":
                res = {field_name:{parent_negated and "$gt" or "$lte":params}}
            elif lookup_type == 'in':
                if not value_annot:
                    raise EmptyResultSet
                res = {field_name: {parent_negated and "$nin" or "$in": params}}
            else:
                raise DatabaseError("Unsupported lookup type: %r" % lookup_type)
    
            spec.update(res)
            
        return spec
        
    def _filter(self, spec_draft, **kwargs):
        spec = self._get_query_spec(spec_draft)
        self._spec_cache = self._spec.copy()
        self._spec.update(spec)
        self._load_data()
        
    def fields(self, spec_draft, **kwargs):
        spec = self._get_query_spec(spec_draft)
        self._fields_cache = self._spec.copy()
        self._fields.update(spec)
        self._load_data()
        
    def find(self, *args, **kwargs):
        if kwargs and kwargs != self._spec:
            self._filter(kwargs)
            
    def filter(self, *args, **kwargs):
        return self.find(*args, **kwargs)
        
    def distinct(self, *args, **kwargs):
        return self._cursor.distinct(*args, **kwargs)

    def where(self, *args, **kwargs):
        return self.__class__(self._cursor.where(*args, **kwargs), self._class_object)

    def sort(self, *args, **kwargs):
        return self.__class__(self._cursor.sort(*args, **kwargs), self._class_object)
    
    def order_by(self, *args, **kwargs):
        d = {}
        for col in args:
            d.update({ (col.startswith("-") and col[1:]) or col : (col.startswith("-") and -1) or 1 })
        return self.__class__(self._cursor.sort(*(d), **kwargs), self._class_object)
    
    def limit(self, *args, **kwargs):
        return self.__class__(self._cursor.limit(*args, **kwargs), self._class_object)

    def hint(self, *args, **kwargs):
        return self.__class__(self._cursor.hint(*args, **kwargs), self._class_object)

    def count(self, *args, **kwargs):
        return self._cursor.count(*args, **kwargs)
        
    def explain(self, *args, **kwargs):
        return self._cursor.explain(*args, **kwargs)

    def next(self, *args, **kwargs):
        data = self._cursor.next(*args, **kwargs)
        return self._class_object(data, collection=self._collection)

    def skip(self, *args, **kwargs):
        return self.__class__(self._cursor.skip(*args, **kwargs), self._class_object)

    def clone(self, *args, **kwargs):
        return self.__class__(self._cursor.clone(), self._class_object, spec=self._spec)
    
    def values(self, *args):
        return (args and [dict(zip(args,[doc[key if not key in ["id", "pk"] else "_id"] for key in args])) for doc in self]) or [obj for obj in self._cursor.clone()] 
        
    def values_list(self, *args, **kwargs):
        flat = kwargs.pop("flat", False)
        if flat and len(args) > 1:
            raise Exception("args len must be 1 when flat=True")
        
        return (flat and self.distinct(args[0] if not args[0] in ["id", "pk"] else "_id")) or zip(*[self.distinct(field if not field in ["id", "pk"] else "_id") for field in args])

    def __iter__(self, *args, **kwargs):
        cursor = self._cursor.clone()
        for obj in cursor:
            yield self._class_object(obj, collection=self._collection)
            
    def __getitem__(self, k):
        return list(self)[k]
    
    def __len__(self, *args, **kwargs):
        return self.count()
            
    def _load_data(self):
        if self._spec != self._spec_cache or self._spec == {} or self._fields != self._fields_cache:
            self._cursor = self._collection.find(*[self._spec])
