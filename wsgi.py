from app import app as application
from airplay_hls import init_airplay_hls
from cast_airplay import init_cast_airplay
from google_photo_frame import init_google_photo_frame
from google_photo_frame_picker import init_google_photo_frame_picker
from google_photo_frame_selection import init_google_photo_frame_selection
from privacy import init_privacy_page
from share_link_defaults import init_share_link_defaults

# Register public/support pages and optional integrations without touching filesystem or DB at startup.
init_privacy_page(application)

# Google Photo Frame state remains lazy and is only read when its routes/UI are used.
init_google_photo_frame(application)
init_google_photo_frame_picker(application)
init_google_photo_frame_selection(application)

# Share links automatically use the configured DNS base URL and require a visitor name for upload/manage links.
init_share_link_defaults(application)

# Mobile AirPlay / Google Cast sessions and the public custom Cast receiver.
init_cast_airplay(application)

# Incremental HLS for iOS AirPlay. The native Capacitor wrapper can start AVPlayer
# as soon as the first segments are ready while the rest is produced in background.
init_airplay_hls(application)

# Gunicorn expects a module-level 'application' or a named app; we expose 'application'.
