# run.py
from app import create_app, db, scheduler, stop_event  # Import create_app, db, scheduler
from app.task_scheduler import start_scheduler # Import start_scheduler function

stop_event.set() # Setting stop_event to initially stop scraping as in original app.py

app = create_app() # Create Flask application instance


if __name__ == "__main__":
    with app.app_context(): # Push application context for db operations and scheduler start
        db.create_all() # Create database tables
        start_scheduler() # Start the scheduler
        # Optionally, you might want to set stop_event here if it's meant to start stopped initially
        pass

    app.run(host='0.0.0.0', debug=True) # Run the Flask development server