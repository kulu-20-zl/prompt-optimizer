"""Production WSGI entry (Render / Railway)."""
import os

from werkzeug.middleware.proxy_fix import ProxyFix

from backend.app import create_app

app = create_app()

# Render / Railway 走 HTTPS 反向代理，修正 Scheme 与 Cookie
if os.getenv("FLASK_DEBUG", "1") != "1":
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
