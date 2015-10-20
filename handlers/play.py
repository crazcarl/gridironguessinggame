import csv
import os
from main import root_dir
from google.appengine.ext import db
import datetime
from handlers.signup import SignupHandler
from google.appengine.api import memcache
from handlers.signup import User
from pytz.gae import pytz
from google.appengine.api import mail
import time
from handlers.signup import Log
from handlers.comments import Thread,Post
from google.appengine.api import urlfetch
import xml.etree.ElementTree as ET
from handlers.helper import teamToLong
from handlers.signup import Cash

ARIZONA = pytz.timezone('US/Arizona')

class Play(SignupHandler):
	def get(self):
		posts = memcache.get("front_posts")
		if not posts:
			posts = FrontPost.all().order("-created").fetch(25)
			memcache.set("front_posts",posts)
		self.render('play.html',user=self.user,posts=posts)
	
	def picks(self):
		if not self.user:
			self.redirect_to('login')
			return None
		
		week = current_week(self)
		if not week or week==0:
			self.redirect_to('play')
			return None
			
		# See if user already picked this week
		picks = picked_this_week(self,week)
		if picks:
			message="You have made picks this week"
			current_picks = picks.picks
		else:
			message=None
			current_picks=[]
		
		view_only = 0
		# get current schedule
		sched = get_sched(self,week)
		if self.request.get('failed'):
			message="Complete picks and try again"
		if not sched:
			message ="No schedule loaded for this week, yet"
			view_only = 1
		
		# see if picks are valid this week
		cur_time = datetime.datetime.now(ARIZONA)
		cutoff_date = current_week(self,return_val=1)
		
		if self.user.username <> "winner" and not view_only:
			view_only = picks_enabled(self,cutoff_date)
			
		if self.user.settings == '1':
			form = "play_picks_alt.html"
		else:
			form = "play_picks.html"
		self.render(form,games=sched,user=self.user,message=message,picks=current_picks,time=cur_time,week=week,cutoff=cutoff_date,vo=view_only)
		

# returns: 0 - picks are enabled (before 5:30pm on the cutoff date passed in)
#		   1 - picks are disabled (after 5:30pm)
def picks_enabled(self,cutoff_date):
		today = datetime.datetime.now(ARIZONA)
		# first check day
		if today.date() < cutoff_date:
			return 0
		elif today.date() == cutoff_date:
			# then check time
			cutoff = datetime.datetime(cutoff_date.year,cutoff_date.month,cutoff_date.day,17,30,0,tzinfo=ARIZONA)
			if today < cutoff:
				return 0
			else:
				return 1
		else:
			return 1

#return_val: 0 - returns current week (integer)
#			 1 - returns picks cutoff day for current week
def current_week(self,update = False,return_val = 0):
	# we'll first get the current day
	today2 = datetime.datetime.now(ARIZONA)
	y = today2.year
	m = today2.month
	d = today2.day
	today = datetime.date(y,m,d)
	
	# 1. check the weeks cache if update is False. If there, return current week
	if memcache.get("weeks") and not update:
		#loop over cache and find week
		weeks = memcache.get("weeks")
	else:
		# 2. else, hit the DB.
		weeks = db.GqlQuery("Select * from Weeks")
		if weeks:
			weeks = list(weeks)
			memcache.set("weeks",weeks)
	
	# Compare current day to weeks list
	if weeks:
		for i in weeks:
			if i.end >= today and i.start <= today:
				if return_val == 0:
					return i.week
				elif return_val == 1:
					return i.cutoff
	return 0

#Grabs  schedule based on week parameter (required).
def get_sched(self,week):
	if not week:
		return None
	sched = memcache.get("week"+str(week))
	if not sched:
		sched = Schedule.all().filter("week =",int(week)).order("game").fetch(20)
		if sched:
			memcache.set("week"+str(week),sched)
	return sched

