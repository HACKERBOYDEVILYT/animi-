import os
import re
import secrets
from datetime import datetime, timezone
from urllib.parse import urlparse

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for, flash
from sqlalchemy import inspect, text
from werkzeug.security import check_password_hash

from models import db, Anime, Episode
from scraper import search_jikan, get_jikan_anime, scrape_anime_data

load_dotenv()

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY", "dev-only-change-this-secret"),
    SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "sqlite:///anime.db").replace(
        "postgres://", "postgresql://", 1
    ),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    JSON_SORT_KEYS=False,
)
db.init_app(app)


def _slugify(value):
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:90] or secrets.token_hex(6)


def _unique_slug(title, current_id=None):
    base = _slugify(title)
    slug, suffix = base, 2
    while True:
        query = Anime.query.filter_by(slug=slug)
        if current_id:
            query = query.filter(Anime.id != current_id)
        if not query.first():
            return slug
        slug = f"{base[:85]}-{suffix}"
        suffix += 1


def _safe_migrate_legacy_sqlite():
    """Additive SQLite migration; existing Anime/Episode rows are preserved."""
    if not app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
        return
    inspector = inspect(db.engine)
    if "anime" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("anime")}
        additions = {
            "external_id": "VARCHAR(80)",
            "source_name": "VARCHAR(40) DEFAULT 'manual'",
            "updated_at": "DATETIME",
        }
        with db.engine.begin() as conn:
            for name, sql_type in additions.items():
                if name not in cols:
                    conn.execute(text(f"ALTER TABLE anime ADD COLUMN {name} {sql_type}"))
            conn.execute(text(
                "UPDATE anime SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL"
            ))


with app.app_context():
    db.create_all()
    _safe_migrate_legacy_sqlite()


@app.context_processor
def inject_language():
    return {"current_language": session.get("language", "bn")}


@app.route("/language/<lang>")
def set_language(lang):
    if lang not in ("bn", "en"):
        abort(404)
    session["language"] = lang
    return redirect(request.referrer or url_for("home"))


@app.route("/")
def home():
    animes = Anime.query.order_by(Anime.created_at.desc()).limit(24).all()
    return render_template("index.html", animes=animes)


@app.route("/anime/<slug>")
def anime_detail(slug):
    anime = Anime.query.filter_by(slug=slug).first_or_404()
    episodes = Episode.query.filter_by(anime_id=anime.id).order_by(
        Episode.episode_number.asc()
    ).all()
    return render_template("anime_detail.html", anime=anime, episodes=episodes)


@app.route("/play/<int:anime_id>/<int:ep_number>")
def play_episode(anime_id, ep_number):
    anime = db.session.get(Anime, anime_id)
    if anime is None:
        abort(404)
    episode = Episode.query.filter_by(
        anime_id=anime_id, episode_number=ep_number
    ).first()
    # Legacy links remain valid. Only already configured, authorized sources play.
    source_url = None
    if episode:
        source_url = episode.video_server_1 or episode.video_server_2
        if source_url and urlparse(source_url).scheme not in ("https", "http"):
            source_url = None
    return render_template(
        "player.html", source_url=source_url, episode=episode,
        anime=anime, episode_number=ep_number
    )


