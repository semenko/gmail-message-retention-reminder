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
        self.response.write('<pre><a href="/tasks/run-silently">/tasks/run-silently</a>/(retention_days)/(warning_days)\n\n')
        self.response.write('or /tasks/send-mail...\n\nSettings:\n')
        self.response.write(' Domain: %s\n' % (send_warning.GA_DOMAIN))
        self.response.write(' Retention period: %d days\n' % (send_warning.RETENTION_DAYS))
        self.response.write(' Warning period: %d days\n' % (send_warning.WARNING_DAYS))
        self.response.write(' Can send mail?: %r\n<hr>\n' % (send_warning.CAN_SEND_MAIL))
        last_run_data = LastRunResult.last_runs(RECORD_KEY).fetch(10)

        for data in last_run_data:
            self.response.write('** %s **\n\n' % (data.date))
            self.response.write('%s\n' % (cgi.escape(data.content)))
            self.response.write('\n\n--------------------------------\n\n')


def run_warning_and_save_output(*args, **kwargs):
    """
    Run the warning script and save the output.
    """
    warning_response = send_warning.run(*args, **kwargs)
    warning_string = '\n'.join(warning_response)

    # Save the result
    storage = LastRunResult(parent=RECORD_KEY,
                            content=warning_string)
    storage.put()

    return warning_string


class JobHandler(webapp2.RequestHandler):
    def get(self, **kwargs):
        should_send_mail = False
        if 'send-mail' in str(kwargs['taskType']):
            #should_send_mail = True

        # Drop the taskType parameter so we can pass raw kwargs to run()
        del(kwargs['taskType'])
        # Convert all the values to INTs
        kwargs = dict((k, int(v)) for k, v in kwargs.iteritems())

        self.response.write('<pre>')
        warning_string = run_warning_and_save_output(send_mail=should_send_mail, **kwargs)
        self.response.write(warning_string)


app = webapp2.WSGIApplication(
    [
        webapp2.Route('/', MainHandler),
        webapp2.Route('/tasks/<taskType:(send-mail|run-silently)>', JobHandler),
        webapp2.Route('/tasks/<taskType:(send-mail|run-silently)>/<retention_period_in_days:\d+>', JobHandler),
        webapp2.Route('/tasks/<taskType:(send-mail|run-silently)>/<retention_period_in_days:\d+>/<warning_window_in_days:\d+>', JobHandler),
        webapp2.Route('/tasks/cleanup', CleanupHandler)
    ], debug=False)
