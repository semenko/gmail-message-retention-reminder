#!/usr/bin/env python

import base64
import logging
import os
import httplib2
import configparser
import time
import urllib
from datetime import date, timedelta
from functools import wraps

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


###
# Load the configuration parameters
###
THIS_PATH = os.path.dirname(os.path.realpath(__file__))

_CONFIG = configparser.ConfigParser()
_CONFIG.read(THIS_PATH + "/secrets.cfg")

GA_DOMAIN = _CONFIG.get('google', 'domain')
SERVICE_ACCOUNT = _CONFIG.get('google', 'serviceAccount')
SERVICE_ACCOUNT_KEY = _CONFIG.get('google', 'serviceAccountKey')
ADMIN_TO_IMPERSONATE = _CONFIG.get('google', 'adminToImpersonate')
GA_SKIP_USERS = _CONFIG.get('google', 'skipUsers')
RETENTION_DAYS = _CONFIG.getint('google', 'retentionPeriodInDays')
WARNING_DAYS = _CONFIG.getint('google', 'warningPeriodInDays')
CAN_SEND_MAIL = _CONFIG.getboolean('google', 'canSendMail')
###

# Grab the service account .pem or .p12 private key
with open(THIS_PATH + "/" + SERVICE_ACCOUNT_KEY, 'rb') as f:
    SERVICE_SECRET_KEY = f.read()


# Bare-bones (one value) handling of pretty output for CRON vs GAE
class gae_print_handler():
    def __init__(self):
        self.buffer = []

    def write(self, message):
        if RUNNING_ON_GAE:
            self.buffer.append(message)
        else:
            print(message)

    def clear(self):
        self.buffer = []

OUTPUT_BUFFER = gae_print_handler()


# Retry decorator
# Adapted from http://googleadsdeveloper.blogspot.com/2014/09/decorating-your-python-dfp-api.html
def retry(func):
    @wraps(func)
    def function_to_retry(*args, **kwargs):
        tries = 4
        delay = 1
        while tries > 1:
            try:
                return func(*args, **kwargs)
            except Exception, e:
                print('%s, Retrying in %d seconds...' % (str(e), delay))
                time.sleep(delay)
                tries -= 1
                delay *= 2
        return func(*args, **kwargs)
    return function_to_retry


def getDirectoryService(user_to_impersonate):
    """Build and returns a Directory service object authorized with the service accounts
    that act on behalf of the given user.

    Args:
      user_email: The email of the user.
    Returns:
      Directory service object.
    """
    assert(user_to_impersonate.endswith(GA_DOMAIN))

    credentials = SignedJwtAssertionCredentials(
        SERVICE_ACCOUNT,
        SERVICE_SECRET_KEY,
        sub=user_to_impersonate,
        scope=['https://www.googleapis.com/auth/admin.directory.user.readonly']
    )

    http = httplib2.Http()
    http = credentials.authorize(http)

    directory_service = retry(build)('admin', 'directory_v1', http=http)

    return directory_service


def getGmailService(user_to_impersonate):
    """Build and returns a Gmail service object authorized with the service accounts
    that act on behalf of the given user.

    Args:
      user_email: The email of the user.
    Returns:
      Gmail service object.
    """
    assert(user_to_impersonate.endswith(GA_DOMAIN))

    credentials = SignedJwtAssertionCredentials(
        SERVICE_ACCOUNT,
        SERVICE_SECRET_KEY,
        sub=user_to_impersonate,
        scope=['https://www.googleapis.com/auth/gmail.readonly',
               'https://www.googleapis.com/auth/gmail.compose']
    )

    http = httplib2.Http()
    http = credentials.authorize(http)

    gmail_service = retry(build)('gmail', 'v1', http=http)

    return gmail_service


def getAllUsers(directory_service):
    """
    Get a list of all users on the domain

    Via API manual at https://developers.google.com/admin-sdk/directory/v1/reference/#Users

    :param directory_service: A directory service object
    :return: A dictionary of {primaryEmail: givenName}
    """
    OUTPUT_BUFFER.write('Listing all users at %s' % (GA_DOMAIN))
    all_users = []
    page_token = None
    params = {'domain': GA_DOMAIN, 'viewType': 'domain_public'}

    while True:
        try:
            if page_token:
                params['pageToken'] = page_token
            current_page = retry(directory_service.users().list(**params).execute)()

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
            OUTPUT_BUFFER.write('Skipped user: %s' % (user['primaryEmail']))

    OUTPUT_BUFFER.write('Found %d users in domain.' % (len(email_and_name)))
    return email_and_name


