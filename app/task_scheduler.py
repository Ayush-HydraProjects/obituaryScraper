# app/task_scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import pytz
import logging

from app import scheduler, stop_event, db # Import scheduler, stop_event, db instances from app/__init__.py
from app.scraper import main # Import the scraper's main function


def is_last_day_of_month():
    """Check if today is the last day of the month in UTC."""
    logging.info("Checking is_last_day_of_month...") # Log when function is called
    tomorrow = datetime.now(pytz.utc) + timedelta(days=1)
    result = tomorrow.day == 1
    return result


def auto_scrape_job():
    """Automated scraping job to be run by scheduler."""
    logging.info("auto_scrape_job function called") # Log at start
    if is_last_day_of_month():
        logging.info("⏰ AUTOSCRAPE: is_last_day_of_month returned True") # Log when condition is met
        logging.info("⏰ AUTOSCRAPE: Last day of month detected, starting automated scrape")
        try:
            from flask import current_app # Import here to avoid circular import issue

            with current_app.app_context(): # Use current_app to get context
                db_session = db.session # Get session from db instance
                main(stop_event, db_session)  # Use your existing main function, pass stop_event and db_session
                logging.info("✅ AUTOSCRAPE: Monthly auto-scrape completed successfully")
        except Exception as e:
            logging.error(f"❌ AUTOSCRAPE ERROR inside try block: {str(e)}") # More specific error log
        finally:
            stop_event.set() # Use imported stop_event
    else:
        logging.info("auto_scrape_job: is_last_day_of_month returned False, skipping scrape.") # Log when not last day


def start_scheduler(): # Modified - no need to pass app for now, using current_app in job.
    """Starts the APScheduler, scheduling the auto_scrape_job."""
    # Scheduler is already initialized in app/__init__.py, using imported 'scheduler' instance

    # Run auto_scrape_job monthly
    scheduler.add_job(
        auto_scrape_job,  # Use auto_scrape_job again
        'cron',
        hour=0,
        minute=0,
        id='monthly_scrape' # Keep the same id
    )

    logging.info("⏲️  Scheduler job added - Auto-scrape job scheduled monthly.") # Updated log message