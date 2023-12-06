# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.0-X] - UNRELEASED

### Fixed
* Form validation of non-active tab for Pexip call rule editor

### Changed

**Mividas Core**

* Only run LDAP sync of current CMS tenant by default


## [3.0.0-rc4] - [2022-05-31]

### Added


**General**

* Add support for LDAP referral chasing
* Lookup LDAP servers using SRV query
* Extended trace log for all API calls

**Mividas Core**

* Add button to hangup call for Pexip meeting control
* First beta for scheduled RTMP-recording for Pexip meetings
* Update scheduling API documentation

**Mividas Rooms:**

* Support to merge identically named groups in addressbook search
* Add filters and API documentation for endpoint list function

### Fixed

**General**

* Hide All items from pagination from tables that lacks support

**Mividas Core**
* Fix recvc recording
* Display more call control error messages on screen
* Fix error response format for callcontrol API actions
* Fix bulk meeting room creating error handling for Pexip
* Fix setting organization unit for CMS spaces with access methods
* Use the same moderator call profile for all nodes of CMS cluster
* Fix removing scheduled meeting rooms from Portal meeting room list
* Fix recurring meeting example and sync items throughout occurences
* Pexip meeting room excel export using type-filter
* Sending emails to non CMS users when bulk-creating CMS spaces
* Changing PIN code using scheduling API

**Mividas Rooms:**

* Fix restoring configuration from backup file
* Don't display proxy count as new when using non-admin account

### Security

* Upgrade django, openssl, libssl1.1
* Related CVEs: CVE-2022-28346, CVE-2022-28347, CVE-2022-0778

### Changed

**Mividas Core**

* Hide clear chat message from CMS space details view if running v3.1+
* Go to todays call statistics when pressing button on dashboard
* Regenerate CMS secret when changing PIN codes
* Decrease number of API calls to update CMS space
* Change Pexip call route rule header

**Mividas Rooms**

* Hide add new organization unit from systems list - groups without systems is immediatly hidden

## [3.0.0-rc3] - 2022-05-02

### Added

* Display license information on Dashboard

**Mividas Core**:
* Add support to use manual call routing when dialing out to external participants in Pexip meeting
* Support to set canChangeScope permission for CMS meeting room members
* Add support to trigger Pexip ldap user sync using API
* Pre-fill cluster name as default Pexip management node description in onboarding wizard
* Pass recording provider playback-support to Meeting Portal
* Add support for changing basic settings of CMS spaces with externally created access methods

**Mividas Rooms:**
* Add support to bulk provision saved dial settings from Rooms to endpoints
* Add support to bulk provision chained passive provisioning
* Display loading errors on dashboard
* Send MS Graph and EWS sync errors to Error log
* Add setting to use addressbook for Scheduling portal searches
* Save number of items per page for data tables between page navigations
* Display call history from local call statistics for passive endpoints
* Support for syncing external sources to nested subgroup (delimited by >)
* Merge folders with the same name from multiple sources in addressbook search
* Add API endpoint to force addressbook sync
* Log TMS address book sync error, force UTF-8 encoding
* Add API-endpoint for external monitoring of system online status/warnings

### Fixed

* Fix database initialization if using FQDN with over 100 characters
* Fix translation in policy views and macro dialog
* Don't display full html page as error message if raw error is passed to frontend
* Remove empty columns from endpoint debug view error log

**Mividas Core**:
* Don't use number input for lobby pin to allow for PIN-codes starting with 0
* Remove console error message when displaying meeting list as a non-admin user
* Fix pagination of participants for Pexip meetings with over 10 participants
* Fix updating moderator call leg profile settings for CMS meetings when combining it with other properties
* Hide deprecated fields in backend admin, display only relevant cluster types
* Ad-hoc recording/streaming for CMS meetings
* Better error message on chained provisioning errors
* Don't reset streamUrl of CMS Space if RTMP streaming is not enabled
* Automatically sync data of users and cospaces when doing freetext search