#Determine if user has picked this week to display results in play/picks
def picked_this_week(self,week):
	picks = memcache.get(str(self.user.username)+"week"+str(week))
	if not picks:
		picks = UserPicks.all().filter('user =', self.user).filter('week =',week).get()
	if picks:
		memcache.set(str(self.user.username)+"week"+str(week),picks)
	return picks

#Handles submission of picks.
class PickHandler(Play):
	def post(self):
		if not self.user:
			self.redirect_to('login')
			return None
		week = current_week(self)	
		picks = picked_this_week(self,week)
		if picks:
			if self.add_new_picks(week):
				picks.delete()
		else:
			#First time user is making picks
			self.add_new_picks(week)
		return None
				
	def add_new_picks(self,week):
		picks = []
		count = 1
		failed = 0
		
		# Can I just get the count of how many games there are instead of the full schedule?
		sched = get_sched(self,current_week(self))
		
		# Get the picks
		for row in sched:
			pick = self.request.get(str(count))
			if not pick and self.user.username == "winner":
				pick = "tie"
			if not pick:
				failed = 1
			else:
				picks.append(pick)
			count+=1
		
		# get the tiebreak
		tiebreak = self.request.get('tiebreak')
		#do some validation here to make sure it's a number
		try:
			tiebreak = int(float(tiebreak)) + 0
		except ValueError:
			tiebreak = 0
		picks.append(str(tiebreak))
		
		# Store picks
		if not failed:
			up = UserPicks(user=self.user,
							picks = picks,
							week = week,
							username = self.user.username)
			up.put()
			if self.user.username == "winner":
				calc_results(self,week,up)
			memcache.set(str(self.user.username)+"week"+str(week),up)
			memcache.set("week"+str(week)+"picks","") #clear cache to be reset
			self.redirect_to('picks')
			
			#email picks
			self.emailPicks(up,week)
			
			# Log Event:
			log = Log(user=self.user,action="Submit Picks")
			log.put()
			return 1
		else:
			self.redirect_to('picks',failed=1)
			return 0
		
	def emailPicks(self,user_picks,week):
		picks_string = ""
		picks = user_picks.picks
		line = picks.pop()  # get the line 
		picks = ", ".join(picks)
		mail.send_mail(sender="Pick Em <crazcarl@gmail.com>",
              to = self.user.email,
              subject = "Picks for week " + str(week),
              body = self.user.username + ", thanks for submitting your picks! Here they are: \n " + picks 
			  + "\n and the tiebreak was " + line + ".\n http://gridironguessinggame.appspot.com")
			  
