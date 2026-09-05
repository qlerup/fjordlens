from app import app as application
from google_photo_frame import init_google_photo_frame
from google_photo_frame_picker import init_google_photo_frame_picker
from google_photo_frame_selection import init_google_photo_frame_selection
from privacy import init_privacy_page

# Register public/support pages and optional integrations without touching filesystem or DB at startup.
init_privacy_page(application)

# Google Photo Frame state remains lazy and is only read when its routes/UI are used.
init_google_photo_frame(application)
init_google_photo_frame_picker(application)
init_google_photo_frame_selection(application)

# Gunicorn expects a module-level 'application' or a named app; we expose 'application'.
