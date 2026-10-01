"""
Local development settings.

Runs the site against a throwaway SQLite file instead of the production MySQL
instance, so the UI can be worked on without a database server:

    python manage.py makemigrations OpenBench --settings=OpenSite.settings_local
    python manage.py migrate                  --settings=OpenSite.settings_local
    python manage.py seed_demo                --settings=OpenSite.settings_local
    python manage.py runserver                --settings=OpenSite.settings_local

Nothing here is used in production; OpenSite.settings remains the default.
"""

import os

# OpenSite.settings refuses to import without its secrets, by design. Local
# development has no production env file, so stand in throwaway values before
# importing: the key is never used to sign anything that leaves this machine,
# and the database password is unused because SQLite replaces MySQL below.
os.environ.setdefault('OPENBENCH_SECRET_KEY', 'local-development-key-not-secret')
os.environ.setdefault('OPENBENCH_DB_PASSWORD', 'unused-by-sqlite')

from OpenSite.settings import *

DEBUG = True

# Left on, matching production. Turning it off here once hid a bug where the
# minifier collapsed the whitespace a stat block is laid out with, so the page
# was only ever broken on the live site.
HTML_MINIFY = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}
