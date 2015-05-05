gmail-message-retention-reminder
========================
Automatically email domain users when they have messages that will be deleted by a retention policy.

Setting a Google Apps retention policy can be scary, since the policy is applied without warning to your users.
Silently deleting old mail seems pretty uncool -- this app will email all users in your domain about messages that 
will be deleted due to a retention policy.

Features:

* Will e-mail all users with email before a given retention policy date
* Emails users with search links and subjects of sample messages to be deleted
* Can be run as a CRON job, or on Appengine (see below)


Some warnings:

* You *must* set the retention policy manually in `settings.cfg` (there's no Google API to access retention policies).
If you enter a different value than your actual policy, reminders will not be sent (or will be sent unnecessarily).

* Provided with no warranty or security guarantees (see `LICENSE`). Although I use this on some domains, it may break in
complex setups, or silently fail, etc.


## Shared Setup

1. Visit https://console.developers.google.com
2. Create a project with a name like "my-organization-retention-warning"
3. Under APIs and Auth > APIs, search for an enable the "Admin SDK" and "Gmail API"
4. APIs and Auth > Credentials select "Create new Client ID" of type "Service account"
5. Ignore the .json you're served, and instead click "Generate new P12 key"
6. Save the .p12 key somewhere (you'll convert it to a .pem next)
7. Convert to .pem: `openssl pkcs12 -in downloaded.p12 -nodes -nocerts > secret.pem` (password: notasecret)
8. Place the secret.pem in the retention_warning/ directory (See secrets.cfg.example)
9. Copy secrets.cfg.example to secrets.cfg and fill in the values.
10. Visit https://admin.google.com/ and go to Security > Show More > Advanced Settings > Manage API Client Access
11. Enter the client name `the-service-account-client-id-from-your-dev-console.apps.googleusercontent.com` and the scopes `https://www.googleapis.com/auth/admin.directory.user.readonly,https://www.googleapis.com/auth/gmail.readonly,https://www.googleapis.com/auth/gmail.compose` and click Authorize.


## Run as a Cron Job

1. Perform the "Shared Setup" steps listed above.
2. `pip install -r requirements.txt`
3. Test this script locally, via `./send_warning.py`
4. Install this as a cron job, e.g. via `/some/path/to/send_warning.py | tee /some/path/to/a.log`


## Run on Appengine

1. Perform the "Shared Setup" steps listed above.
2. `pip install -t lib -r requirements.txt`
3. Test locally (e.g. with GUI tools, or by running `./send_warning.py`)
4. Deploy the app using the GUI tools, or via `appcfg.py --oauth2 -A my-organization-retention-warning update gmail-message-retention-reminder/`
