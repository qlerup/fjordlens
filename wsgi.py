from app import app as application
from google_photo_frame import init_google_photo_frame

# Register optional integrations without touching filesystem or DB at startup.
# Google Photo Frame state remains lazy and is only read when its routes/UI are used.
init_google_photo_frame(application)

# Gunicorn expects a module-level 'application' or a named app; we expose 'application'.
