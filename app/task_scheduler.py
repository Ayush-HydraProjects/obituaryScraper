# app/task_scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import pytz
import logging
import atexit

from app import scheduler, stop_event, db
from app.scraper import main


def is_last_day_of_month():
    """Check if today is the last day of the month in UTC."""
    logging.info("Checking is_last_day_of_month...")
    tomorrow = datetime.now(pytz.utc) + timedelta(days=1)
    return tomorrow.day == 1


def auto_scrape_job():
    """Automated scraping job to be run by scheduler."""
    logging.info("auto_scrape_job function called")
    if is_last_day_of_month():
        logging.info("⏰ AUTOSCRAPE: Last day of month detected, starting automated scrape")
        try:
            from flask import current_app

            with current_app.app_context():
                db_session = db.session
                main(stop_event, db_session)
                logging.info("✅ AUTOSCRAPE: Monthly auto-scrape completed successfully")
        except Exception as e:
            logging.error(f"❌ AUTOSCRAPE ERROR: {str(e)}")
        finally:
            stop_event.set()
    else:
        logging.info("Skipping scrape - not last day of month")


def start_scheduler():
    """Starts the APScheduler with proper job management."""
    try:
        if not scheduler.running:
            # Remove existing job if present
            if scheduler.get_job('monthly_scrape'):
                scheduler.remove_job('monthly_scrape')

            # Add new job
            scheduler.add_job(
                auto_scrape_job,
                'cron',
                hour=0,
                minute=0,
                id='monthly_scrape',
                replace_existing=True
            )

            # Start only if not already running
            if not scheduler.running:
                scheduler.start()
                logging.info("⏲️ MAIN SCHEDULER STARTED")

    except Exception as e:
        logging.error(f"Scheduler error: {str(e)}")


def shutdown_scheduler():
    """Properly shutdown the scheduler"""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logging.info("Scheduler shut down")