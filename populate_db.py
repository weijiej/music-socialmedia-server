import os
from sqlalchemy import *
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from datetime import datetime

# Database setup
DATABASEURI = "postgresql://rq2193:073929@104.196.222.236/proj1part2"
engine = create_engine(DATABASEURI)

# Spotify API setup
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id="86079ffb63234fd4b6a7a17f22f463ac",
    client_secret="87d278bfd8874a588803ba7d57f4ad5a"
))

def get_last_offset():
    """Read the last used offset from a file"""
    try:
        with open('last_offset.txt', 'r') as f:
            offset = int(f.read().strip())
            # Reset offset if near Spotify's limit
            if offset >= 950:
                offset = 0
                print("Resetting offset to 0 as we're near Spotify's limit")
            return offset
    except FileNotFoundError:
        return 0

def save_offset(offset):
    """Save the last used offset to a file"""
    with open('last_offset.txt', 'w') as f:
        f.write(str(offset))

def clear_tables(conn):
    """Clear all data from tables"""
    try:
        print("Clearing existing data from tables...")
        # First clear relationship tables
        conn.execute(text("DELETE FROM includes;"))
        conn.execute(text("DELETE FROM produces;"))
        conn.execute(text("DELETE FROM released_under;"))
        # Then clear entity tables
        conn.execute(text("DELETE FROM songs;"))
        conn.execute(text("DELETE FROM albums;"))
        conn.execute(text("DELETE FROM artists;"))
        conn.commit()
        print("Tables cleared successfully!")
    except Exception as e:
        print(f"Error clearing tables: {str(e)}")
        conn.rollback()

def insert_artist(conn, artist_id, artist_name):
    """Insert artist if not exists"""
    try:
        conn.execute(text("""
            INSERT INTO artists (artistid, artistname)
            VALUES (:id, :name)
            ON CONFLICT (artistid) DO NOTHING;
        """), {'id': artist_id, 'name': artist_name})
    except Exception as e:
        print(f"Error inserting artist {artist_name}: {str(e)}")

def insert_album(conn, album_id, album_title, release_date):
    """Insert album if not exists"""
    try:
        # Handle both YYYY-MM-DD and YYYY formats
        if len(release_date) == 4:  # YYYY format
            release_date = f"{release_date}-01-01"
        
        conn.execute(text("""
            INSERT INTO albums (albumid, albumtitle, releasedate)
            VALUES (:album_id, :album_title, :release_date)
            ON CONFLICT (albumid) DO NOTHING;
        """), {
            'album_id': album_id,
            'album_title': album_title,
            'release_date': release_date
        })
    except Exception as e:
        print(f"Error inserting album {album_title}: {str(e)}")

def insert_song(conn, song_id, song_title, duration):
    """Insert song if not exists"""
    try:
        conn.execute(text("""
            INSERT INTO songs (songid, title, genre, duration_in_seconds)
            VALUES (:id, :title, :genre, :duration)
            ON CONFLICT (songid) DO NOTHING;
        """), {
            'id': song_id,
            'title': song_title,
            'genre': 'hip-hop',
            'duration': duration
        })
    except Exception as e:
        print(f"Error inserting song {song_title}: {str(e)}")

def insert_includes(conn, album_id, song_id):
    """Insert relation if not exists"""
    try:
        conn.execute(text("""
            INSERT INTO includes (albumid, songid)
            VALUES (:albumid, :songid)
            ON CONFLICT (albumid, songid) DO NOTHING;
            """), {
                'albumid': album_id,
                'songid': song_id
            })
    except Exception as e:
        print(f"Error inserting relationship ({album_id}, {song_id}): {str(e)}")

def insert_produces(conn, artist_id, album_id):
    """Insert relation if not exists"""
    try:
        conn.execute(text("""
            INSERT INTO produces (artistid, albumid)
            VALUES (:artistid, :albumid)
            ON CONFLICT (artistid, albumid) DO NOTHING;
            """), {
                'artistid': artist_id,
                'albumid': album_id
            })
    except Exception as e:
        print(f"Error inserting relationship ({artist_id}, {album_id}): {str(e)}")

def insert_released_under(conn, artist_id, song_id):
    """Insert relation if not exists"""
    try:
        conn.execute(text("""
        INSERT INTO released_under (artistid, songid)
        VALUES (:artistid, :songid)
        ON CONFLICT (artistid, songid) DO NOTHING;
        """), {
            'artistid':artist_id,
            'songid':song_id
        })
    except Exception as e:
        print(f"Error inserting relationship ({artist_id}, {song_id}): {str(e)}")

def populate_database():
    """Main function to populate the database"""
    conn = engine.connect()
    try:
        # Get the last used offset
        offset = get_last_offset()
        print(f"\nStarting database population with offset {offset}...")
        
        # Search for hip-hop tracks with offset
        results = sp.search(q="genre:hip-hop", type='track', limit=50, offset=offset)
        
        total_processed = 0
        
        # Begin transaction
        for song in results['tracks']['items']:
            try:
                # Extract all details first
                song_id = song['id']
                song_title = song['name']
                duration = song['duration_ms'] / 1000

                album = song['album']
                album_id = album['id']
                album_title = album['name']
                release_date = album['release_date']

                # 1. Insert all entities first
                # Insert artists
                artists = song['artists']
                for artist in artists:
                    artist_id = artist['id']
                    artist_name = artist['name']
                    insert_artist(conn, artist_id, artist_name)

                # Insert album
                insert_album(conn, album_id, album_title, release_date)

                # Insert song
                insert_song(conn, song_id, song_title, duration)

                # 2. Then insert all relationships
                # Insert artist-album relationships
                for artist in artists:
                    insert_produces(conn, artist['id'], album_id)
                    
                # Insert artist-song relationships
                for artist in artists:
                    insert_released_under(conn, artist['id'], song_id)
                    
                # Insert album-song relationships
                insert_includes(conn, album_id, song_id)
                
                total_processed += 1
                if total_processed % 10 == 0:
                    print(f"Processed {total_processed} songs...")
                    conn.commit()
                    
            except Exception as e:
                print(f"Error processing song {song.get('name', 'unknown')}: {str(e)}")
                conn.rollback()
                continue

        # Final commit
        conn.commit()
        
        # Save the new offset for next run
        save_offset(offset + 50)
        print(f"\nDatabase population completed! Processed {total_processed} songs successfully.")
        print(f"Next run will start from offset {offset + 50}")
        
    except Exception as e:
        print(f"Error during database population: {str(e)}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    populate_database()