#!/usr/bin/env python
import os
import sys
import platform

def exit_upgrade():

    sys.stderr.write('''
    Project has been upgraded to python3 and Django 2.0

    Run last south migrations:
    --------

    git checkout django2-upgrade
    python manage.py migrate

    Upgrade to python3:
    -----------

    git checkout master
    python -mvirtualenv --python=python3 ../ --clear

    find . -name '*.pyc' -delete
    pip install -U setuptools

    Upgrade to django migrations
    ------------

    pip install -r requirements.txt

    # fix broken south
    pip install django-reversion==2.0.13
    rm ../lib/python3.5/site-packages/reversion/migrations/0001_squashed_0004_auto_20160611_1202.py
    python manage.py migrate reversion 0002_auto_20141216_1509 --fake

    python manage.py migrate --fake-initial

    Upgrade
    -------

    pip install -r requirements.txt
    python manage.py migrate --fake-initial
    ''')

    sys.exit(1)

if str(platform.python_version()).startswith('2'):
    exit_upgrade()

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "conferencecenter.settings")

    import django
    if django.VERSION[0] == 1:
        exit_upgrade()

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
