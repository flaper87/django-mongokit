import inspect
import re

from south.db import generic
    
class DatabaseOperations(generic.DatabaseOperations):
    """
    MongoDB implementation of database operations.
    """
    
    backend_name = "mongodb"

    supports_foreign_keys = False
    has_check_constraints = False

    def add_column(self, table_name, name, field, *args, **kwds):
        pass
    
    def alter_column(self, table_name, name, field, explicit_name=True):
        pass

    def delete_column(self, table_name, column_name):
        pass
    
    def rename_column(self, table_name, old, new):
        pass
    
    def create_unique(self, table_name, columns):
        pass
    
    def delete_unique(self, table_name, columns):
        pass

    def delete_primary_key(self, table_name):
        pass
    
    def delete_table(self, table_name, cascade=True):
        pass