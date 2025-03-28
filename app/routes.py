# app/routes.py
import logging
import os
from flask import render_template, jsonify, request, redirect, url_for, send_file, current_app
from flask import flash
from sqlalchemy import extract, func, text
from sqlalchemy.orm import aliased
from flask import Blueprint

from app import db, stop_event, scrape_thread, last_scrape_time  # Import db, global variables
from app.models import Obituary, DistinctObituary # Import models
from app.scraper import main # Import the scraper's main function
import threading
import time
import csv
from datetime import datetime

bp = Blueprint('routes', __name__) # Create a Blueprint instance


@bp.route('/')
def dashboard():
    """Route to display the scraper dashboard."""

    with current_app.app_context():
        total_alumni = DistinctObituary.query.distinct(DistinctObituary.name).count()
        total_obituaries = DistinctObituary.query.count()
        total_cities = len(set(obit.city for obit in DistinctObituary.query.all() if obit.city))
        latest_obituaries = DistinctObituary.query.limit(15).all()
        scraping_active = not stop_event.is_set() # Use imported stop_event
        response_data = { # Prepare data for template
            'total_alumni': total_alumni,
            'total_obituaries': total_obituaries,
            'total_cities': total_cities,
            'obituaries': latest_obituaries,
            'scraping_active': scraping_active,
            'last_scrape_time': last_scrape_time
        }
        return render_template('dashboard.html', **response_data)

@bp.route('/search_obituaries')
def search_obituaries():
    """Route to return search results as JSON for dashboard filtering.""" # Updated docstring
    first_name_query = request.args.get('firstName', '').strip()
    last_name_query = request.args.get('lastName', '').strip()
    city_query = request.args.get('city', '').strip()
    province_query = request.args.get('province', '').strip()
    query_string = request.args.get('query', '').strip()

    with current_app.app_context():
        query_filter = DistinctObituary.query.filter(DistinctObituary.is_alumni == True)

        # Advanced Search Filters
        if first_name_query:
            query_filter = query_filter.filter(DistinctObituary.first_name.ilike(f"%{first_name_query}%"))
        if last_name_query:
            query_filter = query_filter.filter(DistinctObituary.last_name.ilike(f"%{last_name_query}%"))
        if city_query:
            query_filter = query_filter.filter(DistinctObituary.city.ilike(f"%{city_query}%"))
        if province_query and province_query != '':
            query_filter = query_filter.filter(DistinctObituary.province == province_query)


        if query_string: # Simple search - if general query is present, it takes precedence
             query_filter = DistinctObituary.query.filter(
                (DistinctObituary.first_name.ilike(f"%{query_string}%")) |
                (DistinctObituary.last_name.ilike(f"%{query_string}%")) |
                 (DistinctObituary.family_information.ilike(f"%{query_string}%")) # Assuming content exists in DistinctObituary
            )

        obituaries = query_filter.order_by(DistinctObituary.last_name).all()

        obituary_list = [{  # Prepare obituary data as dictionaries for JSON response
            'id': obit.id,
            'name': obit.name,
            'first_name': obit.first_name,
            'last_name': obit.last_name,
            'obituary_url': obit.obituary_url,
            'city': obit.city,
            'province': obit.province,
            'birth_date': obit.birth_date,
            'death_date': obit.death_date,
            'publication_date': obit.publication_date,
            'is_alumni': obit.is_alumni,
            'tags': obit.tags,
            'latitude': obit.latitude,
            'longitude': obit.longitude,
        } for obit in obituaries]

        return jsonify(obituary_list)


