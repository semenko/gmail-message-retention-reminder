#!/usr/bin/env python

import cgi
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

class MainHandler(webapp2.RequestHandler):
    def get(self):
        self.response.write('<pre>Last runs:\n\n')
        last_key = ndb.Key(LastRunResult, 'last')
        last_run_data = LastRunResult.last_runs(last_key).fetch(20)

        for data in last_run_data:
            self.response.write('%s\n' % (cgi.escape(data)))
            self.response.write('\n\n--------------------------------\n\n')



class JobHandler(webapp2.RequestHandler):
    def get(self):
        logging.info('Running CRON job.')
        self.response.write('<pre>Running CRON job (with email)\n\n')

        warning_response = send_warning.run(mail=True)

        storage = LastRunResult(parent=ndb.Key(LastRunResult, 'last'),
                                content = warning_response)
        storage.put()

        self.response.write('\n'.join(warning_response))
        self.response.write('Done.')


class SilentJobHandler(webapp2.RequestHandler):
    def get(self):
        logging.info('Running silent job with no mail.')
        self.response.write('<pre>Running silent job\n\n')

        warning_response = send_warning.run(mail=False)

        storage = LastRunResult(parent=ndb.Key(LastRunResult, 'last'),
                                content = warning_response)
        storage.put()

        self.response.write('\n'.join(warning_response))
        self.response.write('Done.')


app = webapp2.WSGIApplication([
        ('/', MainHandler),
        ('/tasks/send-mail', JobHandler),
        ('/tasks/run-silently', SilentJobHandler)
], debug=True)
