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
3. APIs and Auth > Credentials select "Create new Client ID" of type "Service account"
4. Ignore the .json you're served, and instead click "Generate new P12 key"
5. Save the .p12 key somewhere (you'll convert it to a .pem next)
6. Convert to .pem: `openssl pkcs12 -in downloaded.p12 -nodes -nocerts > secret.pem` (password: notasecret)
7. Place the secret.pem in the retention_warning/ directory (See secrets.cfg.example)
8. Copy secrets.cfg.example to secrets.cfg and fill in the values.


## Run as a Cron Job

1. Perform the "Shared Setup" steps listed above.
2. `pip install -r requirements.txt`
3. 


## Run on Appengine

1. Perform the "Shared Setup" steps listed above.
2. `pip install -t lib -r requirements.txt`
3. Deploy the app using: ``
4.