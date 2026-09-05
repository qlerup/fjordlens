from app import app as application
from google_photo_frame import init_google_photo_frame
from privacy import init_privacy_page

# Register public/support pages and optional integrations without touching filesystem or DB at startup.
init_privacy_page(application)

# Google Photo Frame state remains lazy and is only read when its routes/UI are used.
init_google_photo_frame(application)

# Gunicorn expects a module-level 'application' or a named app; we expose 'application'.
