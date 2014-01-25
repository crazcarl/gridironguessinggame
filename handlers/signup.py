from handlers.base import AppHandler
from google.appengine.ext import db
import re
import hashlib
import random
from string import letters
import webapp2

UN_RE=re.compile("^[a-zA-Z0-9_-]{3,20}$")
PW_RE=re.compile("^.{3,20}$")
EM_RE=re.compile("^[\S]+@[\S]+\.[\S]+$")

SECRET="secret"


	

class SignupHandler(AppHandler):
	def get(self):
		self.render('signup.html',error=[])
	def post(self):
		self.username = self.request.get('username')
		self.password = self.request.get('password')
		self.vpw = self.request.get('verify')
		self.email = self.request.get('email')
		error=["","","",""]
		has_error=0
		if not self.username or not UN_RE.match(self.username):
			error.insert(0,"Invalid Username")
			has_error=1
		if not self.password or not PW_RE.match(self.password):
			error.insert(1,"Invalid PW")
			has_error=1
		if self.password <> self.vpw:
			error.insert(2,"PWs no matchy")
			has_error=1
		if self.email and not EM_RE.match(self.email):
			error.insert(3,"Invalid Email")
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
			self.login(u)
			if self.request.get('source') == "picks":
				self.redirect_to('play')
			else:
				self.redirect_to('welcome')


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
			
class ClearDB(AppHandler):
	def get(self):
		u = db.GqlQuery("Select * FROM User")
		for x in u:
			self.response.out.write(x.username)
			self.response.out.write(x.pw_hash)
			self.response.out.write('||||||||||||||')
			#x.delete()