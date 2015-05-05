#!/usr/bin/env python

import base64
import logging
import os
import httplib2
import configparser
import urllib
from datetime import date, timedelta

from apiclient import errors
from apiclient.discovery import build
from oauth2client.client import SignedJwtAssertionCredentials

# Fix 'six' import errors in OS X
import platform
if platform.system() == "Darwin":
    import sys
    sys.path.insert(1, '/Library/Python/2.7/site-packages')

# Print logging to console
# logging.getLogger().setLevel(logging.INFO)

RUNNING_ON_GAE = 'SERVER_SOFTWARE' in os.environ

# Bare-bones (one value) handling of pretty output for CRON vs GAE
GAE_OUTPUT_BUFFER = []
def print_wrapper(val):
    if RUNNING_ON_GAE:
        GAE_OUTPUT_BUFFER.append(val)
    else:
        print(val)


# Load our configuration
THIS_PATH = os.path.dirname(os.path.realpath(__file__))

_CONFIG = configparser.ConfigParser()
_CONFIG.read(THIS_PATH + "/secrets.cfg")

GA_DOMAIN = _CONFIG.get('google', 'domain')
SERVICE_ACCOUNT = _CONFIG.get('google', 'serviceAccount')
SERVICE_ACCOUNT_KEY = _CONFIG.get('google', 'serviceAccountKey')
ADMIN_TO_IMPERSONATE = _CONFIG.get('google', 'adminToImpersonate')
GA_BLACKLISTED_USERS = _CONFIG.get('google', 'blacklistedUsers')
GA_SKIP_USERS = _CONFIG.get('google', 'skipUsers')
RETENTION_DAYS = _CONFIG.getint('google', 'retentionPeriodInDays')
CAN_SEND_MAIL = _CONFIG.getboolean('google', 'canSendMail')


# Grab the service account .pem or .p12 private key
with open(THIS_PATH + "/" + SERVICE_ACCOUNT_KEY, 'rb') as f:
    SERVICE_SECRET_KEY = f.read()


def getDirectoryService(user_to_impersonate):
    """Build and returns a Directory service object authorized with the service accounts
    that act on behalf of the given user.

    Args:
      user_email: The email of the user.
    Returns:
      Directory service object.
    """
    assert(user_to_impersonate.endswith(GA_DOMAIN))
    assert(user_to_impersonate not in GA_BLACKLISTED_USERS)

    credentials = SignedJwtAssertionCredentials(
        SERVICE_ACCOUNT,
        SERVICE_SECRET_KEY,
        sub=user_to_impersonate,
        scope=['https://www.googleapis.com/auth/admin.directory.user.readonly']
    )

    http = httplib2.Http()
    http = credentials.authorize(http)

    return build('admin', 'directory_v1', http=http)


def getGmailService(user_to_impersonate):
    """Build and returns a Gmail service object authorized with the service accounts
    that act on behalf of the given user.

    Args:
      user_email: The email of the user.
    Returns:
      Gmail service object.
    """
    assert(user_to_impersonate.endswith(GA_DOMAIN))
    assert(user_to_impersonate not in GA_BLACKLISTED_USERS)

    credentials = SignedJwtAssertionCredentials(
        SERVICE_ACCOUNT,
        SERVICE_SECRET_KEY,
        sub=user_to_impersonate,
        scope=['https://www.googleapis.com/auth/gmail.readonly',
               'https://www.googleapis.com/auth/gmail.compose']
    )

    http = httplib2.Http()
    http = credentials.authorize(http)

    return build('gmail', 'v1', http=http)


def getAllUsers(directory_service):
    """
    Get a list of all users on the domain

    Via API manual at https://developers.google.com/admin-sdk/directory/v1/reference/#Users

    :param directory_service: A directory service object
    :return: A dictionary of {primaryEmail: givenName}
    """
    print_wrapper('Listing all users at %s' % (GA_DOMAIN))
    all_users = []
    page_token = None
    params = {'domain': GA_DOMAIN, 'viewType': 'domain_public'}

    while True:
        try:
            if page_token:
                params['pageToken'] = page_token
            current_page = directory_service.users().list(**params).execute()

            all_users.extend(current_page['users'])
            page_token = current_page.get('nextPageToken')
            if not page_token:
                break
        except errors.HttpError as error:
            logging.error('An error occurred: %s' % error)
            break

    email_and_name = {}
    for user in all_users:
        if str(user['primaryEmail']) not in GA_SKIP_USERS:
            email_and_name[user['primaryEmail']] = user['name']['givenName']
        else:
            print_wrapper('Skipped user: %s' % (user['primaryEmail']))

    print_wrapper('Found %d users in domain.' % (len(email_and_name)))
    return email_and_name