# Manually set the admin flag to 1 for a user to make them an admin and have access to this menu.
class AdminHandler(SignupHandler):
	def get(self):
		admin = 0
		cur_week = current_week(self)
		if self.user:
			admin = self.user.admin
		if not admin:
			self.redirect_to('play')
			return None
		else:
			self.render('admin.html',user=self.user,message="The current week is " + str(cur_week))
	def post(self):
		if not self.user.admin:
			self.redirect_to('play')
			return None

		type=self.request.get('type')
		
		# For loading the weekly dates for the entire season
		if type=="loaddates":
			# Hit DB to look for weeks, if so delete
			# 	We may want to move this to only run after
			#	we have successfully validated and loaded
			#   in the new file.
			weeks = Weeks.all().fetch(18)
			if weeks:
				for w in weeks:
					w.delete()
					
			# Grab the data from the date textarea
			dates=self.request.get('dates')
			dates = [s for s in dates.splitlines() if s]   # Split and remove blanks
			
			wk_cache = []
			for date in dates:
				date = date.split(",")
				if date[0] == "Week":
					continue
				week = int(date[0])
				start_date = date[1].split("/")
				start = datetime.date(int(start_date[2]),int(start_date[0]),int(start_date[1]))
				end_date = date[2].split("/")
				end = datetime.date(int(end_date[2]),int(end_date[0]),int(end_date[1]))
				cutoff_date = date[3].split("/")
				cutoff = datetime.date(int(cutoff_date[2]),int(cutoff_date[0]),int(cutoff_date[1]))
				weeks = Weeks(week=week,start=start,end=end,cutoff=cutoff)
				weeks.put()
				wk_cache.append(weeks)
			
			if len(wk_cache) > 0:
				memcache.set("weeks",wk_cache)
			self.render('admin.html',message="Date file loaded",user=self.user)
			
		# Loads weekly schedule
		elif type=="loadweek":
			#determine selected week
			input_week = int(self.request.get("weekselection"))

			#Grab contents of input
			week = self.request.get('week')
			if not week or week == "":
				self.render('admin.html',message="Not a valid weeks file",user=self.user)
				return None
			week = [s for s in week.splitlines() if s]   # Split and remove blanks
			
			# Grab Current Schedule
			cur_sched = Schedule.all().filter("week =",input_week).fetch(100)
			for cs in cur_sched:
				cs.delete()  # This should probably be moved down to the bottom
							 # so we only delete if the load is successful
			sched_cache = []
			game_num = 0
			comments=self.request.get('brandon')
			email_body = ""
			if comments:
				email_body += comments
			email_body += "\nHere is the schedule for this week:"
			for game in week:
				game = game.split(",")
				if game[0] == "Home":
					continue
				home_team = game[0]
				away_team = game[1]
				line = float(game[2])
				if len(game) > 3:
					special = game[3]  # For special messages about games(thursday/xmas/etc..)
				else:
					special = ""
				schedule = Schedule(week=input_week,home_team=home_team,away_team=away_team,line=line,special=special,game=game_num)
				schedule.put()
				sched_cache.append(schedule)
				game_num += 1
				email_body += "\n" + away_team + " is playing at " + home_team + " with a line of " + game[2]
			email_body += "\n http://gridironguessinggame.appspot.com"
			# Email out new schedule
			users = User.all().fetch(100)
			for u in users:
				mail.send_mail(sender="Pick Em <crazcarl@gmail.com>",
					to = u.email,
					subject = "Schedule for week " + str(input_week),
					body = email_body)		
				
			if len(sched_cache) > 0:
				memcache.set('week'+str(input_week),sched_cache)
			self.render('admin.html',message="week file loaded",user=self.user)

		# Load winning picks manually
		elif type=="loadwinners":
			winners = self.request.get("winners")
			if not winners or winners == "":
				self.render('admin.html',message="Not a valid winner file",user=self.user)
				return None
			winners = [s for s in winners.splitlines() if s]   # Split and remove blanks
				
			# Determine selected week
			input_week = int(self.request.get("winner_weekselection"))
			
			
			# Don't allow loading in winner picks twice.
			results = Results.all().filter("week =",input_week).fetch(1)
			if results:
				self.render('admin.html',message="Already have results for this week. Clear them out first.",user=self.user)
				return None
			
			winner_user = User.by_name("winner")
						
			up = UserPicks(user=winner_user,
				picks = winners,
				week = input_week,
				username = winner_user.username)
			up.put()
			calc_results(self,input_week,up)
			self.render('admin.html',message="winner picks loaded, results calculated",user=self.user)
		
		# submit money paid by user
		elif type=="payments":
			u = self.request.get('user')
			u = User.by_name(u)
			if not u:
				self.render('admin.html',message="Unknown user",user=self.user)
				return None
			amount = self.request.get('amount')
			try:
				amount = int(float(amount)) + 0
			except ValueError:
				self.render('admin.html',message="Bad Money Value - must be a number",user=self.user)
				return None
			
			c = Cash(user=u,amount=amount,type="payment")
			c.put()
			self.render('admin.html',message="payment successful!",user=self.user)
									
									
# Builds temporary winning picks
#  temps = list of temporary winning picks
#  picks = list of UserPick objects
# Returns array with # of wins per user with current temporary picks
def build_temp(self,temps,picks):
	results = {}
	for p in picks:
		if p.user.username == "winner":
			continue
		results[p.user] = 0
		u_picks = p.picks
		for u_pick in u_picks:
			if u_pick in temps:
				results[p.user] += 1
	return results