def sendWarningMessage(gmail_service, retention_period_in_days, user_email, user_name,
                       message_count, subjects, before_date, suggest_date):
    """
    Send a warning email to a user who has mail that may be deleted.
    """
    # TODO: Clean up this mess.
    logging.debug('Sending message to %s' % user_email)
    subject = "[%s] Warning: Some very old emails will be trashed" % (user_name)

    body = [
        "Your email address (%s) is set to keep messages for %s days (%.2g years).\n" % (user_email, retention_period_in_days, retention_period_in_days / float(365)),
        "You have at least %s messages from before %s that will be deleted over the next month.\n" % (message_count, before_date),
        "Some of the ancient emails to be removed include:\n\n> %s\n\n" % (subjects),
        "You can see the full list of messages at: https://mail.google.com/a/%s/#search/%s\n" % (GA_DOMAIN, urllib.quote_plus('before:%s' % before_date)),
        "Thanks,", "Domain Administrator\n\n",
        "P.S. You'll receive a message like this every month if you have extremely old emails.",
        "Want to clean up now? Try deleting some of these messages: https://mail.google.com/a/%s/#search/%s\n" % (GA_DOMAIN, urllib.quote_plus('before:%s' % suggest_date))
    ]

    body = '\n'.join(body)

    message = 'From: %s\nTo: %s\nSubject: %s\n\n%s' % (user_email, user_email, subject, body)
    encoded_message = base64.urlsafe_b64encode(message)
    params = {'userId': user_email, 'body': {'raw': encoded_message}}

    try:
        sent_message = retry(gmail_service.users().messages().send(**params).execute)()
        OUTPUT_BUFFER.write('Sent message, ID: %s' % sent_message['id'])
    except errors.HttpError, error:
        logging.error('An error occurred: %s' % error)


def run(send_mail=False, retention_period_in_days=RETENTION_DAYS, warning_window_in_days=WARNING_DAYS):
    """
    Look up users, and email a warning if they have super old emails.
    """
    OUTPUT_BUFFER.clear()

    # There's a "warning" period of "hey, this will get deleted"
    # And a "suggest" period of "why not clean out this other old stuff, too?"
    date_before = date.today() - timedelta(days=(retention_period_in_days - warning_window_in_days))  # e.g. subtract 45 d.
    suggest_before = date.today() - timedelta(days=(retention_period_in_days - (365 * 2)))  # Subtract 365*2 for a suggestion email period
    date_string_before = date_before.strftime('%Y/%m/%d')
    suggest_string_before = suggest_before.strftime('%Y/%m/%d')

    directory_service = getDirectoryService(ADMIN_TO_IMPERSONATE)
    all_users = getAllUsers(directory_service)

    OUTPUT_BUFFER.write('Retention set to: %d days' % (retention_period_in_days))
    OUTPUT_BUFFER.write('Before string is: %d days (%s)' % (warning_window_in_days, date_string_before))
    OUTPUT_BUFFER.write('Sending mail: %s' % (send_mail and CAN_SEND_MAIL))

    OUTPUT_BUFFER.write('Looping over users...\n')
    for email, firstName in all_users.iteritems():
        gmail_service = getGmailService(email)

        params = {'userId': email, 'q': 'before:%s' % date_string_before}

        one_page = retry(gmail_service.users().threads().list(**params).execute)()

        size_estimate = one_page['resultSizeEstimate']
        if 'threads' in one_page:
            size_estimate = max(size_estimate, len(one_page['threads']))

        if size_estimate > 0:
            OUTPUT_BUFFER.write('User: %s (%s)' % (email, size_estimate))

            # Cap size to 10
            one_page['threads'] = one_page['threads'][:10]

            thread_params = {'userId': email, 'format': 'metadata',
                             'fields': 'messages/payload/headers', 'metadataHeaders': 'subject'}

            subject_list = []
            for thread in one_page['threads']:
                thread_params['id'] = thread['id']
                one_thread = retry(gmail_service.users().threads().get(**thread_params).execute)()
                first_subject = one_thread['messages'][0]['payload']['headers'][0]['value']
                safer_subject = first_subject.encode('ascii', 'ignore')
                if safer_subject is not "":
                    subject_list.append(safer_subject)
                    OUTPUT_BUFFER.write('\t' + safer_subject)

            if send_mail and CAN_SEND_MAIL:
                sendWarningMessage(gmail_service, retention_period_in_days, email, firstName, size_estimate,
                                   '\n> '.join(subject_list), date_string_before, suggest_string_before)
            OUTPUT_BUFFER.write('')

    OUTPUT_BUFFER.write('Done.')
    return OUTPUT_BUFFER.buffer


if __name__ == "__main__":
    OUTPUT_BUFFER.write('Running...')
    run(send_mail=True)
    OUTPUT_BUFFER.write('Done.')
