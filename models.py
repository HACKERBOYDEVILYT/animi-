from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint

db = SQLAlchemy()


class Anime(db.Model):
    __tablename__ = "anime"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)
    image_url = db.Column(db.String(500))
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default="Ongoing", index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Additive fields: old SQLite databases are upgraded by app.py's safe migration.
    external_id = db.Column(db.String(80), unique=True, nullable=True, index=True)
    source_name = db.Column(db.String(40), default="manual")
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    episodes = db.relationship(
        "Episode", backref="anime", lazy=True,
        cascade="all, delete-orphan", order_by="Episode.episode_number"
    )

    def __repr__(self):
        return f"<Anime {self.title}>"


class Episode(db.Model):
    __tablename__ = "episode"
    __table_args__ = (
        UniqueConstraint("anime_id", "episode_number", name="uq_episode_anime_number"),
    )

    id = db.Column(db.Integer, primary_key=True)
    anime_id = db.Column(db.Integer, db.ForeignKey("anime.id"), nullable=False, index=True)
    episode_number = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(200))
    # These legacy columns are intentionally retained. Only store authorized stream URLs.
    video_server_1 = db.Column(db.String(500))
    video_server_2 = db.Column(db.String(500))
    is_available = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"<Episode {self.anime_id}:{self.episode_number}>"