# Handles the standings page (how many wins/losses by user by week)
class StandingsHandler(SignupHandler):
	def get(self):
		if not self.user:
			self.redirect_to('play')
			return None	
			
		week = current_week(self)
		results = []
		
		# How many weeks worth of standings will we have?
		winner = User.by_name("winner")
		if not winner:
			self.redirect_to('play')
			return None
		weeks = UserPicks.all().filter('user =', winner).order("-week").get()
		if not weeks:
			self.redirect_to('play')
			return None
		weeks = weeks.week
		
		# grab the results for each week to add to the standings
		for w in range(1,weeks+1):
			results.append(fetch_results(self,w))
		results = map(list, zip(*results))
		
		overall_results=[]
		# Calculate Cumulative results
		for row in results:
			wins = 0
			for wk_result in row:
				wins += wk_result.wins
			overall_results.insert(0,[row[0].user.username,wins])
		
		# Sort Overall Results Highest to Lowest
		overall_results = sorted(overall_results, key=lambda x: -x[1])
		
		self.render('play_standings.html',results=results,overall_results=overall_results,user=self.user,weeks=weeks)
		
# Grabs the results for building the standings
def fetch_results(self,week,update = False):
	results = ""
	if update <> True:
		results = memcache.get("week"+str(week)+"results")
	if not results:
		results = Results.all().filter('week =',week).order("user").fetch(100)
		results = list(results)
		memcache.set("week"+str(week)+"results",results)
	return results

# We calculate the results when the "winner" picks are loaded
def calc_results(self,week,w_picks = None):
	#need something to delete out old picks if need to be updated
	if not w_picks:
		winner = User.by_name("winner")
		w_picks = UserPicks.all().filter('user =', winner).filter('week =',week).get()
	if not w_picks:
		return None
	#get the number of games in the week for no picks case
	games = len(w_picks.picks) - 1
	results = {}
	top_wins = 0
	winner_list = []
	users = User.all().fetch(100)
	for u in users:
		if u.username == "winner":
			continue
		u_picks = memcache.get(str(u.username)+"week"+str(week))
		if not u_picks:
			u_picks = UserPicks.all().filter('user =', u).filter('week =',week).get()
		if u_picks:
			tb = abs(int(u_picks.picks[-1]) - int(w_picks.picks[-1]))
			(wins,losses) = compare_picks(self,w_picks.picks,u_picks.picks)
			# Log $5 to Cash
			c = Cash(type="picks",amount=5,user=u)
			c.put()
		else:
			# check that user is active
			if u.active == False:
				continue
			# no picks for this week, zero wins
			wins = 0
			losses = games
			tb = 0
		results = Results(wins=wins,losses=losses,user=u,week=week,tb=tb)
		results.put()
		if wins >= top_wins:
			if wins == top_wins:
				winner_list.append([results,tb])
			else:
				top_wins = wins
				winner_list = [[results,tb]]
		check_previous_weeks(week,u)
	if len(winner_list) > 1:
		#do tb case, sort by second element in array
		winner_list = sorted(winner_list, key=lambda x: x[1])
	for w in range(len(winner_list)):
		if winner_list[w][1] == winner_list[0][1]:
			winner_list[w][0].winner = 1
			winner_list[w][0].put()
			# Send email to winner
			mail.send_mail(sender="Pick Em <crazcarl@gmail.com>",
              to = winner_list[w][0].user.email,
              subject = "You won this week!",
              body = winner_list[w][0].user.username + ", You won this week! Head over to http://gridironguessinggame.appspot.com/iwon to upload an"
			  + "image to celebrate.")
	time.sleep(1)
	return fetch_results(self,week,update = True)

	# Verifies all users have picks for every week
def check_previous_weeks(week,u):
	for wk in range(1,week):
		# Determine num of games for week:
		winner = User.by_name("winner")
		r_picks = UserPicks.all().filter('week =',wk).filter('user =',winner).get()
		games = len(r_picks.picks) - 1
		u_results = Results.all().filter('user =', u).filter('week =',wk).get()
		if not u_results:
			wins = 0
			losses = games
			tb = 0
			results = Results(wins=wins,losses=losses,user=u,week=wk,tb=tb)
			results.put()

