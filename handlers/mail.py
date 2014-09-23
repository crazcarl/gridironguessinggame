from handlers.signup import SignupHandler
from handlers.play import current_week
from google.appengine.api import mail
from handlers.signup import User
from handlers.play import UserPicks

class MailHandler(SignupHandler):
	def get(self):
		if self.request.headers.get('X-AppEngine-Cron') is None:
			return None
		week = current_week(self)
		if not week:
			return None
		u_list = User.all().fetch(100)
		u_list = list(u_list)
		for u in u_list:
			if u.username == "winner":
				continue
			picks = UserPicks.all().filter("user =", u).filter("week =", week).get()
			if not picks:
				mail.send_mail(sender="Pick Em <crazcarl@gmail.com>",
				to = u.email,
				subject = "Picks Reminder",
				body = "Hey " + u.username + " remember to submit your picks today! \n http://gridironguessinggame.appspot.com")
				
				
