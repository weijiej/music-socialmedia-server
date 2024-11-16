import os
  # accessible as a variable in index.html:
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, request, render_template, g, redirect, Response, abort

tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
#flask instance
app = Flask(__name__, template_folder=tmpl_dir)
DATABASEURI = "postgresql://rq2193:073929@104.196.222.236/proj1part2"
engine = create_engine(DATABASEURI)

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



@app.route('/dashboard', methods=["GET"])
def dashboard():
  return "Welcome to your dashboard"


  username = session.get('username')

  #Fetch most liked songs for the feed
  songs = g.conn.execute(text(
        "SELECT Title, Likes, SongID FROM Songs ORDER BY Likes DESC LIMIT 10"
    )).fetchall()

  # Fetch user's playlists
  user_playlists = g.conn.execute(text(
        "SELECT PlaylistID, PlaylistName, TotalSongs FROM User_Playlists WHERE Username = :username"
    ), {"username": username}).fetchall()

  # Fetch popular artists to follow
    popular_artists = g.conn.execute(text(
        "SELECT ArtistName, ArtistID FROM Artists A "
        "LEFT JOIN Follows F ON A.ArtistID = F.ArtistID "
        "GROUP BY A.ArtistID, A.ArtistName "
        "ORDER BY COUNT(F.Username) DESC LIMIT 5"
    )).fetchall()

    # Use the most liked songs as recommendations
    recommendations = songs

    return render_template(
        "dashboard.html",
        songs=songs,
        user_playlists=user_playlists,
        popular_artists=popular_artists,
        recommendations=recommendations
    )

  #  This route handles the creation of playlists. Users can specify a playlist name and description.
@app.route('/create_playlist', methods=["GET", "POST"])
def create_playlist():
    username = session.get('username')#ensure the user is logged in
    if request.method == "POST":
        playlist_name = request.form.get("playlist_name")
        description = request.form.get("description")

        #insert new playlist
        g.conn.execute(text(
            "INSERT INTO User_Playlists (PlaylistName, Description, Username, TotalSongs) "
            "VALUES (:playlist_name, :description, :username, 0)"
        ), {"playlist_name": playlist_name, "description": description, "username": username})
        g.conn.commit()

        return redirect("/dashboard")
     return render_template("create_playlist.html")

# this route diplays specific details of songs and allow user to leave comments

@app.route('/song/<song_id>', methods=["GET", "POST"])
def song_details(song_id):
     if request.method == "POST":
        comment_text = request.form.get("comment_text")
        username = session.get('username')

        g.conn.execute(text(
            "INSERT INTO Posted_Comment_Reviews (CommentText, Username, SongID) "
            "VALUES (:comment_text, :username, :song_id)"
        ), {"comment_text": comment_text, "username": username, "song_id": song_id})
        g.conn.commit()

        #show songs' details

        song = g.conn.execute(text(
        "SELECT Title, Likes, DurationInSeconds FROM Songs WHERE SongID = :song_id"
    ), {"song_id": song_id}).fetchone()

        # comments

        comments = g.conn.execute(text(
        "SELECT CommentText, Username, Likes FROM Posted_Comment_Reviews WHERE SongID = :song_id"
    ), {"song_id": song_id}).fetchall()

    return render_template("song_details.html", song=song, comments=comments)







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