**Mividas Rooms:**
* Strip XML namespace from chained passive provision services using tandberg CUIL namespace
* Better connection/response error-handling when updating endpoint status
* Better error handling of disconnecting participants in ongoing meeting list
* Fix using prefilled default SIP proxy password when bulk-provisioning endpoint dial settings
* Fix saving endpoints if changing it from backend admin
* Fix freetext search for address book items in root folder
* Fix rescheduling tasks for next night when last task in particular timezone had errors
* Better error handling for connection errors when updating call statistics from previously offline endpoints
* Fix saving endpoint in backend admin if default protocol is not specified
* Fix omitting null arguments when running commands
* Timestamp for recent Spark calls for Room OS 10
* Use password input for new password field in provisioning view
* Separate offline command definitions for passive systems where the same model uses both TC7 and CE-firmware

### Security
* Upgrade libgmp, zlib1g, libssl, libzma5, gzip
* Related CVEs: CVE-2022-0778, CVE-2021-43618, CVE-2018-25032, CVE-2022-1271

### Changed
* Increase log verbosity for ldap logins
* Allow multiple reverse proxy/load balancer hops when resolving client ip

**Mividas Core**:
* Automatically add moderator permissions to new users of a CMS meeting room if multiple access methods exists
* Use wider fields for number serie input in backend admin
* Include CMS participants without CDR remoteParty-information in call statistics
* Add some jitter to delay of retrying call statistics consolidation to minimize risk of locking issues
* Display more information about access methods for CMS Spaces
* Use limited form to only display fields allowed changing for auto generated CMS spaces

**Mividas Rooms:**
* Log firmware version when called endpoint commands fail
* Automatically disable further calendar sync from expired MS Graph credentials
* Don't set endpoint status to "in call" when display endpoint status until call is connected
* Always display mac address and serial field in endpoint form to be able to replace it with a new one
* Pass endpoint remote IP as X-Forwarded-For to chained provisioning servers to enable geo-location
* Separate task in for room analytics provisioning to filter unsupported settings for each system
* Don't bulk provision room analytics settings for personal systems by default
* Disable change password functionality for passive endpoints - not supported
* Populate MAC/software version from initial passive provision event
* Change checkbox text label for provisioning room controls

## [3.0.0-rc2] - 2022-03-09

### Added

**Mividas Core**:
* API endpoint to rematch call statistics tenants from number series
* Add CMS meeting room owner as member for new rooms
* Include CMS error cause for failed API calls - e.g. invalid user id, duplicate uri
* Add placeholder codes for Pexip desktop client in invite messages
* Add flag to include moderator joining details in scheduling API to decrease number of API calls
* Send more API errors from calls to external systems (e.g. MCUs) to Error log
* Display more error information when bulk-creating Pexip meeting rooms
* Display customer name of scheduled meeting if using multi-tenant search

**Mividas Rooms:**
* Support for getting provisioning data from external passive provisioning server

### Fixed
* Reset user session if currently selected customer is removed
* Remove console log for missing favicon

**Mividas Core**:
* Fix disabling rows in bulk create form
* Use callId as lobby user for CMS meeting rooms without set uri
* Force including CMS tenant in next object sync if newly created or when scheduling meetings
* Fix webinar moderator permission if empty lobby pin is included in scheduling API
* Fix placeholder codes for moderator webinar invite messages
* Fix updating CMS meeting rooms when using dialog from meeting room list, pre-set existing PIN code
* Fix translations in excel export

**Mividas Rooms:**
* Remove console warning in organization tree view
* Fix endpoint proxy-client empty password in multi-tenant Rooms installations
* Prefill default sip proxy settings when provisioning multiple endpoints
* Bulk provisioning missing endpoint device aliases to Pexip Infinity

### Security
* Upgrade libexpat1
* Related CVEs: CVE-2022-23852 CVE-2022-25235 CVE-2022-25236 CVE-2022-25313 CVE-2022-25315

### Changed

**Mividas Core**:
* Display error message containing reason for failed CMS meeting room creation
* Better label for CMS tenant API key field in new tenant form

