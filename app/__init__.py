# app/__init__.py
import os
from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
import logging
import threading
from flask_mail import Mail

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

db = SQLAlchemy()
migrate = Migrate()
mail = Mail()
scheduler = BackgroundScheduler(timezone=pytz.utc)

# Global variables to track scraper state
scrape_thread = None
stop_event = threading.Event()
last_scrape_time = None

from app.config import Config
from app.routes import bp as routes_bp
from app.task_scheduler import start_scheduler

def create_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), '..', 'templates'),
        static_folder=os.path.join(os.path.dirname(__file__), '..', 'static')
    )
    app.config.from_object(Config)

    app.config.update(
        MAIL_SERVER='smtp.gmail.com',
        MAIL_PORT=587,
        MAIL_USE_TLS=True,
        MAIL_USERNAME='rememberinglancers@gmail.com',  # Must match exactly
        MAIL_PASSWORD='zcim whvt xrvf beay',  # Not your Gmail password
        MAIL_DEFAULT_SENDER=('Lancers Updates', 'rememberinglancers@gmail.com')
    )

    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    app.register_blueprint(routes_bp)

    # Import models after db initialization
    from app import models

    # Prevent duplicate scheduler in Flask debug mode
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        with app.app_context():
            if not scheduler.running:
                try:
                    start_scheduler()
                    logging.info("Scheduler PROPERLY initialized")
                except Exception as e:
                    logging.error(f"Scheduler initialization failed: {str(e)}")
            else:
                logging.warning("Scheduler already running - skipping reinitialization")

    # Replace teardown with proper shutdown
    def shutdown_scheduler_on_exit():
        if scheduler.running:
            scheduler.shutdown(wait=False)
            logging.info("Scheduler stopped during app exit")

    import atexit
    atexit.register(shutdown_scheduler_on_exit)

    return app