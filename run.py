# run.py
from app import create_app, db, scheduler, stop_event  # Import create_app, db, scheduler
from app import create_app
from app.task_scheduler import start_scheduler # Import start_scheduler function

stop_event.set() # Setting stop_event to initially stop scraping as in original app.py

app = create_app()

if __name__ == "__main__":
    with app.app_context():
        # Access components through app extensions
        from app import db
        from app.task_scheduler import start_scheduler

        db.create_all()
        start_scheduler()

    app.run(host='0.0.0.0', debug=True)