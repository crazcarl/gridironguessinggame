from handlers.signup import SignupHandler
from handlers.signup import User
from main import root_dir
from google.appengine.ext import db
import datetime
import random
from pytz.gae import pytz
from handlers.play import Weeks
from handlers.play import UserPicks
from handlers.play import Results
from handlers.play import Schedule
from handlers.play import calc_results
from handlers.play import current_week
from google.appengine.api import memcache
import time
from handlers.play import check_previous_weeks

ARIZONA = pytz.timezone('US/Arizona')

class TestHandler(SignupHandler):
	def get(self):
		if not self.user:
			self.redirect_to('login')
			return None
		admin = self.user.admin
		if not admin:
			self.redirect_to('play')
			return None
		else:
			message = datetime.datetime.now(ARIZONA)
			self.render('test.html',user=self.user,message=message)
	
	# Various testing scenarios
	def post(self):
		type=self.request.get('type')
		message = ""
		
		if type == "simulation":
			message = self.simulate()
		
		if type == "winners":
			message = self.winners()
		
		if type == "setup":
			message = self.setup()
		
		if type == "picks":
			message = self.picks_and_results()
			
		if type == "advance":
			message = self.advance()
			
		# TODO:
		# 1. Too many games for a week (schedule loaded in 2x or badly)
		# 2. User has more than 1 selection of picks for a week
		# 3. 

		
		self.render('test.html',user=self.user,message=message)
	
	# Full Season Simulation. Wipes out most data.
	def simulate(self):
		# First, Delete out:
		#  1. Weeks
		self.delete_weeks()
		#  2. Userpicks
		self.delete_picks()
		#  3. Results
		self.delete_results()
		#  4. Schedule
		self.delete_sched()
		
		
		#Next, clear memcache
		memcache.flush_all()
		
		for w in range(16):
			# Next, set week to 1
			self.set_week(w+1)
			
			# Next, load in schedule
			self.set_schedule(w+1)
			
			# Let Schedule catch up before posting picks
			time.sleep(1)
			
			# Next, make some picks
			self.make_picks(w+1,'crazcarl2')
			self.make_picks(w+1,'crazcarl3')
			self.make_picks(w+1,'crazcarl')
			
			# Next, make the winner picks
			self.make_picks(w+1,'winner')
			time.sleep(2)
			
			# Next, calculate results
			calc_results(self,w+1)
			self.delete_weeks()
		# Next, set the current week to 2 so we can see standing:
		self.set_week(17)
		message = "simulation successful"
		return message
	
	# Loops through results and make sure winners has top score (or at least tied for top score)
	def winners(self):
		r = Results.all().order("-week").get()
		weeks = r.week
		message = ""
		if not weeks or weeks<1:
			message = "No results found for valid week"
		
		if message:
			return message
		
		for w in range(weeks):
			results=Results.all().filter("week =", w+1).order("-wins").fetch(1000)
			wins = -1
			marked_winner = -1
			for r in results:
				if wins == -1:
					wins = r.wins
				if r.winner == 1:
					marked_winner = r.wins
					break
			if wins <> marked_winner:
				message += "Marked winner has " + str(marked_winner) + " wins, while top wins were " + str(wins) + " for week " + str(r.week) + ".\n"
			
			if message:
				return message
	
	# Starts season over. Loads in picks to get ready for week 1
	def setup(self):
		# First, Delete out:
		#  1. Weeks
		self.delete_weeks()
		#  2. Userpicks
		self.delete_picks()
		#  3. Results
		self.delete_results()
		#  4. Schedule
		self.delete_sched()
		
		
		#Next, clear memcache
		memcache.flush_all()		
		

		
		# Next, set week to 1
		self.set_week(1)
			
		# Next, load in schedule
		self.set_schedule(1)
		
		message = "Season setup and ready to go, current week is 1"
		return message
		
	def picks_and_results(self):
		# Grab the current week
		w = current_week(self)
		
		# Next, make some picks
		self.make_picks(w,'crazcarl2')
		self.make_picks(w,'crazcarl3')
		self.make_picks(w,'crazcarl')
		
		# Change the week so results page can be seen:
		self.set_week(w,1)
		time.sleep(1)
		
		# Next, make the winner picks
		self.make_picks(w,'winner')
		time.sleep(2)
		
		# Next, calculate results
		calc_results(self,w)
		
		memcache.set("weeks","")
		
		message = "Results are ready to view for week " + str(w)
		return message
		
	def advance(self):
		# Grab the current week
		w = current_week(self)
		memcache.set("weeks","")
		
		self.set_week(w+1)
		self.set_schedule(w+1)
		message = "Week " + str(w+1) + " is ready for picks!"
		return message
		
	def delete_weeks(self):
		weeks = Weeks.all().fetch(100)
		for w in weeks:
			w.delete()
	def delete_picks(self):
		picks = UserPicks.all().fetch(1000)
		for p in picks:
			p.delete()
	def delete_results(self):
		results = Results.all().fetch(1000)
		for r in results:
			r.delete()
	def delete_sched(self):
		sched = Schedule.all().fetch(1000)
		for s in sched:
			s.delete()
	
	#option = 0/"" Set week so start date = today
	#option = 1    Set week so end date = today
	def set_week(self,week,option = ""):
		self.delete_weeks()
		today2 = datetime.datetime.now(ARIZONA)
		y = today2.year
		m = today2.month
		d = today2.day
		if not option:
			today = datetime.date(y,m,d)
			tomorrow = today + datetime.timedelta(days=1)
			next = today + datetime.timedelta(days=2)
		else:
			today = datetime.date(y,m,d) - datetime.timedelta(days=2)
			tomorrow = datetime.date(y,m,d) - datetime.timedelta(days=1)
			next = datetime.date(y,m,d)			
		weeks = Weeks(week=week,start=today,end=next,cutoff=tomorrow)
		weeks.put()
	
	def set_schedule(self,week):
		teams=['Buffalo','Miami','New England','NY Jets',
			'Baltimore','Cincinnati','Cleveland','Pittsburg',
			'Houston','Indianapolis','Jacksonville','Tennessee',
			'Denver','Kansas City','Oakland','San Diego',
			'Dallas','NY Giants','Philadelphia','Washington',
			'Chicago','Detroit','Green Bay','Minnesota',
			'Atlanta','Carolina','New Orleans','Tampa Bay',
			'Arizona','St. Louis','San Francisco','Seattle']
		random.shuffle(teams)
		game_num = 0
		for game in range(16):
			home_team = teams.pop()
			away_team = teams.pop()
			line = random.uniform(-10,10)
			sched = Schedule(week=week,home_team=home_team,away_team=away_team,line=line,game=game_num)
			sched.put()
			game_num += 1
			
	def make_picks(self,week,user):
		sched = Schedule.all().filter("week =",int(week)).fetch(17)
		sched = list(sched)
		picks = []
		for game in sched:
			team = random.randint(0,1)
			if team:
				pick = game.home_team
			else:
				pick = game.away_team
			picks.append(pick)
		line = str(random.randint(0,10))
		picks.append(line)
		u = User.by_name(user)
		up = UserPicks(week=week,user=u,picks=picks)
		up.put()
		