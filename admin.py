"""Flask-Admin setup. Import and call init_admin(app) from app.py."""
from flask import redirect, session, url_for
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView

from models import db, Anime, Episode


class SecureAdminIndexView(AdminIndexView):
    @expose("/")
    def index(self):
        if not session.get("admin_authenticated"):
            return redirect(url_for("admin_login"))
        return super().index()

    def is_accessible(self):
        return bool(session.get("admin_authenticated"))

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for("admin_login", next="/admin/"))


class SecureModelView(ModelView):
    can_view_details = True
    page_size = 30

    def is_accessible(self):
        return bool(session.get("admin_authenticated"))

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for("admin_login"))


def init_admin(app):
    admin = Admin(
        app, name="AnimeZone Admin", index_view=SecureAdminIndexView(),
        template_mode="bootstrap4"
    )
    admin.add_view(SecureModelView(Anime, db.session, category="Catalog"))
    admin.add_view(SecureModelView(Episode, db.session, category="Catalog"))
    return admin


# Backwards-compatible exported object; app.py initializes its own bound admin.
admin = None
