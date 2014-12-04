from google.appengine.ext import db
from handlers.signup import SignupHandler
from google.appengine.api import memcache
from handlers.play import Schedule
from handlers.signup import User
from handlers.signup import Log
from handlers.play import current_week
from handlers.play import UserPicks
from handlers.play import Schedule
from handlers.play import Weeks


class StatsHandler(SignupHandler):
	def get(self):
		if not self.user:
			self.redirect_to('login')
		ep = self.earliest_picks()
		lp = self.earliest_picks(1)
		ud = self.underdog_stats()
		mp = self.most_picks()
		ol = self.outliers()
		self.render('stats.html',user=self.user,ep=ep,lp=lp,ud=ud,mp=mp,ol=ol)

	def earliest_picks(self,late = 0):
		early = []
		week = current_week(self)
		for wk in range(week-1):
			if not late:
				pick = UserPicks.all().filter("week =",wk+1).order("created").fetch(1)
			else:
				pick = UserPicks.all().filter("week =",wk+1).order("-created").fetch(2)
			if pick:
				early.append(pick[late])  # Need first for early, second for late to exclude winner
		return early

	def underdog_stats(self):
		week = current_week(self)
		underdogs = {}
		for wk in range(week):
			# Build list of underdogs for week just once
			underdog_list = []
			games = Schedule.all().filter("week =",wk).fetch(17)
			for g in games:
				if g.line < 0:
					underdog_list.append(g.away_team)
				else:
					underdog_list.append(g.home_team)

			# Get user picks
			picks = UserPicks.all().filter("week =",wk).fetch(100)
			for up in picks:
				if up.user.username == "winner":
					continue
				count = 0
				for pick in up.picks:
					if pick in underdog_list:
						count += 1
				if not underdogs.has_key(str(up.user.username)):
					underdogs[str(up.user.username)] = count
				else:
					underdogs[str(up.user.username)] += count
		return underdogs
	
	def most_picks(self):
		picks = Log.all().filter('action =','Submit Picks').fetch(1000)
		users = {}
		for p in picks:
			if users.has_key(str(p.user.username)):
				users[str(p.user.username)] += 1
			else:
				users[str(p.user.username)] = 1
		return users
	
	def outliers(self):
		ol = {}
		return ol
		