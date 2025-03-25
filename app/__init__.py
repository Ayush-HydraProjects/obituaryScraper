# app/__init__.py
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
import logging
import threading

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

db = SQLAlchemy()
migrate = Migrate()
scheduler = BackgroundScheduler(timezone=pytz.utc)  # Initialize scheduler

# --- Global variables to track scraper state --- in app/__init__.py
scrape_thread = None
stop_event = threading.Event()
last_scrape_time = None

from app.config import Config # Import Config class
from app.routes import bp as routes_bp # Import the blueprint
from app.task_scheduler import start_scheduler # Import start_scheduler function  <- Import start_scheduler

def create_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), '..', 'templates'),  # Portable template path (already modified)
        static_folder=os.path.join(os.path.dirname(__file__), '..', 'static')      # Portable static path - ADD THIS LINE
    )
    app.config.from_object(Config) # Load config from Config class

    db.init_app(app)
    migrate.init_app(app, db)

    # Register Blueprint Directly Here
    app.register_blueprint(routes_bp) # Register the blueprint

    # Import models here to be registered with SQLAlchemy
    from app import models  # Import models from the 'app' package

    start_scheduler()

    # Start scheduler
    scheduler.start()
    logging.info("Scheduler initialized and started.")

    return app

from app import models, routes, scraper, utils, task_scheduler # Make modules available under app package