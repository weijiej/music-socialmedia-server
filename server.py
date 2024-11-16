import os
import spotipy
  # accessible as a variable in index.html:
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, request, render_template, g, redirect, Response, abort, session
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
#required for sessions implementation
app.secret_key = 'test'

#Log In Page
@app.route('/login', methods=["POST", "GET"])
def login():
    if request.method == "GET":
        return render_template("login.html")
        
    username = request.form.get("username")
    
    if not username or username.strip() == "":
        return render_template("login.html", error="Username is required"), 400
        
    result = g.conn.execute(
        text("SELECT username FROM Users WHERE username = :username"),
        {"username": username}
    ).fetchone()
    
    if result:
        session['username'] = username  # Store username in session
        return redirect('/dashboard')
    else:
        return render_template("login.html", error="Invalid username. Please try again or sign up."), 401

#Sign Up Page
@app.route('/signup', methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html")
        
    username = request.form.get("username")
    DoB = request.form.get("DoB")
    
    if not username or username.strip() == "":
        return render_template("signup.html", error="Username is required"), 400
        
    if not DoB:
        return render_template("signup.html", error="Date of Birth is required"), 400
        
    existing_user = g.conn.execute(
        text("SELECT username FROM users WHERE username = :username"),
        {"username": username}
    ).fetchone()
    
    if existing_user:
        return render_template("signup.html", error="Username already exists. Please choose another."), 400
    
    g.conn.execute(
        text("INSERT INTO users (username, DateOfBirth) VALUES (:username, :DoB)"),
        {"username": username, "DoB": DoB}
    )
    g.conn.commit()
    
    session['username'] = username  # Store username in session
    return redirect('/dashboard')

#User Dashboard
@app.route('/dashboard')
def dashboard():
    #checks for valid session
    if 'username' not in session:
        return redirect('/login')
    current_user = session['username']

    #query for distinct songs not currently favorited by user
    #returns the song title and its respective artist
    songs = g.conn.execute(text("""
        SELECT DISTINCT s.songid, s.title, a.artistname
        FROM songs s JOIN released_under ru ON s.songid = ru.songid
        JOIN artists a ON a.artistid = ru.artistid
        WHERE s.songid NOT IN (
            SELECT f.songid
            FROM favorites f
            WHERE f.username = :username
        )
        LIMIT 10
        """), {
            'username':current_user
        }).fetchall()
    
    posts = []
    for song in songs:
        posts.append({
            'song_id': song[0],
            'song_title': song[1],
            'artist_name': song[2]
        })

    return render_template("dashboard.html", user=session['username'], posts=posts)

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