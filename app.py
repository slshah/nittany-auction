import argparse
import os
import subprocess
import sys
from pathlib import Path

from flask import Flask
from flask_wtf.csrf import CSRFProtect

from auth_views import auth_bp
from bidder_views import bidder_bp
from config import get_settings
from helpdesk_views import helpdesk_bp
from seller_listings import seller_listings_bp
from seller_views import seller_bp

settings = get_settings()

app = Flask(__name__)
app.config["SECRET_KEY"] = settings.flask_secret_key
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
CSRFProtect(app)
app.register_blueprint(auth_bp)
app.register_blueprint(bidder_bp)
app.register_blueprint(seller_bp)
app.register_blueprint(helpdesk_bp)
app.register_blueprint(seller_listings_bp)


def parse_args():
    parser = argparse.ArgumentParser(description="Run NittanyAuction Flask app.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help=(
            "Reset and fully repopulate the Phase 2 database in strict mode "
            "before starting the app."
        ),
    )
    return parser.parse_args()


def should_run_startup_tasks(debug_enabled: bool) -> bool:
    # Flask debug reloader launches a parent and child process.
    return (not debug_enabled) or os.environ.get("WERKZEUG_RUN_MAIN") == "true"


def run_reset_phase2() -> None:
    project_root = Path(__file__).resolve().parent
    reset_script = project_root / "scripts" / "reset_phase2.py"
    subprocess.run(
        [
            sys.executable,
            str(reset_script),
        ],
        check=True,
        cwd=project_root,
    )


if __name__ == "__main__":
    args = parse_args()

    if args.reset and should_run_startup_tasks(settings.flask_debug):
        run_reset_phase2()

    app.run(debug=settings.flask_debug)
