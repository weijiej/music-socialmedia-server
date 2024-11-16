import os
import spotipy
  # accessible as a variable in index.html:
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, request, render_template, g, redirect, Response, abort
from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials

tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
#flask instance
app = Flask(__name__, template_folder=tmpl_dir)
DATABASEURI = "postgresql://rq2193:073929@104.196.222.236/proj1part2"
engine = create_engine(DATABASEURI)

#spotify API setup
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id="86079ffb63234fd4b6a7a17f22f463ac",
    client_secret="87d278bfd8874a588803ba7d57f4ad5a"
))

@app.before_request
def before_request():
  """
  This function is run at the beginning of every web request
  (every time you enter an address in the web browser).
  We use it to setup a database connection that can be used throughout the request.

  The variable g is globally accessible.
  """
  try:
    g.conn = engine.connect()
  except:
    print("uh oh, problem connecting to database")
    import traceback; traceback.print_exc()
    g.conn = None

@app.teardown_request
def teardown_request(exception):
  """
  At the end of the web request, this makes sure to close the database connection.
  If you don't, the database could run out of memory!
  """
  try:
    g.conn.close()
  except Exception as e:
    pass

#our code:


#initial page
@app.route('/')
def index():
  return redirect("/login")

#website methods
@app.route('/login', methods=["POST", "GET"])
def login():
  #check request type:
  if request.method == "POST":
    #Retrieve the data
    username = request.form.get("username")

    #check if username is in database:
    result = g.conn.execute(text("SELECT * FROM Users WHERE username = :username"), {"username": username}).fetchone()
    g.conn.commit()
    if result:
      return redirect("/dashboard")
    else:
      return "Invalid username or password", 401

  #return to blank login page
  return render_template("login.html")

@app.route('/signup', methods=["GET", "POST"])
def signup():
  if request.method == "POST":
    username = request.form.get("username")
    DoB = request.form.get("DoB")

    existing_user = g.conn.execute(text("SELECT * FROM users WHERE username = :username"), {"username": username}).fetchone()
    
    #if the user already exists, prompt a message
    if existing_user:
      return "User already exists.", 400

    #insert new user into the database
    g.conn.execute(text("INSERT INTO users (username, DateOfBirth) VALUES (:username, :DoB)"),{"username": username, "DoB": DoB})
    g.conn.commit()
    return redirect("/dashboard")
  
  #refresh to blank signup page
  return render_template("signup.html")


@app.route('/dashboard')
def dashboard():
  return render_template("dashboard.html")

if __name__ == "__main__":
  import click
  
  @click.command()
  @click.option('--debug', is_flag=True)
  @click.option('--threaded', is_flag=True)
  @click.argument('HOST', default='0.0.0.0')
  @click.argument('PORT', default=8111, type=int)
  def run(debug, threaded, host, port):
    """
    This function handles command line parameters.
    Run the server using:

        python3 server.py

    Show the help text using:

        python3 server.py --help

    """

    HOST, PORT = host, port
    print("running on %s:%d" % (HOST, PORT))
    app.run(host=HOST, port=PORT, debug=debug, threaded=threaded)

  run()