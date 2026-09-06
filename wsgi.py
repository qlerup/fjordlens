from app import app as application
from airplay_controls import init_airplay_controls
from airplay_hls import init_airplay_hls
from airplay_seek_fix import init_airplay_seek_fix
from cast_airplay import init_cast_airplay
from google_photo_frame import init_google_photo_frame
from google_photo_frame_picker import init_google_photo_frame_picker
from google_photo_frame_selection import init_google_photo_frame_selection
from people_section import init_people_section
from privacy import init_privacy_page
from safe_airplay_assets import init_safe_airplay_assets
from share_link_defaults import init_share_link_defaults

# Register public/support pages and optional integrations without touching filesystem or DB at startup.
init_privacy_page(application)

# Speed up the People view and give media managers the People-specific actions
# without widening access to system maintenance/settings.
init_people_section(application)

# Google Photo Frame state remains lazy and is only read when its routes/UI are used.
init_google_photo_frame(application)
init_google_photo_frame_picker(application)
init_google_photo_frame_selection(application)

# Share links automatically use the configured DNS base URL and require a visitor name for upload/manage links.
init_share_link_defaults(application)

# Disable the two older AirPlay frontend injectors before their blueprints are initialized.
# Their backend routes are still registered; the lightweight cache-busted clients below replace only the UI scripts.
application.extensions["cast_airplay_assets_registered"] = True
application.extensions["airplay_hls_assets_registered"] = True

# Mobile AirPlay / Google Cast sessions and the public custom Cast receiver.
init_cast_airplay(application)

# Incremental HLS for iOS AirPlay.
init_airplay_hls(application)

# Slideshow duration settings and phone-side seek/previous/next controls.
init_airplay_controls(application)

# Safari/WebKit needs a more defensive HLS seek implementation around discontinuities.
init_airplay_seek_fix(application)

# Safe mobile clients: no global MutationObserver and no monkey-patching window.fetch.
init_safe_airplay_assets(application)

# Gunicorn expects a module-level 'application' or a named app; we expose 'application'.