# Compare "winner" picks to user picks
def compare_picks(self,winner_picks,player_picks):
	(wins,losses) = 0,0
	for pick in player_picks:
		if pick == player_picks[-1]:
			break
		if pick in winner_picks:
			wins += 1
		else:
			losses += 1
	return (wins,losses)
	
class TempStandings(SignupHandler):
	def get(self):
		if not self.user:
			self.redirect_to('login')
		week = current_week(self)
		result = get_current_winners(self)
		if not result:
			message="Problem with NFL stats API. Check back later"
			self.render('temp_standings.html',user=self.user,message=message)
			return None
		# Grab Picks for current week
		picks = memcache.get("week"+str(week)+"picks")
		if not picks:
			picks = UserPicks.all().filter('week = ',week).fetch(1000)
			if picks:
				memcache.set("week"+str(week)+"picks",list(picks))
		results = build_temp(self,result,picks)
		
		# Can you still win?
		# 1. Calculate # of games left
		gamesLeft = len(Schedule.all().filter('week =',week).fetch(20))
		# 2. Find person with highest score
		topDog = 0
		for r in results:
			if results[r] > topDog:
				topDog = results[r]
		# 3. Compare to your current score
		if self.user in results and (topDog - results[self.user] > gamesLeft):
			canWin = 0
		else:
			canWin = 1
		
		
		self.render('temp_standings.html',user=self.user,temp_standings=results,canWin=canWin)

def get_current_winners(self):
		url = "http://www.nfl.com/liveupdate/scorestrip/ss.xml"
		try:
			result = urlfetch.fetch(url)
		except runtime.apiproxy_errors.DeadlineExceededError:
			return []
		result = result.content
		root=ET.fromstring(result)
		week = current_week(self)
		rc=[]
		for child in root:
			if child.get('w') <> str(week):
				continue
			for game in child:
				if game.get('q') <> 'F' and game.get('q') <> 'FO':
					continue
				home_team = teamToLong(game.get('h'))
				gm = Schedule.all().filter('week =',week).filter('home_team =',home_team).get()
				# Shouldn't happen
				if not gm:
					continue
				home_score_modified = int(game.get('hs')) + gm.line
				away_score = int(game.get('vs'))				
				if home_score_modified > away_score:
					rc.append(home_team)
				elif home_score_modified < away_score:
					rc.append(teamToLong(game.get('v')))
				else:
					rc.append('tie')
		return rc

##### Models #####		
class Results(db.Model):
	week = db.IntegerProperty(required = True)
	user = db.ReferenceProperty(User)
	wins = db.IntegerProperty(required = True)
	losses = db.IntegerProperty(required = True)
	tb = db.IntegerProperty(default = 0)
	winner = db.IntegerProperty(default = 0)
class UserPicks(db.Model):
	user = db.ReferenceProperty(User)
	picks = db.ListProperty(required = True, item_type=str)
	created = db.DateTimeProperty(auto_now_add = True)
	week = db.IntegerProperty(required = True)
class Schedule(db.Model):
	week = db.IntegerProperty(required = True)
	home_team = db.StringProperty(required = True)
	away_team = db.StringProperty(required = True)
	line = db.FloatProperty(required = True)
	special = db.StringProperty()
	game = db.IntegerProperty()
class Weeks(db.Model):
	week = db.IntegerProperty(required = True)
	start = db.DateProperty(required = True)
	end = db.DateProperty(required = True)
	cutoff = db.DateProperty(required = True)
class FrontPost(db.Model):
	title = db.StringProperty(required = True)
	content = db.TextProperty(required = True)
	created = db.DateTimeProperty(auto_now_add = True)
	winner = db.IntegerProperty(default = 0)
	user = db.ReferenceProperty(User)
	week = db.IntegerProperty(required = True, default = 0)