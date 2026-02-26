from app import app as application, init_db

# Ensure DB and directories exist on server start
try:
    init_db()
except Exception:
    # Swallow errors so the server can still boot; app routes also call ensure/init in critical paths.
    pass

# Gunicorn expects a module-level 'application' or a named app; we expose 'application'.
