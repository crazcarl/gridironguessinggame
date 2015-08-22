#from handlers.base import AppHandler
from google.appengine.ext import db
import datetime
from handlers.signup import SignupHandler
from google.appengine.api import memcache
from handlers.play import Schedule
from handlers.signup import User
from pytz.gae import pytz
from handlers.signup import Log
from handlers.play import current_week
from handlers.play import UserPicks
from handlers.play import Schedule
from handlers.play import Weeks
from handlers.play import picks_enabled
from handlers.helper import teamToShort
from handlers.play import get_current_winners
from handlers.play import FrontPost
from handlers.play import Results

ARIZONA = pytz.timezone('US/Arizona')




class ResultsHandler(SignupHandler):
	def get(self):
		if not self.user:
			self.redirect_to('login')
		# If week selected by user, use that. Otherwise, use current week
		week = ""
		if self.request.get("weekselection"):
			week = int(self.request.get("weekselection"))
		if not week:
			week=current_week(self)
		if not week or week == 0:
			self.redirect_to('play')
			return None
		
		# Only show results after cutoff date
		# cutoff_date = current_week(self,return_val=1)
		wk = Weeks.all().filter("week =",week).get()
		if wk:
			cutoff_date = wk.cutoff
			show_results = picks_enabled(self,cutoff_date)
		else:
			show_results = ""
			cutoff_date = ""
		
		if not show_results:
			# Display message about results
			self.render('full_results.html',message = "Results for week " + str(week) +" are not available until after cutoff date",user = self.user,week=week)
			return None	
			
			
		games = Schedule.all().filter('week =',week).order('game').fetch(17)
		if not games:
			self.render('full_results.html',user=self.user,message="No games loaded for this week")
			return none
		gamelist=[]
		for g in games:
			gamelist.append([teamToShort(g.home_team),teamToShort(g.away_team)])
		users = User.all().fetch(1000)
		results = []
		w_picks = []
		count = 0
		for u in users:
			up = UserPicks.all().filter('week =',week).filter('user =',u).get()
			if not up:
				continue
			if up.user.username == "winner":
				w_picks = up.picks
				continue
			result = [u.username]
			picks = up.picks
			for g in games:
				if g.home_team in picks:
					result.append(teamToShort(g.home_team))
				else:
					result.append(teamToShort(g.away_team))
			result.append(picks[-1])
			results.append(result)

		if not w_picks:
			w_picks = get_current_winners(self)
		if w_picks:
			w_picks = [ teamToShort(x) for x in w_picks ]
			self.render('full_results.html',user=self.user,games=gamelist,results=results,w_picks=w_picks,week=week)
		else:
			self.render('full_results.html',user=self.user,games=gamelist,results=results,week=week)
			
class WinHandler(SignupHandler):
	def get(self):
		if not self.user:
			self.redirect_to('login')
		
		if self.verify_winner():
			self.render('iwon.html',user=self.user)
			return None
		
		self.redirect_to('play')
		
	def post(self):
		if not self.user:
			self.redirect_to('login')
			
		win_wk = self.verify_winner()
		if not win_wk:
			self.redirect_to('play')
			return None
			
		image = self.request.get("imageLink")
		if not image:
			#TODO: Update with fail msg
			self.render('iwon.html',user=self.user)
			return None
		
		p = FrontPost.all().filter("week =",win_wk).filter("user =",self.user).filter("winner =",1).get()
		if p:
			p.content = image
		else: 
			p = FrontPost(user=self.user,
						title="Winner for week 1",
						content=image,
						winner=1,
						week=win_wk)
		p.put()
		memcache.set("front_posts","")
		self.render('iwon.html',user=self.user,message="got it!")
		
	def verify_winner(self):
		week=current_week(self)
		if not week:
			self.redirect_to('play')
			return 0
			
		# Try the current week first to see if they are posting right after winning
		won = Results.all().filter('week =',week).filter('winner =',1).filter('user =',self.user).get()
		if won:
			return week
		
		# Then try the previous week
		won = Results.all().filter('week =',week-1).filter('winner =',1).filter('user =',self.user).get()
		if won:
			return week-1
		
		