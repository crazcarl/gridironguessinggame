#!/usr/bin/env python

from webapp2 import WSGIApplication, Route
import re
import os
# Set useful fields
root_dir = os.path.dirname(__file__)
template_dir = os.path.join(root_dir, 'templates')
								
from google.appengine.ext import db


		
# Create the WSGI application and define route handlers
app = WSGIApplication([
	Route(r'/',handler='handlers.play.Play'),
	Route(r'/play',handler='handlers.play.Play',name='play'),
	Route(r'/play/picks',handler='handlers.play.Play',name='picks',handler_method='picks'),
	Route(r'/play/makepicks',handler='handlers.play.PickHandler'),
	Route(r'/signup',handler='handlers.signup.Register', name='signup'),
	Route(r'/login',handler='handlers.signup.LoginHandler',name='login'),
	Route(r'/logout',handler='handlers.signup.LoginHandler',name='logout',handler_method='logout'),
	Route(r'/play/results',handler='handlers.play.ResultsHandler',name='results'),
	Route(r'/admin',handler='handlers.play.AdminHandler', name='admin'),
	Route(r'/play/standings',handler='handlers.play.StandingsHandler', name='standings'),
	Route(r'/play/comments',handler='handlers.comments.ForumHandler', name='forum'),
	Route(r'/play/comments/<thread:\d+>',handler='handlers.comments.ThreadHandler',name='thread'),
	Route(r'/play/settings',handler='handlers.signup.Settings',name='settings'),
	Route(r'/admin/reminders',handler='handlers.mail.MailHandler',name='reminders'),
	Route(r'/reset',handler='handlers.signup.Reset',name='reset'),
	Route(r'/tempstand',handler='handlers.play.TempStandings',name='tempstand'),
	Route(r'/full_results',handler='handlers.results.ResultsHandler',name='full_results'),
	#Route(r'/stats',handler='handlers.stats.StatsHandler',name='stats'),
	Route(r'/cleanup',handler='handlers.Tests.TestHandler',name='cleanup',handler_method='cleanup'),
	Route(r'/iwon',handler='handlers.results.WinHandler',name='winner'),
	# Normally disabled to prevent running in prd.
	#Route(r'/test',handler='handlers.Tests.TestHandler',name='test'),
    #Route(r'/export/picks',handler='handlers.stats.StatsHandler',handler_method='export_picks'),
], debug=False)