def sendWarningMessage(gmail_service, user_email, user_name, message_count, subjects, before_date, suggest_date):
    """
    Send a warning email to a user who has mail that may be deleted.
    """
    # TODO: Clean up this mess.
    logging.debug('Sending message to %s' % user_email)
    subject = "[%s] Warning: Some very old emails will be trashed" % (user_name)

    body = [
        "Your email address (%s) is set to keep messages for %s days (%.4g years).\n" % (user_email, RETENTION_DAYS, RETENTION_DAYS / float(365)),
        "You have at least %s messages from before %s that will be trashed over the next month.\n" % (message_count, before_date),
        "Some of the ancient emails to be removed include:\n\n> %s\n\n" % (subjects),
        "You can see the full list of messages at: https://mail.google.com/a/%s/#search/%s\n" % (GA_DOMAIN, urllib.quote_plus('before:%s' % before_date)),
        "Thanks,", "Domain Administrator\n\n",
        "P.S. You'll receive a message like this every Monday if you have extremely old emails -- they really slow down your mailbox!",
        "Want to clean up now? Try deleting some of these messages: https://mail.google.com/a/%s/#search/%s\n" % (GA_DOMAIN, urllib.quote_plus('before:%s' % suggest_date))
    ]

    body = '\n'.join(body)

    message = 'From: %s\nTo: %s\nSubject: %s\n\n%s' % (user_email, user_email, subject, body)
    encoded_message = base64.urlsafe_b64encode(message)
    params = {'userId': user_email, 'body': {'raw': encoded_message}}

    try:
        sent_message = gmail_service.users().messages().send(**params).execute()
        print_wrapper('Sent message, ID: %s' % sent_message['id'])
    except errors.HttpError, error:
        logging.error('An error occurred: %s' % error)


def run(mail=False):
    """
    Look up users, and email a warning if they have super old emails.
    """
    # There's a "warning" period of "hey, this will get deleted"
    # And a "suggest" period of "why not clean out this other old stuff, too?"
    date_before = date.today() - timedelta(days=(RETENTION_DAYS - 30))  # Subtract 30 for a warning period
    suggest_before = date.today() - timedelta(days=(RETENTION_DAYS - (365 * 2)))  # Subtract 365*2 for a suggestion email period
    date_string_before = date_before.strftime('%Y/%m/%d')
    suggest_string_before = suggest_before.strftime('%Y/%m/%d')

    directory_service = getDirectoryService(ADMIN_TO_IMPERSONATE)
    all_users = getAllUsers(directory_service)

    print_wrapper('Retention set to: %d days' % (RETENTION_DAYS))
    print_wrapper('Before string is: %s' % (date_string_before))
    print_wrapper('Sending mail: %s' % (mail and CAN_SEND_MAIL))

    print_wrapper('Looping over users...')
    for email, firstName in all_users.iteritems():
        gmail_service = getGmailService(email)

        params = {'userId': email, 'q': 'before:%s' % date_string_before}
        one_page = gmail_service.users().threads().list(**params).execute()

        size_estimate = one_page['resultSizeEstimate']
        if 'threads' in one_page:
            size_estimate = max(size_estimate, len(one_page['threads']))

        if size_estimate > 0:
            print_wrapper('User: %s (%s)' % (email, size_estimate))

            # Cap size to 15
            one_page['threads'] = one_page['threads'][:15]

            thread_params = {'userId': email, 'format': 'metadata',
                             'fields': 'messages/payload/headers', 'metadataHeaders': 'subject'}

            subject_list = []
            for thread in one_page['threads']:
                thread_params['id'] = thread['id']
                one_thread = gmail_service.users().threads().get(**thread_params).execute()
                first_subject = one_thread['messages'][0]['payload']['headers'][0]['value']
                safer_subject = first_subject.encode('ascii', 'ignore')
                if safer_subject is not "":
                    subject_list.append(safer_subject)
                    print_wrapper('\t' + safer_subject)

            if mail and CAN_SEND_MAIL:
                sendWarningMessage(gmail_service, email, firstName, size_estimate, '\n> '.join(subject_list), date_string_before, suggest_string_before)
            print_wrapper('')

    return GAE_OUTPUT_BUFFER


if __name__ == "__main__":
    print_wrapper('Running...')
    run(mail=True)
    print_wrapper('Done.')
