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
	Route(r'/play/standings',handler='handlers.play.StandingsHandler', name='standings')
], debug=True)