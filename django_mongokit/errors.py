
class DatabaseError(Exception): 
    pass

class IntegrityError(DatabaseError):
    pass
