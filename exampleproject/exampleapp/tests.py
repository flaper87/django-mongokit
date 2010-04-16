from pprint import pprint
from django.core.urlresolvers import reverse
import datetime
from django.test import TestCase
from django.conf import settings

from django_mongokit import get_database
from models import Talk

try:
    from django.db import connections
    __django_12__ = True
except ImportError:
    __django_12__ = False

class ExampleTest(TestCase):
    def setUp(self):
        if not __django_12__:
            # Ugly but necessary
            from django.db import load_backend
            backend = load_backend('django_mongokit.mongodb')
            self.connection = backend.DatabaseWrapper({
                'DATABASE_HOST': getattr(settings, 'MONGO_DATABASE_HOST', None),
                'DATABASE_NAME': settings.MONGO_DATABASE_NAME,
                'DATABASE_OPTIONS': getattr(settings, 'MONGO_DATABASE_OPTIONS', None),
                'DATABASE_PASSWORD': getattr(settings, 'MONGO_DATABASE_PASSWORD', None),
                'DATABASE_PORT': getattr(settings, 'MONGO_DATABASE_PORT', None),
                'DATABASE_USER': getattr(settings, 'MONGO_DATABASE_USER', None),
                'TIME_ZONE': settings.TIME_ZONE,
            })
            self.old_database_name = settings.MONGO_DATABASE_NAME
            self.connection.creation.create_test_db()
                
        db = get_database()
        assert 'test_' in db.name, db.name
    
    def tearDown(self):
        for name in get_database().collection_names():
            if name not in ('system.indexes',):
                get_database().drop_collection(name)
                
        # because we have to manually control the creation and destruction of
        # databases in Django <1.2, I'll destroy the database here
        if not __django_12__:
            self.connection.creation.destroy_test_db(self.old_database_name)

        
    def test_creating_talk_basic(self):
        """test to create a Talk instance"""
        talk = Talk()
        talk.topic = u"Bla"
        talk.when = datetime.datetime.now()
        talk.tags = [u"foo", u"bar"]
        talk.duration = 5.5
        talk.validate()
        talk.save()
        
        self.assertTrue(talk['_id'])
        self.assertEqual(talk.duration, 5.5)
        
    def test_homepage(self):
        """rendering the homepage will show talks and will make it possible to 
        add more talks and delete existing ones"""
        response = self.client.get(reverse('homepage'))
        self.assertTrue(response.status_code, 200)
        self.assertTrue('No talks added yet' in response.content)
        
        data = {'topic': '', 
                'when': '2010-12-31',
                'duration':'1.0',
                'tags': ' foo , bar, ,'}
        response = self.client.post(reverse('homepage'), data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue('class="errorlist"' in response.content)
        self.assertTrue('This field is required' in response.content)
        
        data['topic'] = 'My Topic'
        response = self.client.post(reverse('homepage'), data)
        self.assertEqual(response.status_code, 302)
        
        response = self.client.get(reverse('homepage'))
        self.assertTrue(response.status_code, 200)
        self.assertTrue('My Topic' in response.content)
        self.assertTrue('31 December 2010' in response.content)
        self.assertTrue('Tags: foo, bar' in response.content)
        
        talk = Talk.objects.one()
        assert talk.topic == u"My Topic"
        delete_url = reverse('delete_talk', args=[str(talk._id)])
        response = self.client.get(delete_url)
        self.assertEqual(response.status_code, 302)
        
        response = self.client.get(reverse('homepage'))
        self.assertTrue(response.status_code, 200)
        self.assertTrue('My Topic' not in response.content)
        
        
        
        
        
