import datetime
from handlers.signup import SignupHandler
from google.appengine.api import memcache
from handlers.signup import User
from google.appengine.ext import db

#ARIZONA = pytz.timezone('US/Arizona')

class ForumHandler(SignupHandler):
	def get(self):
		threads = Thread.all().order('-created').fetch(10)
		self.render('forum.html',threads=threads,user=self.user)
	def post(self):
		user = self.request.get('username')
		user = User.by_name(user)
		post = self.request.get('post')
		title = self.request.get('title')
		# needs better handling for user and post verification
		if user and post and title:
			# Create New Thread
			thread = Thread(author = user,
							title = title)
			thread.put()
			post = Post(parent = thread,
						content = post,
						user = user)
			post.put()
		else:
			self.redirect_to('play')
			return None
		self.redirect_to('forum')
class ThreadHandler(SignupHandler):
	def get(self,thread):
		thread=Thread.by_id(int(thread))
		posts = Post.all().order('-created').fetch(20)
		self.render('post.html',thread=thread,posts=posts,user=self.user)
	def post(self,thread):
		user = self.user
		post = self.request.get('post')
		thread_cls=Thread.by_id(int(thread))
		#needs better verification
		if user and post and thread:
			post = Post(parent = thread_cls,
						content = post,
						user = user)
			post.put()
		self.redirect_to('thread',thread=thread)
		

class Thread(db.Model):
	created = db.DateTimeProperty(auto_now_add = True)
	author = db.ReferenceProperty(User)
	lastpost = db.DateTimeProperty(auto_now_add = True)
	title = db.StringProperty(required = True)
	
	@classmethod
	def by_id(cls, uid):
		return Thread.get_by_id(uid)

	
class Post(db.Model):
	user = db.ReferenceProperty(User)
	created = db.DateTimeProperty(auto_now_add = True)
	content = db.TextProperty(required = True)
