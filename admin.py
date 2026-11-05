from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from models import db, Anime, Episode
from scraper import scrape_anime_data, get_video_source

class EpisodeInline(ModelView):
    can_create = True
    can_edit = True
    can_delete = True
    column_list = ('episode_number', 'is_available')

class AnimeModelView(ModelView):
    # Custom Column List
    column_list = ('title', 'slug', 'status', 'created_at')
    form_excluded_columns = ('episodes',) # We handle episodes separately or via inline
    
    # Custom Create Form to allow URL Input
    def create_form(self):
        form = super().create_form()
        # Add a custom field for HiAnime URL if you want manual trigger
        form.url_field = self._get_url_field()
        return form

    def on_model_change(self, form, model, is_created):
        if is_created:
            # If you have a URL field in your admin form, scrape it automatically
            # This part assumes you added a 'source_url' field to your admin form
            pass 

# Initialize Admin
admin = Admin(name='Anime Dashboard', template_mode='bootstrap4')
admin.add_view(ModelView(Anime, db.session, category='Content'))
admin.add_view(ModelView(Episode, db.session, category='Content'))