@app.route("/api/v1/anime")
def api_anime_list():
    page = max(1, request.args.get("page", 1, type=int))
    per_page = min(50, max(1, request.args.get("per_page", 20, type=int)))
    query = Anime.query
    search = (request.args.get("q") or "").strip()
    if search:
        query = query.filter(Anime.title.ilike(f"%{search[:100]}%"))
    status = request.args.get("status")
    if status in ("Ongoing", "Completed"):
        query = query.filter_by(status=status)
    pagination = query.order_by(Anime.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return jsonify({
        "data": [{
            "id": a.id, "title": a.title, "slug": a.slug,
            "image_url": a.image_url, "description": a.description,
            "status": a.status, "episode_count": len(a.episodes),
            "detail_url": url_for("anime_detail", slug=a.slug, _external=True),
        } for a in pagination.items],
        "pagination": {
            "page": pagination.page, "per_page": pagination.per_page,
            "total": pagination.total, "pages": pagination.pages,
        },
    })


@app.route("/api/v1/anime/<slug>")
def api_anime_detail(slug):
    anime = Anime.query.filter_by(slug=slug).first_or_404()
    return jsonify({
        "id": anime.id, "title": anime.title, "slug": anime.slug,
        "image_url": anime.image_url, "description": anime.description,
        "status": anime.status,
        "episodes": [{
            "id": ep.id, "episode_number": ep.episode_number,
            "title": ep.title, "is_available": ep.is_available,
            "play_url": url_for("play_episode", anime_id=anime.id,
                                ep_number=ep.episode_number, _external=True),
        } for ep in anime.episodes],
    })


@app.route("/api/v1/providers/jikan/search")
def api_jikan_search():
    query = (request.args.get("q") or "").strip()
    if len(query) < 2:
        return jsonify({"error": "q must contain at least 2 characters"}), 400
    try:
        return jsonify({"data": search_jikan(query)})
    except Exception:
        app.logger.exception("Jikan search failed")
        return jsonify({"error": "Metadata provider temporarily unavailable"}), 502


def _save_metadata(data):
    title = (data.get("title") or "").strip()[:200]
    if not title:
        raise ValueError("Anime title is required")
    external_id = str(data.get("external_id") or "").strip() or None
    anime = Anime.query.filter_by(external_id=external_id).first() if external_id else None
    if anime is None:
        anime = Anime.query.filter_by(title=title).first()
    if anime is None:
        anime = Anime(title=title, slug=_unique_slug(title))
        db.session.add(anime)
    anime.title = title
    anime.slug = _unique_slug(title, anime.id)
    anime.image_url = data.get("image")
    anime.description = data.get("description") or ""
    anime.status = data.get("status") or "Ongoing"
    anime.external_id = external_id
    anime.source_name = data.get("source_name", "manual")
    db.session.commit()
    return anime


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = os.getenv("ADMIN_USERNAME", "")
        password_hash = os.getenv("ADMIN_PASSWORD_HASH", "")
        supplied_user = request.form.get("username", "")
        supplied_password = request.form.get("password", "")
        if (username and password_hash and secrets.compare_digest(supplied_user, username)
                and check_password_hash(password_hash, supplied_password)):
            session.clear()
            session["admin_authenticated"] = True
            session["language"] = session.get("language", "bn")
            return redirect(request.args.get("next") or url_for("admin_dashboard"))
        flash("Login failed. Check your credentials.", "error")
    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_authenticated", None)
    return redirect(url_for("home"))


@app.route("/admin")
def admin_dashboard():
    if not session.get("admin_authenticated"):
        return redirect(url_for("admin_login"))
    return render_template("admin_dashboard.html", anime_count=Anime.query.count(),
                           episode_count=Episode.query.count())


@app.route("/admin/add-anime", methods=["POST"])
@app.route("/add-anime", methods=["POST"])
def add_anime_auto():
    # Legacy endpoint is preserved but now protected.
    if not session.get("admin_authenticated"):
        if request.is_json:
            return jsonify({"error": "authentication_required"}), 401
        return redirect(url_for("admin_login"))
    payload = request.get_json(silent=True) or request.form
    try:
        if payload.get("mal_id"):
            data = get_jikan_anime(payload["mal_id"])
        elif payload.get("url"):
            data = scrape_anime_data(payload.get("url"))
            if not data:
                return jsonify({"error": "Could not read metadata from that URL"}), 422
        else:
            return jsonify({"error": "Provide mal_id or a supported metadata URL"}), 400
        anime = _save_metadata(data)
        return jsonify({"message": "Anime saved", "id": anime.id,
                        "slug": anime.slug, "title": anime.title}), 201
    except (ValueError, TypeError):
        db.session.rollback()
        return jsonify({"error": "Invalid anime data"}), 400
    except Exception:
        db.session.rollback()
        app.logger.exception("Failed to add anime")
        return jsonify({"error": "Could not save anime"}), 500


@app.route("/admin/sync-jikan/<int:mal_id>", methods=["POST"])
def admin_sync_jikan(mal_id):
    if not session.get("admin_authenticated"):
        abort(401)
    try:
        anime = _save_metadata(get_jikan_anime(mal_id))
        return jsonify({"message": "Metadata synced", "id": anime.id, "slug": anime.slug})
    except Exception:
        db.session.rollback()
        app.logger.exception("Jikan sync failed")
        return jsonify({"error": "Metadata sync failed"}), 502


@app.errorhandler(404)
def not_found(error):
    if request.path.startswith("/api/"):
        return jsonify({"error": "not_found"}), 404
    return render_template("error.html", code=404, message="Page not found"), 404


@app.errorhandler(500)
def server_error(error):
    db.session.rollback()
    app.logger.exception("Unhandled server error")
    if request.path.startswith("/api/"):
        return jsonify({"error": "internal_server_error"}), 500
    return render_template("error.html", code=500, message="Something went wrong"), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")),
            debug=os.getenv("FLASK_DEBUG", "0") == "1")