@bp.route('/get_obituaries')
def get_obituaries():
    """Route to fetch distinct alumni obituaries data, ordered by city and publication date."""
    with current_app.app_context():
        # Subquery to rank entries by name and publication date
        subquery = db.session.query(
            DistinctObituary,
            func.row_number().over(
                partition_by=DistinctObituary.name,  # Group by name
                order_by=DistinctObituary.publication_date.desc()  # Latest first
            ).label('row_num')
        ).subquery()

        # Create an alias to map back to our model
        ObituaryAlias = aliased(DistinctObituary, subquery)

        # Get only the latest entry per name
        obituaries = db.session.query(ObituaryAlias).\
            filter(subquery.c.row_num == 1).\
            order_by(ObituaryAlias.publication_date.desc()).\
            all()

        obituary_list = [{
            'id': obit.id,
            'name': obit.name,
            'first_name': obit.first_name,
            'last_name': obit.last_name,
            'obituary_url': obit.obituary_url,
            'city': obit.city,
            'province': obit.province,
            'birth_date': obit.birth_date,
            'death_date': obit.death_date,
            'publication_date': obit.publication_date,
            'is_alumni': obit.is_alumni,
            'tags': obit.tags,
            'latitude': obit.latitude,
            'longitude': obit.longitude,
        } for obit in obituaries]
        return jsonify(obituary_list)

@bp.route('/api/publications/grouped-by-year')
def get_publications_by_year_endpoint():
    """API endpoint to get publications grouped by year."""
    publications_by_year = get_publications_grouped_by_year()
    if publications_by_year:
        return jsonify(publications_by_year)
    else:
        return jsonify({"error": "Failed to fetch publications by year"}), 500


def get_publications_grouped_by_year():
    """
+   Fetches publications from the database, grouped by publication year,
+   and categorized into year groups (2025, 2024, 2023, 2022, <2022).
+   """
    try:
        result = (
            db.session.query(
                extract('year', DistinctObituary.publication_date).label('publication_year'),
                func.json_agg(func.json_build_object(
                    'id', DistinctObituary.id,
                    'name', DistinctObituary.name,
                    'first_name', DistinctObituary.first_name,
                    'last_name', DistinctObituary.last_name,
                    'obituary_url', DistinctObituary.obituary_url,
                    'city', DistinctObituary.city,
                    'province', DistinctObituary.province,
                    'birth_date', DistinctObituary.birth_date,
                    'death_date', DistinctObituary.death_date,
                    'publication_date', DistinctObituary.publication_date,
                    'is_alumni', DistinctObituary.is_alumni,
                    'tags', DistinctObituary.tags
                )).label('publications_in_year')
            )
            .group_by(extract('year', DistinctObituary.publication_date))
            .order_by(text('publication_year DESC'))
            .all()
        )

        grouped_data = {
            "2025": [], "2024": [], "2023": [], "2022": [], "Before 2022": []
        }

        for row in result:
            year = row.publication_year
            year_str = str(int(year)) if year else None # Convert year to string for dictionary key
            if year_str in grouped_data: # Check if year_str is a key in grouped_data
                grouped_data[year_str] = list(row.publications_in_year) if row.publications_in_year else [] # Ensure it's a list
            elif year and year < 2022:
                grouped_data["Before 2022"].extend(list(row.publications_in_year) if row.publications_in_year else []) # Extend for <2022 group

        return grouped_data
    except Exception as e:
        print(f"Database error fetching publications by year: {e}")
        return None


@bp.route('/update_tags/<int:obituary_id>', methods=['POST'])
def update_tags(obituary_id):
    new_tags = request.form.get('tags')
    temp_obituary_id = None # Temporary variable to store obituary_id

    # Update Obituary
    with current_app.app_context():
        obituary = DistinctObituary.query.get_or_404(obituary_id)
        obituary.tags = new_tags

        # Update DistinctObituary if exists
        distinct_obit = DistinctObituary.query.filter_by(
            obituary_url=obituary.obituary_url
        ).first()
        if distinct_obit:
            distinct_obit.tags = new_tags

        db.session.commit()
        temp_obituary_id = obituary.id # Fetch and store obituary.id WHILE INSIDE app context

    return redirect(url_for('routes.obituary_detail', obituary_id=temp_obituary_id))


