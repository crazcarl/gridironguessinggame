from handlers.base import AppHandler
from google.appengine.ext import db
import re
import hashlib
import random
from string import letters
import webapp2
from google.appengine.api import memcache

UN_RE=re.compile("^[a-zA-Z0-9_-]{3,20}$")
PW_RE=re.compile("^.{3,20}$")
EM_RE=re.compile("^[\S]+@[\S]+\.[\S]+$")


	

class SignupHandler(AppHandler):
	def get(self):
		self.render('signup.html',error=[])
	def post(self):
		self.username = self.request.get('username')
		self.password = self.request.get('password')
		self.vpw = self.request.get('verify')
		self.email = self.request.get('email')
		self.league = self.request.get('league')
		self.realname = self.request.get('realname')
		error=["","","","","",""]
		has_error=0
		if not self.realname:
			error.insert(5,"Please Enter your Real Name")
			has_error=1
		if not self.username or not UN_RE.match(self.username):
			error.insert(0,"Invalid Username")
			has_error=1
		if not self.password or not PW_RE.match(self.password):
			error.insert(1,"Invalid PW")
			has_error=1
		if self.password <> self.vpw:
			error.insert(2,"Passwords do not match")
			has_error=1
		if not self.email or not EM_RE.match(self.email):
			error.insert(3,"Valid Email Required")
			has_error=1
		# TODO: replace with actual PW at some point
		if self.league <> 'asdf':
			error.insert(4,"Invalid League PW")
			has_error=1
		if has_error==1:
			self.render('signup.html',error=error)
		else:
			self.done()

		

class Register(SignupHandler):
	def done(self):
        #make sure the user doesn't already exist
		u = User.by_name(self.username)
		if u:
			msg = 'That user already exists.'
			error=[]
			error.insert(0,msg)
			self.render('signup.html', error=error)
		else:
			u = User.register(self.username, self.password,self.email)
			u.put()
			usernames = memcache.get('usernames')
			if usernames:
				usernames.append(u.username)
				memcache.set('usernames',usernames)
			self.login(u)
			if self.request.get('source') == "picks":
				self.redirect_to('play')
			else:
				self.redirect_to('welcome')
	
class Settings(SignupHandler):
	def get(self):
		if not self.user:
			self.redirect_to('login')
			return None
		
		self.render('user_settings.html',user=self.user,error=[],email=self.user.email)
		
	def post(self):
		password = self.request.get('password')
		verify = self.request.get('verify')
		email = self.request.get('email')
		error = ["","",""]
		has_error=0
		
		if not self.user:
			self.redirect_to('login')
			return None
		
		# changing passwords:
		if password:
			if not PW_RE.match(password):
				error.insert(0,"Invalid PW")
				has_error=1
			if password <> verify:
				error.insert(1,"PWs no matchy")
				has_error=1
			# Submit password change
			if not has_error:
				u = self.user
				pw_hash=make_pw_hash(u.username, password)
				u.pw_hash=pw_hash
				u.put()
				error.insert(0,"password changed")
		
		# changing email
		if email:
			if not EM_RE.match(email):
				error.insert(2,"Invalid Email")
			else:
				# Submit email change
				u = self.user
				u.email = email
				u.put()
				error.insert(2,"Email Changed")
		
		self.render('user_settings.html',user=self.user,error=error,email=self.user.email)

class Reset(SignupHandler):
	def get(self):
		self.render('reset_pw.html')
		
	def post(self):
		email = self.request.get('email')
		message=""
		if email:
			if not EM_RE.match(email):
				message="Not a valid email address"
			else:
				u = User.all().filter('email =', email).get()
				if u:
					#Generate New Password
					password=''.join(random.choice(letters) for _ in range(12))
					
					#Do the password reset
					pw_hash=make_pw_hash(u.username, password)
					u.pw_hash=pw_hash
					u.put()
					
					#send email
					mail.send_mail(sender="Pick Em <crazcarl@gmail.com>",
					to = u.email,
					subject = "Football Picks Password reset",
					body = "Your new password is " + password "\n After logging in, change it by clicking the settings button in the top right")
					message="Email Sent"
				else:
					message="Email address not found"
		self.render('reset_pw.html',message=message)
def make_salt(length = 5):
    return ''.join(random.choice(letters) for x in xrange(length))

def make_pw_hash(name, pw, salt = None):
    if not salt:
        salt = make_salt()
    h = hashlib.sha256(name + pw + salt).hexdigest()
    return '%s,%s' % (salt, h)
	
def valid_pw(name, password, h):
	if h:
		salt = h.split(',')[0]
		return h == make_pw_hash(name, password, salt)

def users_key(group = 'default'):
	return db.Key.from_path('users', group)
	
class User(db.Model):
	username=db.StringProperty(required = True)
	pw_hash=db.StringProperty(required = True)
	admin = db.IntegerProperty(default = 0)
	email = db.EmailProperty()
	realname = db.StringProperty()
	money = db.FloatProperty()
    
	@classmethod
	def by_id(cls, uid):
		return User.get_by_id(uid)

	@classmethod
	def by_name(cls, name):
		u = User.all().filter('username =', name).get()
		return u
	
	@classmethod
	def register(cls,name,password,email):
		pw_hash = make_pw_hash(name, password)
		return User(username = name, pw_hash = pw_hash, email = email)
					
	@classmethod
	def login(cls, name, password):
		u = cls.by_name(name)
		if u and valid_pw(name, password, u.pw_hash):
			return u
		
class WelcomeHandler(SignupHandler):
	def welcome(self):
		#grab cookie
		u = self.user
		if not u:
			self.redirect_to('login')
		else:
			self.render('welcome.html',username=u.username)
		

class LoginHandler(WelcomeHandler):
	def get(self):
		self.render("login.html",error="")
	def post(self):
		username = self.request.get('username')
		password = self.request.get('password')
		u = User.login(username, password)
		if u:
			self.login(u)
			if self.request.get('source') == "picks":
				self.redirect_to('play')
			else:
				self.redirect_to('welcome')
		else:
			msg = 'Invalid login'
			self.render('login.html', error = msg)
	def logout(self):
		self.response.headers.add_header('Set-Cookie', 'user_id=; Path=/')
		if self.request.get('source') == 'picks':
			self.redirect_to('play')
		else:
			self.redirect_to('signup')
