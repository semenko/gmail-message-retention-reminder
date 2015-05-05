#!/usr/bin/env python

import cgi
import datetime
import logging
import webapp2

from google.appengine.ext import ndb
from retention_warning import send_warning


class LastRunResult(ndb.Model):
    content = ndb.StringProperty()
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
        self.response.write('<pre>Last runs:\n\n')
        last_run_data = LastRunResult.last_runs(RECORD_KEY).fetch(10)

        for data in last_run_data:
            self.response.write('** %s **\n\n' % (data.date))
            self.response.write('%s\n' % (cgi.escape(data.content)))
            self.response.write('\n\n--------------------------------\n\n')


class JobHandler(webapp2.RequestHandler):
    def get(self):
        self.response.write('<pre>Running CRON job (with email)\n\n')

        warning_response = send_warning.run(mail=True)
        warning_string = '\n'.join(warning_response)
        self.response.write(warning_string)

        storage = LastRunResult(parent=RECORD_KEY,
                                content=warning_string)
        storage.put()


class SilentJobHandler(webapp2.RequestHandler):
    def get(self):
        self.response.write('<pre>Running silent job\n\n')

        warning_response = send_warning.run(mail=False)
        warning_string = '\n'.join(warning_response)
        self.response.write(warning_string)

        storage = LastRunResult(parent=RECORD_KEY,
                                content=warning_string)
        storage.put()


app = webapp2.WSGIApplication(
    [
        ('/', MainHandler),
        ('/tasks/send-mail', JobHandler),
        ('/tasks/run-silently', SilentJobHandler),
        ('/tasks/cleanup', CleanupHandler)
    ], debug=True)
