#akta anime website banaisi akahon hi anime je api use kore ta koi pabo ba hi anime ar api use kore akta anime website banaiya dite parba admin panel soho , jekhane kono pokar video manually upload  kora lagbo na fully automatic jeno upload  from flask_sqlalchemy import SQLAlchemy
from flask_admin.contrib.sqla import Model
import datetime

db = SQLAlchemy()

class Anime(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False) # URL friendly name
    image_url = db.Column(db.String(500))
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default="Ongoing")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # One-to-Many Relationship for Episodes
    episodes = db.relationship('Episode', backref='anime', lazy=True, cascade="all, delete-orphan")

class Episode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    anime_id = db.Column(db.Integer, db.ForeignKey('anime.id'), nullable=False)
    episode_number = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(200))
    video_server_1 = db.Column(db.String(500)) # Primary Stream Link
    video_server_2 = db.Column(db.String(500)) # Backup Stream Link
    is_available = db.Column(db.Boolean, default=False)
    
    def __repr__(self):
        return f'<Episode {self.anime.title} Ep {self.episode_number}>'
