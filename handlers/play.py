#from handlers.base import AppHandler
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


ARIZONA = pytz.timezone('US/Arizona')

class Play(SignupHandler):
	def get(self):
		self.render('play.html',user=self.user)
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
		self.render('play_picks.html',games=sched,user=self.user,message=message,picks=current_picks,time=cur_time,week=week,cutoff=cutoff_date,vo=view_only)
		

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
              body = self.user.username + ", thanks for submitting your picks! Here they are: \n " + picks + "\n and the tiebreak was " + line +".")
			  
#Manually set the admin flag to 1 for a user to make them an admin and have access to this menu.
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
			email_body = "Here is the schedule for this week:"
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
		# Load winning picks
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

# Handles Results (showing who picked each team for each game)
class ResultsHandler(SignupHandler):
	# Loops over users and finds who picked (and didn't) in UserPicks DB for current week
	def get(self):
		if not self.user:
			self.redirect_to('login')
			return None
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
			self.render('play_results.html',message = "Results for week " + str(week) +" are not available until after cutoff date",user = self.user)
			return None
		
		# Get list of all users
		usernames = memcache.get('username')
		if not usernames:
			usernames = []
			users = User.all().fetch(1000)
			users = list(users)
			for u in users:
				usernames.append(u.username)
			memcache.set('username',usernames)
		
		# Grab Picks for current week
		picks = memcache.get("week"+str(week)+"picks")
		if not picks:
			picks = UserPicks.all().filter('week = ',week).fetch(1000)
			if picks:
				memcache.set("week"+str(week)+"picks",list(picks))
		
		
		# Build Temporary Standings
		# 0. Check to see if we're in temporary standings range (after cutoff for current week)
		temp_standings = {}
		if show_results and week == current_week(self):
			# 1. See if we have temporary winning picks for this week from forum post
			thread = Thread.by_id(5726348362383360)
			if thread:
				posts = Post.all().order('-created').ancestor(thread).fetch(200)
				for post in posts:
					if post.content.split(",")[0] == str(week):
						temp_standings = self.build_temp(post.content,picks)
						break
		
		
		winner_list = ""
		# Remove winner from picks and generate list of users who did not submit picks
		for p in picks:
			if p.user.username == "winner":
				winner_list = p.picks
				picks.remove(p)
			if p.user.username in usernames:
				usernames.remove(p.user.username)
		
		
		self.display_results(picks,usernames,week,winner_list,temp_standings)
	
	# Renders the play_results.html file to show what users picked for each game
	# 	picks - files from the UserPicks DB for the current week
	#	nopicks - list of names of users that did not pick this week
	def display_results(self,picks,nopicks,week,winner_list,temp_standings):
		#get teams array
		schedule = Schedule.all().filter("week =",week).order("game").fetch(20)
		schedule = list(schedule)
		games = {}
		i = 1
		#on results.html, build hash table for results
		for s in schedule:
			games[i] = {}
			ht=s.home_team
			at=s.away_team
			games[i][ht] = []
			games[i][at] = []
			for p in picks:
				if ht in p.picks:
					user=p.user
					games[i][ht].append(user.username)
				elif at in p.picks:
					user=p.user
					games[i][at].append(user.username)
			games[i][at] = ', '.join([un for un in games[i][at]])
			games[i][ht] = ', '.join([un for un in games[i][ht]])
			i += 1
		self.render('play_results.html',results=games,user=self.user,no_picks_list=nopicks,
										week=week,winner_list=winner_list,temp_standings=temp_standings)
	
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
		
		#grab the results for each week to add to the standings
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
		else:
			#no picks for this week, zero wins
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
		#check_previous_weeks(week,u)   #not currently enabled
	if len(winner_list) > 1:
		#do tb case, sort by second element in array
		winner_list = sorted(winner_list, key=lambda x: x[1])
	for w in range(len(winner_list)):
		if winner_list[w][1] == winner_list[0][1]:
			winner_list[w][0].winner = 1
			winner_list[w][0].put()
	time.sleep(1)
	return fetch_results(self,week,update = True)

	# Verifies all users have picks for every week
def check_previous_weeks(week,u):
	for wk in range(1,week):
		# Determine num of games for week:
		r_picks = UserPicks.all().filter('week =',wk).get()
		games = 99 #len(r_picks.picks) - 1
		u_picks = UserPicks.all().filter('user =', u).filter('week =',wk).get()
		if not u_picks:
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

##### Models ######		
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