@bp.route('/start_scrape', methods=['POST'])
def start_scrape(last_scrape_time=None):
    """Route to start the scraper in a background thread."""

    if not stop_event.is_set():
        response_data = {
            'message': 'Scraping is already running!',
            'scraping_active': not stop_event.is_set(),
            'last_scrape_time': last_scrape_time.isoformat() if last_scrape_time else None
        }
        return jsonify(response_data), 400

    stop_event.clear()

    csv_file_path = "obituaries_data.csv"
    if os.path.exists(csv_file_path):
        open(csv_file_path, 'w').close()

    def run_scraper_with_session(stop_event, app):
        with app.app_context():
            db_session = db.session
            main(stop_event, db_session)

    scrape_thread = threading.Thread(
        target=run_scraper_with_session,
        args=(stop_event, current_app._get_current_object())
    )
    scrape_thread.start()

    last_scrape_time = datetime.now()

    response_data = {
        'message': 'Scraping started in the background.',
        'scraping_active': True,
        'last_scrape_time': last_scrape_time.isoformat()
    }
    return jsonify(response_data)


@bp.route('/stop_scrape', methods=['POST'])
def stop_scrape(last_scrape_time=None):
    """Route to stop the scraper (set event to stop gracefully)."""

    if stop_event.is_set():
        response_data = {
            'message': 'Scraping is not currently running!',
            'scraping_active': not stop_event.is_set(),
            'last_scrape_time': last_scrape_time.isoformat() if last_scrape_time else None
        }
        return jsonify(response_data), 400

    stop_event.set()
    time.sleep(2) # Keep delay for testing

    last_scrape_time = datetime.now()

    response_data = {
        'message': 'Stopping scraping...',
        'scraping_active': False,
        'last_scrape_time': last_scrape_time.isoformat()
    }
    return jsonify(response_data)


@bp.route('/scrape_status')
def scrape_status():
    """Route to get the current scraping status."""

    response_data = {
        'scraping_active': not stop_event.is_set(),
        'last_scrape_time': last_scrape_time.isoformat() if last_scrape_time else None
    }
    return jsonify(response_data)


def run_scraper_background(stop_event): # This function seems unused in routes.py, but was in original app.py. Keeping it here just in case, if not used, it can be removed.
    """Function to run the scraper in the background thread."""
    logging.info("Scraper background thread started.")
    try:
        main(stop_event, db.session) # Pass db.session and stop_event
    except Exception as e:
        logging.error(f"Scraper background thread encountered an error: {e}")
    finally:
        # Automatically stop when done
        with current_app.app_context():
            try:
                client = current_app.test_client()
                client.post('/stop_scrape')
                logging.info("Automatic stop triggered after completion")
            except Exception as e:
                logging.error(f"Error triggering automatic stop: {e}")
        logging.info("Scraper background thread finished.")


@bp.route('/obituary/<int:obituary_id>')
def obituary_detail(obituary_id):
    """Route to display details for a specific obituary."""
    with current_app.app_context():
        obituary = DistinctObituary.query.get_or_404(obituary_id) # Fetch from DistinctObituary, or Obituary if you prefer
        return render_template('obituary_detail.html', obituary=obituary)


def generate_csv():
    """Helper function to generate a fresh CSV file from the database."""
    with current_app.app_context():
        obituaries = DistinctObituary.query.order_by(DistinctObituary.publication_date.desc()).all()

        if not obituaries:
            return None  # No data available

        csv_file_path = "obituaries_data.csv"

        with open(csv_file_path, 'w', newline='') as csvfile:
            fieldnames = ['id', 'name', 'first_name', 'last_name', 'city', 'province', 'birth_date',
                          'death_date', 'obituary_url', 'tags'] # Added tags
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for obit in obituaries:
                writer.writerow({
                    'id': obit.id,
                    'name': obit.name,
                    'first_name': obit.first_name,
                    'last_name': obit.last_name,
                    'obituary_url': obit.obituary_url,
                    'city': obit.city,
                    'province': obit.province,
                    'birth_date': obit.birth_date,
                    'death_date': obit.death_date,
                    'tags': obit.tags, # Added tags
                })

        return csv_file_path  # Return the file path


@bp.route('/download_csv')
def download_csv():
    """Route to generate and download obituaries data as CSV."""
    csv_file = generate_csv()  # Generate CSV before downloading
    if not csv_file:
        return jsonify({'error': 'No obituaries available to download'}), 404

    return send_file(csv_file, as_attachment=True, download_name="obituaries.csv", mimetype="text/csv")


@bp.route('/about')
def about():
    """Route to display the About page."""
    return render_template('about.html')

def init_app(app): # Initialization function to register blueprint
    app.register_blueprint(bp)