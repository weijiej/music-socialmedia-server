import os
import spotipy
  # accessible as a variable in index.html:
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, request, render_template, g, redirect, Response, abort, session, flash, url_for
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
        
    #check wether username is already in database
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
        
    existing_user = g.conn.execute(
        text("SELECT username FROM users WHERE username = :username"),
        {"username": username}
    ).fetchone()
    
    if existing_user:
        return render_template("signup.html", error="Username already exists. Please choose another."), 400
    
    #username is not in database
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
        LIMIT 20
        """), {
            'username':current_user
        }).fetchall()
    
    #list to store song information
    posts = []
    for song in songs:
        posts.append({
            'song_id': song[0],
            'song_title': song[1],
            'artist_name': song[2]
        })

    return render_template("dashboard.html", user=session['username'], posts=posts)

@app.route('/add_favorite', methods = ["POST"])
def add_favorite():
    #check if user is logged in
    if 'username' not in session:
        return redirect('/login')
    
    song_id = request.form.get('song_id')
    username = session['username']

    #database queries:
    #1. Get song title for success message
    song = g.conn.execute(text("SELECT s.title FROM songs s WHERE s.songid = :songid"), {"songid":song_id}).fetchone()

    song_title = song[0]

    #2. Check favorites table
    current_favorites = g.conn.execute(text("""
        SELECT *
        FROM favorites f
        WHERE username = :username AND songid = :songid
        """
    ),{
        'username':username,
        'songid':song_id
    }).fetchone()

    if not current_favorites:
        #add to favorites
        g.conn.execute(text("""
            INSERT INTO favorites(username, songid)
            VALUES (:username, :songid)
        """), {
            "username":username,
            "songid":song_id
        })
        g.conn.commit()
        flash(f"'{song_title}' was added to your favorites!", "success")
    else:
        flash(f"'{song_title}' is already in your favorites!", "info")

    return redirect("/dashboard")

@app.route('/song/<string:song_id>/comments')
def view_comments(song_id):
    #check if user is still logged in
    if 'username' not in session:
        return redirect('/login')

    #get the song details
    song_details = g.conn.execute(text("""
        SELECT s.songid, s.title, a.artistname
        FROM songs s JOIN released_under ru ON s.songid = ru.songid
        JOIN artists a ON ru.artistid = a.artistid
        WHERE s.songid = :songid
    """), {
        "songid": song_id
    }).fetchone()

    #check if its a valid song
    if not song_details:
        return redirect('/dashboard')

    song = {
        'id': song_details[0],
        'title': song_details[1],
        'artist_name': song_details[2]
    }

    #query for all comments associated with the song
    comments_details = g.conn.execute(text("""
        SELECT *
        FROM posted_comment_reviews pcr JOIN songs s ON pcr.songid = s.songid
        WHERE s.songid = :songid
        ORDER BY pcr.likes DESC
    """),{
        "songid": song_id
    }).fetchall()

    all_comments = []
    for comment in comments_details:
        all_comments.append({
            'commentid': comment[0],
            "comment_text": comment[1],
            "likes": comment[2],
            "date_created": comment[3],
            "username": comment[4]
        })
    
    return render_template("comments.html", song=song, comments=all_comments)

@app.route('/song/<string:song_id>/comment', methods=['POST'])
def add_comment(song_id):
    if 'username' not in session:
        return redirect('/login')

    #get the user input
    comment_text = request.form.get('comment_text')
    try:
        #check the last comment number, used for creating new commentid
        last_comment = g.conn.execute(text("""
            SELECT pcr.commentid
            FROM posted_comment_reviews pcr
            ORDER BY commentid DESC
            LIMIT 1
        """)).fetchone()

        if last_comment:
            #get the last commentid #
            last_num = int(last_comment[0][3:])
            new_num = last_num + 1
        else:
            #no comments exist
            new_num = 1

        new_comment_id = f"CMT{new_num:07d}"

        #insert new comment into the database
        g.conn.execute(text("""
            INSERT INTO posted_comment_reviews (commentid, comment_text, likes, datecreated, username, songid)
            VALUES (:commentid, :comment_text, 0, CURRENT_TIMESTAMP, :username, :songid)
        """),{
            'commentid': new_comment_id,
            'comment_text': comment_text,
            'username': session['username'],
            'songid': song_id
        })
        g.conn.commit()

        flash("Comment added successfully", "success")
    except Exception as e:
        print(f"Error adding comment: {e}")
        flash("Error adding comment. Please try again.", "info")

    return redirect(url_for('view_comments', song_id=song_id))
  
#artist's profile page
@app.route('/artist/<artist_id>', methods=["GET"])
def artist_profile(artist_id):
    # Fetch artist details by ID
    artist = g.conn.execute(text(
        "SELECT ArtistName, ArtistBio, Country FROM Artists WHERE ArtistID = :artist_id"
    ), {"artist_id": artist_id}).fetchone()

    if not artist:
        return f"<h1>Artist not found</h1><p>The artist with ID {artist_id} does not exist.</p><a href='/search'>Back to Search</a>", 404

    artist_dict = {
        "ArtistName": artist[0],  # Ensure the name is fetched correctly
        "ArtistBio": artist[1],
        "Country": artist[2]
    }

    # Fetch songs released by the artist
    songs = g.conn.execute(text(
        "SELECT S.Title, S.SongID FROM Songs S JOIN Released_Under R ON S.SongID = R.SongID WHERE R.ArtistID = :artist_id"
    ), {"artist_id": artist_id}).fetchall()

    # Convert songs to a list of dictionaries
    songs_list = [{"Title": row[0], "SongID": row[1]} for row in songs]

    return render_template("artist_profile.html", artist=artist_dict, songs=songs_list)

@app.route('/search', methods=["GET", "POST"])
def search():
    results = None
    search_query = None

    if request.method == "POST":
        search_query = request.form.get("search_query")

        # Perform a search across artists and users
        artists = g.conn.execute(text(
            "SELECT ArtistName, ArtistID FROM Artists WHERE ArtistName ILIKE :query"
        ), {"query": f"%{search_query}%"}).fetchall()

        users = g.conn.execute(text(
            "SELECT Username FROM Users WHERE Username ILIKE :query"
        ), {"query": f"%{search_query}%"}).fetchall()

        # Convert results to dictionaries
        results = {
            "artists": [{"ArtistName": artist[0], "ArtistID": artist[1]} for artist in artists],
            "users": [{"Username": user[0]} for user in users],
        }

    return render_template("search.html", results=results, search_query=search_query)

#seperate route viewing other's profile
@app.route('/user/<username>', methods=["GET"])
def user_profile_view(username):
    user = g.conn.execute(text(
        "SELECT Username FROM Users WHERE Username ILIKE :username"
    ), {"username": username}).fetchone()

    if not user:
        return render_template("error.html", message="User not found"), 404

    # Fetch data from the database
    playlists = g.conn.execute(text("""
        SELECT up.playlistid, up.playlistname, up.since
        FROM user_playlists up
        WHERE up.username ILIKE :username
    """), {'username': username}).fetchall()

    followed_artists = g.conn.execute(text("""
        SELECT f.artistid, a.artistname, f.since
        FROM follows f JOIN artists a ON f.artistid = a.artistid
        WHERE f.username ILIKE :username
    """), {'username': username}).fetchall()

    favorited_songs = g.conn.execute(text("""
        SELECT f.songid, s.title, a.artistname
        FROM favorites f JOIN songs s ON f.songid = s.songid
        JOIN released_under ru ON s.songid = ru.songid
        JOIN artists a ON ru.artistid = a.artistid
        WHERE f.username ILIKE :username
    """), {'username': username}).fetchall()

    # Convert to dictionaries
    playlists = [{"PlaylistID": row[0], "PlaylistName": row[1], "Since": row[2]} for row in playlists]
    followed_artists = [{"ArtistID": row[0], "ArtistName": row[1], "Since": row[2]} for row in followed_artists]
    favorited_songs = [{"SongID": row[0], "Title": row[1], "ArtistName": row[2]} for row in favorited_songs]

    return render_template('user_profile.html', username=username, playlists=playlists, artists=followed_artists, favorites=favorited_songs)


#user profile
@app.route('/profile')
def user_profile():
    if 'username' not in session:
        return redirect('/login')

    username = session['username']

    try:
        # Get the user's playlists
        playlists = g.conn.execute(text("""
            SELECT up.PlaylistID, up.PlaylistName, up.Since
            FROM user_playlists up
            WHERE up.Username = :username
        """), {
            'username': username
        }).fetchall()
        
        # Get the followed artists
        followed_artists = g.conn.execute(text("""
            SELECT f.ArtistID, a.ArtistName, f.Since
            FROM follows f JOIN artists a ON f.ArtistID = a.ArtistID
            WHERE f.Username = :username
        """), {
            'username': username
        }).fetchall()

        # Get the user's favorite songs
        favorited_songs = g.conn.execute(text("""
            SELECT f.SongID, s.Title, a.ArtistName
            FROM favorites f JOIN songs s ON f.SongID = s.SongID
            JOIN released_under ru ON s.SongID = ru.SongID
            JOIN artists a ON ru.ArtistID = a.ArtistID
            WHERE f.Username = :username 
        """), {
            'username': username
        }).fetchall()

        # Turn queries into lists
        playlists_list = []
        for playlist in playlists:
            playlists_list.append({
                'PlaylistID': playlist[0],
                'PlaylistName': playlist[1],
                'Since': playlist[2]
            })

        artists_list = []
        for artist in followed_artists:
            artists_list.append({
                'ArtistID': artist[0],
                'ArtistName': artist[1],
                'Since': artist[2]
            })

        favorites_list = []
        for song in favorited_songs:
            favorites_list.append({
                'SongID': song[0],
                'Title': song[1],
                'ArtistName': song[2]
            })
            
        return render_template('user_profile.html', username=username, playlists=playlists_list, artists=artists_list, favorites=favorites_list)

    except Exception as e:
        print(f"Error loading profile data: {e}")
        flash("Error loading profile information", "info")
        return redirect('/dashboard')

#follow artist function 
@app.route('/follow_artist', methods=['POST'])
def follow_artist():
    if 'username' not in session:
        flash("You must be logged in to follow an artist.", "danger")
        return redirect('/login')

    artist_name = request.form.get('artist_name')  # Fetch artist name from the form
    username = session['username']

    try:
        # Fetch artist_id using artist_name
        artist_id = g.conn.execute(text("""
            SELECT artistid FROM artists WHERE artistname = :artist_name
        """), {"artist_name": artist_name}).scalar()  # Use scalar() to fetch a single value directly

        # Check if the user already follows the artist
        existing_follow = g.conn.execute(text("""
            SELECT * FROM follows WHERE username = :username AND artistid = :artist_id
        """), {
            'username': username,
            'artist_id': artist_id
        }).fetchone()

        if not existing_follow:
            # Insert the follow relationship
            g.conn.execute(text("""
                INSERT INTO follows (username, artistid)
                VALUES (:username, :artist_id)
            """), {
                'username': username,
                'artist_id': artist_id
            })
            g.conn.commit()
            flash(f"You are now following {artist_name}!", "success")
        else:
            flash(f"You are already following {artist_name}.", "info")

    except Exception as e:
        print(f"Error following artist: {e}")
        flash("An unexpected error occurred. Please try again.", "danger")

    # Stay on the same artist profile page
    return redirect(request.referrer)

#add playlist function
@app.route('/add_to_playlist/<song_id>', methods=['POST'])
def add_to_playlist(song_id):
    if 'username' not in session:
        return jsonify({"success": False, "message": "You must be logged in to add songs to a playlist."}), 401

    username = session['username']

    try:
        # Check if the song is already in the playlist
        existing_entry = g.conn.execute(text("""
            SELECT * FROM favorites WHERE username = :username AND songid = :songid
        """), {"username": username, "songid": song_id}).fetchone()

        if not existing_entry:
            # Insert the song into the user's playlist
            g.conn.execute(text("""
                INSERT INTO favorites (username, songid)
                VALUES (:username, :songid)
            """), {"username": username, "songid": song_id})
            g.conn.commit()
            return jsonify({"success": True}), 200
        else:
            return jsonify({"success": False, "message": "Song is already in your playlist."}), 400
    except Exception as e:
        print(f"Error adding to playlist: {e}")
        return jsonify({"success": False, "message": "An unexpected error occurred."}), 500


if __name__ == "__main__":
  import click

  @click.command()
  @click.option('--debug', is_flag=True, default=True)  # Default to debug mode
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