**Mividas Rooms:**
* Open endpoint web admin interface in new window
* Set default passive provision heartbeat to 7 minutes (activated endpoint still use < 1 min)
* Reject invalid SMTP recipient domains instead of silently discarding emails
* Hide call id generation field when editing existing meeting room
* Display password indicator in provision dialog if default sip proxy password is set
* Only allow selecting one endpoint when filtering statistics instead of silently ignoring extra ones

## [3.0.0-rc1] - 2022-02-10

### Added

* Audit and Error-log in debug view
* Improve API schema documentation
* Display progress log while waiting for data layers to start up on deploy

**Mividas Core**:
* Support for changing meeting room pin code from Mividas Portal
* Support for setting Pexip meeting room layout
* Support for moderator layout for CMS, Pexip and scheduled meetings
* Increase console log verbosity
* Fix incremental pagination for Pexip call statistics sync
* Basic support for automatic multi-tenant self-management from user ldap attributes

**Mividas Rooms:**
* Support to identify Pexip service registered endpoints
* Support for chained passive provisioning service
* Display more information in backend admin
* Add support to requiring shared key before adding Rooms Proxy client
* Support for collecting air quality, temperature and humidity from endpoints with sensors that allow it
* More interactive help texts for EWS and Microsoft Graph calendar integration
* Support for Rooms addressbook search in Mividas Portal and connecting with users private endpoint
* Support disabling OBTP function for a customer
* Detect webex registered endpoints and disable some dial settings
* Display endpoint MAC address in details view
* Display call status in call history list

### Fixed

**Mividas Core**:
* Correct order of debug call statistics tab and content
* Populate owner name and email for scheduled Pexip meetings
* Validating of policy auth source field
* Better support for handling pruned endpoint history data
* Allow submitting Pexip Infinity onboarding-wizard form without preparing event sink and policy configurations
* Moving Pexip user to default tenant for multi-cluster installations
* Fix displaying self-management call statistics in multi cluster environments if user only belongs to default tenant of a cluster

**Mividas Rooms:**
* Fix Endpoint statistics view in mobile browser
* Don't allow connecting scheduled meeting to endpoint before it is approved
* Increase timeout for uploading branding files to allow for larger images over low bandwidth
* Mark tasks for removed endpoints as cancelled
* Fix some translations
* Don't send out empty scheduled meeting list to endpoints if no meetings have been scheduled in Rooms
* Use correct Excel file extension for debug report
* Fix removing room controls
* Fix endpoint online filter
* Update call status for passive endpoints
* Reset endpoint head count when is goes offline
* Fix parsing call history from Room OS 10 systems

### Security
* Lock out user/IP during bruteforce login attempt
* Run containers with read only root file system where possible
* Add option to disable local accounts if ldap is being used
* Add option to enable certificate validation for MCU nodes
* Upgrade Django, celery and lxml backend libraries
* Upgrade frontend javascript libraries
* Related CVEs: CVE-2021-23727 CVE-2022-23833 CVE-2021-45116 CVE-2021-45115

### Changed

* More consistent UI page actions/search
* Remove points from room analytics graph
* Better handling of default language when user browser does not support any of the available languages
* Increase gap between soft- and hard limit for backend tasks to decrease number of force-killed processes

**Mividas Core**:
* Join call participants for ended distributed calls to a merged one in a background task instead of when receiving event
* Display user profile icon for user/logout menu
* Hide sections from backend admin and API documentation that are not available in license
* Handle incoming CDR data and endpoint events in background task instead of when receiving event
* Allow adding management node to empty Pexip clusters
* Allow adding more VCS nodes to cluster

**Mividas Rooms:**
* Decrease initial connection timeout value for endpoint API requests
* New UI for handling branding profiles
* Better navigation between items in debug log views and single endpoint debug tables
* Better multithreading of updating endpoint status
* Display help texts when people count sensor is disabled (e.g. sleep mode)
* Reload more data on endpoint dashboard if button is pressed
* Reload call history when call status changes
* Use single endpoint provision dialog if only one endpoint is selected in system list
