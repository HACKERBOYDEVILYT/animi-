from flask import Flask, render_template, request, jsonify, redirect, url_for
from models import db, Anime, Episode
from scraper import scrape_anime_data, get_video_source
import threading
import time

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///anime.db'
app.config['SECRET_KEY'] = 'supersecretkey'
db.init_app(app)

# Create tables
with app.app_context():
    db.create_all()

# --- ROUTES ---

@app.route('/')
def home():
    # Show latest added anime
    latest_animes = Anime.query.order_by(Anime.created_at.desc()).limit(10).all()
    return render_template('index.html', animes=latest_animes)

@app.route('/anime/<slug>')
def anime_detail(slug):
    anime = Anime.query.filter_by(slug=slug).first_or_404()
    return render_template('anime_detail.html', anime=anime)

@app.route('/play/<int:anime_id>/<int:ep_number>')
def play_episode(anime_id, ep_number):
    # Check if we already have the source cached
    episode = Episode.query.filter_by(anime_id=anime_id, episode_number=ep_number).first()
    
    if episode and episode.video_server_1:
        source_url = episode.video_server_1
    else:
        # If not cached, fetch it now!
        # You need the anime_id from the anime object
        anime = Anime.query.get(anime_id)
        # HiAnime URL structure might vary, assuming standard format here
        # In a real scenario, you'd store the hi_anime_id in the Anime model too.
        source_url = get_video_source(anime.slug, ep_number) 
        
        # Cache it for next time
        if source_url:
            if episode:
                episode.video_server_1 = source_url
                episode.is_available = True
            else:
                new_ep = Episode(anime_id=anime_id, episode_number=ep_number, video_server_1=source_url, is_available=True)
                db.session.add(new_ep)
            db.session.commit()
            
    return render_template('player.html', source_url=source_url, episode=episode)

@app.route('/add-anime', methods=['POST'])
def add_anime_auto():
    """
    Admin endpoint to add an anime by just pasting a HiAnime URL
    """
    hianime_url = request.form.get('url')
    data = scrape_anime_data(hianime_url)
    
    if not data:
        return "Failed to scrape data. Check URL."
        
    # Save to DB
    anime = Anime(title=data['title'], slug=data['title'].lower().replace(' ', '-'), image_url=data['image'])
    db.session.add(anime)
    db.session.flush() # Get ID
    
    for ep_info in data['episodes']:
        # Don't scrape all sources immediately to save bandwidth, 
        # just save the reference. Scrape source when user plays.
        ep = Episode(anime_id=anime.id, episode_number=ep_info['number'])
        db.session.add(ep)
        
    db.session.commit()
    return f"Added {data['title']} with {len(data['episodes'])} episodes!"

# --- BACKGROUND SCRAPER THREAD ---
def auto_update_loop():
    while True:
        # Check for Ongoing anime that are missing episodes
        ongoing_animes = Anime.query.filter_by(status='Ongoing').all()
        for anime in ongoing_animes:
            # Logic to check if latest episode exists in DB
            # If not, scrape the latest episode source and save it
            pass
        time.sleep(3600) # Run every hour

# Start background thread
threading.Thread(target=auto_update_loop, daemon=True).start()

if __name__ == '__main__':
    app.run(debug=True)
