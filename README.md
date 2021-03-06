## About this App
[![Build Status](https://travis-ci.org/semenko/gmail-message-retention-reminder.svg?branch=master)](https://travis-ci.org/semenko/gmail-message-retention-reminder) [![Code Climate](https://codeclimate.com/github/semenko/gmail-message-retention-reminder/badges/gpa.svg)](https://codeclimate.com/github/semenko/gmail-message-retention-reminder)

Setting a [Google Apps retention policy](https://support.google.com/a/answer/151128?hl=en) is a good way to keep your inbox manageable, but it can be scary since the policy is applied _without warning_ to your users.

Silently deleting old mail seems pretty uncool, so this app will email users in your domain about any messages that will be deleted due to a retention policy.


Some warnings:

* You *must* set the retention policy manually in `settings.cfg` (there's no Google API to access retention policies).
If you enter a different value than your actual policy, reminders will not be sent (or will be sent unnecessarily).

* Provided with no warranty or security guarantee (see `LICENSE`). Although I use this on some domains, it is likely to break in complex or large setups, silently fail, etc.

## Setup

You can run this app locally by executing `./retention_warning/send_warning.py`. You'll need to configure `secrets.cfg` first -- see the steps below.

After you perform the shared setup requirements, you can either run this on App Engine (suggested) or as a CRON job.

### Shared Setup Requirements

1. Visit https://console.developers.google.com
2. Create a project with a name like "my-organization-retention-warning"
3. Under Overview, search for and enable the APIs "Admin SDK" and "Gmail API"
4. Under Credentials, select "Create Credentials" > "Service Account Key"
5. Select type "New service account" and enter a descriptive name, e.g. `my-domain-retention-warning`
6. Save the .json file in the `retention_warning/` directory (See secrets.cfg.example)
7. Copy secrets.cfg.example to secrets.cfg and fill in the values.
8. Back in the developer console, click "Manage Service Accounts" and find the key you just created
9. Under the options dots, click "Edit" then select "Enable Google Apps Domain-wide Delegation" and enter a name for your app
10. Click "View Client ID" and copy your App ID, e.g. `my-domain-retention-warning@aldine-mail-retention-warning.iam.gserviceaccount.com`
11. Visit https://admin.google.com/ and go to Security > Show More > Advanced Settings > Manage API Client Access
12. Enter the client name `my-domain-retention-warning@your-appengine-name.iam.gserviceaccount.com` and the scopes `https://www.googleapis.com/auth/admin.directory.user.readonly,https://www.googleapis.com/auth/gmail.readonly,https://www.googleapis.com/auth/gmail.compose` and click Authorize.

### Running as a Cron Job

1. Perform the "Shared Setup" steps listed above.
2. `pip install -r requirements.txt`
3. Test this script locally, via `./send_warning.py`
4. Install this as a cron job, e.g. via `/some/path/to/send_warning.py | tee /some/path/to/a.log`


### Running on App Engine

1. Perform the "Shared Setup" steps listed above.
2. `pip install -t lib -r requirements.txt`
3. Test locally (e.g. with the App Engine GUI tools, or by running `./send_warning.py`)
4. Visit https://admin.google.com/ and click the "App Engine Apps" panel
6. Click the "+" for "Add Services" and under "Google App Engine" enter "my-organization-retention-warning" (your app ID). This is needed to restrict access to @yourdomain.com admins.
7. Deploy the app using the GUI tools, or via `appcfg.py --oauth2 -A my-organization-retention-warning update gmail-message-retention-reminder/`

## Authors
**Nick Semenkovich**
+ https://github.com/semenko/
+ https://nick.semenkovich.com/

## License
Copyright 2015-2016, Nick Semenkovich <semenko@alum.mit.edu>

Released under the MIT License. See LICENSE for details.
