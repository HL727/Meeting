Video Meeting System
================

Backend is built using Django, Django Rest Framework, and background tasks in Celery. Frontend mainly in vuejs (and some django-based views).

Mividas Core, Rooms and Insights are in all included in the system but are activated depending on license flags and / or settings for users and customers in / admin /

To use the system in Windows, please set up a WSL (Windows subsystem for linux) with Ubuntu 20.04 and create a virtualenv in that due to not all libraries working correctly otherwise

Run this before cloning in windows:
```
git config core.autocrlf input
git config core.eol lf
```

Best practises och Git branch model
=================================

In short - use `git rebase`, use branches for larger changes, and try to keep `master` functioning at all times

Bootstrap development environment using docker
==============

Build and start image:

* `sh deploy/docker_devserver.sh`

Run in background and display streaming logs:

* `sh deploy/docker_devserver.sh up -d`
* `sh deploy/docker_devserver.sh logs web --follow`

Reset database:

* `sh deploy/docker_devserver.sh down -v`


Bootstrap environment manually
==============

Dependencies:

* python 3.8
* virtualenv
* build-dependencies for Python (e.g. `apt-get build-dep python3-cffi python3-lxml` requires `deb-src` in `/etc/apt/sources.list`)
* nodejs och npm
* watchman speeds up `manage.py runserver` autoreload. `apt-get install watchman; pip install pywatchman`
* Preferably postgresql, rabbitmq och redis to have the same environment as in products, but development works with SQLite except for multithreaded views
* Ubuntu/Debian oneliner: `apt-get install -y python3-virtualenv python3-venv python3-pip git libldap2-dev build-essential postgresql-client less virtualenvwrapper libsasl2-dev`
  See more details in docker buildfile `deploy/docker/Dockerfile-base`


Virtualenv
----------

Using virtualenvwrapper:
```bash
git clone ssh://git@gitlab.mividas.com:2222/mividas/core.git mividas-core
cd mividas-core
mkvirtualenv core -a "`pwd`"
```

Manually:
```bash
python3 -m virtualenv MividasCore
cd MividasCore
git clone ssh://git@gitlab.mividas.com:2222/mividas/core.git mividas-core
cd mividas-core
source ../bin/activate
pip install -r requirements-dev.txt
pre-commit install -f
pre-commit install -f -t pre-push  # to run tests and check migrations before push
```


Configuration
-------------------

* Create a file called conferencecenter/local\_settings.py using example in conferencecenter/local\_settings\_example.py
* Use `DEBUG = True` for development. This activates livereload for javascript ui, see below


Database
-------
* Use correct settings for `DATABASES`
* Create database tables:
  ```bash
  python manage.py migrate
  python manage.py upgrade_installation
  ```

LDAP
-----

For ldap-login, configure `LDAP_*` in `.env`, see `.env-example`


Start devserver
------------------

```bash

# for development:
python manage.py runserver

# for produktion
../bin/gunicorn conferencecenter.wsgi:application
```

Javascript-UI
--------------

Install dependencies:
```bash
npm ci
```

Start with live reload

```bash
npm run serve
```

React, fontawesome mm is not built anymore and will be removed. To update manually:

```
cd js-ui/deprecated
npm install
npm run build
git add ../../static/distv2 && git commit ../../static/distv2
```

Start celery
----------

Celery is used to schedule functions and run them in the background.

Use either redis or rabbitmq as backend (must be installed as a service on a computer)

Run the combined run server and celery using the following command:

`python manage.py celery_devserver`

To use standalone celery `CELERY_BROKER_URL` must be set in `local\_settings.py` and `CELERY_TASK_ALWAYS_EAGER = False`

Start celery standalone development version by running:

```
pip install watchdog[watchmedo] pyyaml
PYTHONPATH=. watchmedo auto-restart -d . -p '*.py' --recursive -- celery worker -B --pool threads -c 3 -A conferencecenter.celery --loglevel=info -Ofair
```

To manually restart when changes happen:

```
PYTHONPATH=. python3 celery worker -B --pool threads -c 3 -A conferencecenter.celery --loglevel=info -Ofair
```


API-documentation
----------------

For scheduling API, see http://localhost:8006/api/v1/, for all other APIs see http://localhost:8006/json-api/v1/

For PDF export, cairo och pango is required.

Mac:

```
brew install cairo pango
```

Tests
=======

Run tests
--------------

`python manage.py test --settings=conferencecenter.settings_test --parallel=10`

Using sqlite for faster tests during development:
`SQLITE=1 python manage.py test --settings=conferencecenter.settings_test --parallel=10`


Test without DEBUG=True
-------------------

Run in docker: `sh deploy/docker-run/run.sh`

Manually:

`DEBUG = False`

Collect static files (must be done after each change):
```
npm run build
python manage.py collectstatic
```

Run tests for the latest committed git state using `sh deploy/docker_tests.sh`

Exchange PowerShell
-------------------

Start by [installing powershell](https://docs.microsoft.com/en-us/powershell/scripting/install/installing-powershell-core-on-linux?view=powershell-7.1)

This requires libssl1.0, so in Ubuntu 20.04 it's easier to run `sudo snap install powershell --classic`

Install modules:
```
Install-Module -Name ExchangeOnlineManagement -RequiredVersion 2.0.4-Preview6 -AllowPrerelease
```

Log in:
```
Connect-ExchangeOnline
```

To be able to list rooms via EWS, they must be in a RoomList. Add all rooms by running

```
New-DistributionGroup -Name "Conference Rooms" -PrimarySmtpAddress "allrooms@mividasdev.onmicrosoft.com" -RoomList

$ConfRooms = Get-Mailbox -RecipientTypeDetails RoomMailbox | select -ExpandProperty Alias

$ConfRooms | Add-DistributionGroupMember -Identity "Conference Rooms"
```

Set permissions for all rooms
```
$ConfRooms | Set-CalendarProcessing -DeleteComments $false -DeleteSubject $false -RemovePrivateProperty $false -AddOrganizerToSubject $false -ProcessExternalMeetingMessages $true
```

Integration tests
=================

```
RUN_INTEGRATION_TESTS=1 python -m unit shared.tests.integration
```
Docker
======

Build docker images by running `deploy/build_docker.sh`
