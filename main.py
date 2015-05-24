#!/usr/bin/env python

import cgi
import datetime
import webapp2

from google.appengine.ext import ndb
from retention_warning import send_warning


class LastRunResult(ndb.Model):
    content = ndb.TextProperty()
    date = ndb.DateTimeProperty(auto_now_add=True)

    @classmethod
    def last_runs(cls, ancestor_key):
        return cls.query(ancestor=ancestor_key).order(-cls.date)

    @classmethod
    def cleanup(cls):
        oldest_date = datetime.datetime.now() - datetime.timedelta(days=90)
        oldest_keys = cls.query(cls.date <= oldest_date).fetch(keys_only=True)
        ndb.delete_multi(oldest_keys)


RECORD_KEY = ndb.Key(LastRunResult, 'last')


class CleanupHandler(webapp2.RequestHandler):
    def get(self):
        self.response.write('<pre>Removing old values.\n')
        LastRunResult.cleanup()
        self.response.write('\nDone.')


class MainHandler(webapp2.RequestHandler):
    def get(self):
        self.response.write('<a href="/tasks/run-silently">/tasks/run-silently</a> or /tasks/send-mail<br><br>')
        self.response.write('Retention period: %d days<br><hr>' % (send_warning.RETENTION_DAYS))
        self.response.write('<pre>Last runs:\n\n')
        last_run_data = LastRunResult.last_runs(RECORD_KEY).fetch(10)

        for data in last_run_data:
            self.response.write('** %s **\n\n' % (data.date))
            self.response.write('%s\n' % (cgi.escape(data.content)))
            self.response.write('\n\n--------------------------------\n\n')


def run_warning_and_save_output(should_send_mail, retention_time=None):
    """
    Run the warning script and save the output.
    :param mail: Send mail? Boolean.
    :return: String of results object.
    """
    if retention_time is not None:
        warning_response = send_warning.run(send_mail=should_send_mail, retention_period_in_days=int(retention_time))
    else:
        warning_response = send_warning.run(send_mail=should_send_mail)
    warning_string = '\n'.join(warning_response)

    # Save the result
    storage = LastRunResult(parent=RECORD_KEY,
                            content=warning_string)
    storage.put()

    return warning_string


class JobHandler(webapp2.RequestHandler):
    def get(self, retention_time=None):
        self.response.write('<pre>Running CRON job (with email)\n\n')
        warning_string = run_warning_and_save_output(should_send_mail=True, retention_time=retention_time)
        self.response.write(warning_string)


class SilentJobHandler(webapp2.RequestHandler):
    def get(self, retention_time=None):
        self.response.write('<pre>Running silent job\n\n')
        warning_string = run_warning_and_save_output(should_send_mail=False, retention_time=retention_time)
        self.response.write(warning_string)


app = webapp2.WSGIApplication(
    [
        ('/', MainHandler),
        ('/tasks/send-mail', JobHandler),
        ('/tasks/send-mail/(\d+)', JobHandler),
        ('/tasks/run-silently', SilentJobHandler),
        ('/tasks/run-silently/(\d+)', SilentJobHandler),
        ('/tasks/cleanup', CleanupHandler)
    ], debug=True)
