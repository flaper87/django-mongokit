"""
MongoKit (MongoDB) backend for Django.
"""

from mongokit import Connection
from mongokit.document import DocumentProperties, CallableMixin

from django.core.exceptions import ImproperlyConfigured
from django.db.backends import *
from django.db.backends.creation import BaseDatabaseCreation
from django.conf import settings

from django_mongokit.errors import *

class UnsupportedConnectionOperation(Exception):
    pass

def complain(*args, **kwargs):
    #print "ARGS", args
    #print "KWARGS", kwargs
    raise UnsupportedConnectionOperation("ARGS=%s" % unicode(args))

def ignore(*args, **kwargs):
    pass

class DatabaseOperations(BaseDatabaseOperations):
    def quote_name(self, name):
        return '<%s>' % name
    def sql_flush(self, *args, **kwargs):
        # deliberately do nothing as this doesn't apply to us
        return [True] # pretend that we did something

class DatabaseClient(BaseDatabaseClient):
    runshell = complain

class DatabaseIntrospection(BaseDatabaseIntrospection):
    #get_table_list = complain
    def get_table_list(self, cursor):
        return []
    get_table_description = complain
    get_relations = complain
    get_indexes = complain
    
    
 
# Needed for Django <1.2
#class MongoCursor(object):
#    latest_result = None
#    def execute(self, sql, params=None):
#        print "SQL Command"
#        print repr(sql)
#        print 
#        self.latest_result = None
#        
#    def fetchone(self):
#        return [self.latest_result]

TEST_DATABASE_PREFIX = 'test_'
    
class DatabaseCreation(BaseDatabaseCreation):
    def create_test_db(self, verbosity=1, autoclobber=False):
        # No need to create databases in mongoDB :)
        # but we can make sure that if the database existed is emptied
        
        if self.connection.settings_dict.get('TEST_NAME'):
            test_database_name = self.connection.settings_dict['TEST_NAME']
        elif 'NAME' in self.connection.settings_dict:
            test_database_name = TEST_DATABASE_PREFIX + self.connection.settings_dict['NAME']
        elif 'DATABASE_NAME' in self.connection.settings_dict:
            if self.connection.settings_dict['DATABASE_NAME'].startswith(TEST_DATABASE_PREFIX):
                # already been set up
                # must be because this is called from a setUp() instead of something formal.
                # suspect this Django 1.1
                test_database_name = self.connection.settings_dict['DATABASE_NAME']
            else:
                test_database_name = TEST_DATABASE_PREFIX + \
                  self.connection.settings_dict['DATABASE_NAME']
        else:
            raise ValueError("Name for test database not defined")
            
        # This is important. Here we change the settings so that all other code
        # things that the chosen database is now the test database. This means
        # that nothing needs to change in the test code for working with 
        # connections, databases and collections. It will appear the same as
        # when working with non-test code.
        try:
            settings.DATABASES['mongodb']['NAME'] = test_database_name
        except AttributeError:
            settings.MONGO_DATABASE_NAME = test_database_name
            
        settings.DATABASE_SUPPORTS_TRANSACTIONS = False # MongoDB :)
        
        # In this phase it will only drop the database if it already existed
        # which could potentially happen if the test database was created but 
        # was never dropped at the end of the tests
        self._drop_database(test_database_name)
        # if it didn't exist it will automatically be created by the mongokit conncetion
        
    def destroy_test_db(self, old_database_name, verbosity=1):
        """
        Destroy a test database, prompting the user for confirmation if the
        database already exists. Returns the name of the test database created.
        """
        if verbosity >= 1:
            print "Destroying test database '%s'..." % self.connection.alias
        if 'DATABASE_NAME' in self.connection.settings_dict:
            # Django <1.2
            test_database_name = settings.MONGO_DATABASE_NAME #self.connection.settings_dict['DATABASE_NAME']
        else:
            test_database_name = self.connection.settings_dict['NAME']
        self._drop_database(test_database_name)
        
        try:
            settings.DATABASES['mongodb']['NAME'] = old_database_name
        except AttributeError:
            # Django <1.2
            settings.MONGO_DATABASE_NAME = old_database_name
        
    def _drop_database(self, database_name):
        if not database_name.startswith(TEST_DATABASE_PREFIX):
            # paranoia
            raise DatabaseError(
              "Suspicous! Can't delete database (%r) unless it's prefixed by %s" % \
              (database_name, TEST_DATABASE_PREFIX))
        if database_name in self.connection.connection.database_names():
            # needs to be dropped
            self.connection.connection.drop_database(database_name)
        



class DatabaseWrapper(BaseDatabaseWrapper):
    operators = {}
    _commit = ignore
    _rollback = ignore
    
    autocommit = None # ignore 
    
    
    def __init__(self, settings_dict, alias=None, # alias was added in Django 1.2
                 *args, **kwargs):
        self.features = BaseDatabaseFeatures()
        self.ops = DatabaseOperations()
        self.client = DatabaseClient(self)
        self.creation = DatabaseCreation(self)
        self.introspection = DatabaseIntrospection(self)
        try:
            self.validation = BaseDatabaseValidation(self)
        except TypeError:
            # Django < 1.2
            self.validation = BaseDatabaseValidation()

        settings_dict['SUPPORTS_TRANSACTIONS'] = False
        self.settings_dict = settings_dict
        self.alias = alias and alias or settings_dict['DATABASE_NAME']
        
        self.connection = ConnectionWrapper(host=self.settings_dict["HOST"],
                                            port=int(self.settings_dict["PORT"]
or 27017))
 
# Experimenting with commenting this out
#    def _cursor(self):
#        return MongoCursor()
    

    def close(self):
        pass

class ConnectionWrapper(Connection):
    # Need to pretend we care about autocommit
    # BaseDatabaseCreation (in django/db/backends/creation.py) needs to
    # set autocommit
    autocommit = True # Needed attribute but its value is ignored
    
    def __init__(self, *args, **kwargs):
        super(ConnectionWrapper, self).__init__(*args, **kwargs)
        
    def __repr__(self):
        return 'ConnectionWrapper: ' + super(ConnectionWrapper, self).__repr__()
    
    def register(self, obj_list):
        """
        Django wants __module__ attr so we had to overwrite this method.
        """
        for obj in obj_list:
            # we'll set obj as mmanager model If there's one and its model is None
#            if not hasattr(obj, "mmanager"):
#                obj.mmanager = MongoManager()
#                obj.mmanager.model = obj
                 
#            if hasattr(obj, "objects") and not isinstance(getattr(obj, "objects"), MongoManager):
#                setattr(obj, "dobjects", getattr(obj, "objects"))
            if hasattr(obj, "objects"):
                if callable(obj.objects):
                    obj.objects = obj.objects()
                if not obj.objects.model:
                    obj.objects.model = obj

            #We don't want descriptors_validation
            if not obj.skip_validation:
                obj()._validate_descriptors()
            CallableDocument = type(
              "Callable%s" % obj.__name__,
              (obj, CallableMixin), {"_obj_class":obj, "__repr__":obj.__repr__, "__module__":obj.__module__})
            self._registered_documents[obj.collection_name] = CallableDocument
