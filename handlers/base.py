# Setup using this:
# http://forums.udacity.com/questions/6017214/how-to-setup-a-routing-system-and-separate-out-your-project-modules#cs253
import jinja2
import webapp2
import hmac
from main import template_dir
import handlers.signup
import pytz

# Initialize the jinja2 environment
jinja_environment = jinja2.Environment(autoescape=True,
        loader=jinja2.FileSystemLoader(template_dir))
SECRET = "secret"
		
class AppHandler(webapp2.RequestHandler):
	
	#Base handler, encapsulating jinja2 functions.
	def __init__(self, request=None, response=None):
		#Initialize the handler.
		super(AppHandler, self).__init__(request, response)
		self.jinja = jinja_environment
		
	def write(self, string):
		#Write an arbitrary string to the response stream.
		self.response.out.write(string)
		
	def render_str(self, template_name, values=None, **kwargs):
		#Render a jinja2 template and return it as a string.
		template = self.jinja.get_template(template_name)
		return template.render(values or kwargs)
		
	def render(self, template_name, values=None, **kwargs):
		#Render a jinja2 template using a dictionary or keyword arguments.
		self.write(self.render_str(template_name, values or kwargs))

	def redirect_to(self, name, *args, **kwargs):
		#Redirect to a URI that corresponds to a route name.
		self.redirect(self.uri_for(name, *args, **kwargs))
	
	def set_secure_cookie(self,name,val):
		cookie_val = make_secure_val(val)
		self.response.headers.add_header('Set-Cookie', '%s=%s' % (name,cookie_val))
		
	def login(self, user):
		self.set_secure_cookie('user_id', str(user.key().id()))
		
	def read_secure_cookie(self, name):
		cookie_val = self.request.cookies.get(name)
		return cookie_val and check_secure_val(cookie_val)
	def initialize(self, *a, **kw):
		webapp2.RequestHandler.initialize(self, *a, **kw)
		uid = self.read_secure_cookie('user_id')
		self.user = uid and handlers.signup.User.by_id(int(uid))
		
def hash_str(s):
	return hmac.new(SECRET, s).hexdigest()
	
def check_secure_val(secure_val):
	val = secure_val.split('|')[0]
	if secure_val == make_secure_val(val):
		return val
def make_secure_val(val):
	return '%s|%s' % (val, hash_str(val))

	

def format_datetime(value):
	utc = pytz.utc
	fmt = '%m/%d/%y %H:%M:%S'
	ARIZONA = pytz.timezone('US/Arizona')
	value = utc.localize(value)
	return value.astimezone(ARIZONA).strftime(fmt)

jinja_environment.filters['datetime'] = format_datetime