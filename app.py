import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'skinsensation.settings'
os.environ['DJANGO_ENV'] = 'production'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
