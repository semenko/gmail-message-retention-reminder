#!/usr/bin/env python

import logging
import webapp2
from retention_warning import send_warning

class MainHandler(webapp2.RequestHandler):
    def get(self):
        self.response.write('<pre>Last run:<br>')


class JobHandler(webapp2.RequestHandler):
    def get(self):
        logging.info('Running CRON job.')
        self.response.write('<pre>Running CRON job (with email)<br>')

        warning_response = send_warning.run(mail=True)
        self.response.write('<br>'.join(warning_response))

        self.response.write('Done.')


class SilentJobHandler(webapp2.RequestHandler):
    def get(self):
        logging.info('Running silent job with no mail.')
        self.response.write('<pre>Running silent job<br>')

        warning_response = send_warning.run(mail=False)
        self.response.write('<br>'.join(warning_response))

        self.response.write('Done.')


app = webapp2.WSGIApplication([
        ('/', MainHandler),
        ('/tasks/send-mail', JobHandler),
        ('/tasks/run-silently', SilentJobHandler)
], debug=True)
