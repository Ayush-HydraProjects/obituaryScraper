# app/routes.py
import io
import logging
import os
from flask import render_template, jsonify, request, redirect, url_for, send_file, current_app, stream_with_context, \
    Response
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
import tempfile

from app import mail # Import mail instance from _init_
from flask_mail import Message


def get_filtered_obituaries(filters):
    """Filters DistinctObituary based on a dictionary of filters."""
    with current_app.app_context():
        query = DistinctObituary.query

        # Handle text filters
        if filters.get('firstName'):
            query = query.filter(DistinctObituary.first_name.ilike(f"%{filters['firstName']}%"))
        if filters.get('lastName'):
            query = query.filter(DistinctObituary.last_name.ilike(f"%{filters['lastName']}%"))
        if filters.get('city'):
            query = query.filter(DistinctObituary.city.ilike(f"%{filters['city']}%"))
        if filters.get('province') and filters.get('province') != '':
            query = query.filter(DistinctObituary.province == filters['province'])

        # Handle month/year filter
        if filters.get('month_year'):
            try:
                year, month = map(int, filters['month_year'].split('-'))
                query = query.filter(
                    extract('year', DistinctObituary.publication_date) == year,
                    extract('month', DistinctObituary.publication_date) == month
                )
            except (ValueError, AttributeError) as e:
                logging.warning(f"Invalid month_year format: {filters['month_year']} - {str(e)}")

        obituaries = query.order_by(DistinctObituary.publication_date.desc()).all()
        logging.info(f"Filtering found {len(obituaries)} obituaries. Filters: {filters}")
        return obituaries

def generate_csv_in_memory(obituaries):
    """Generates CSV data in memory from obituary list."""
    if not obituaries: return None
    output = io.StringIO()
    fieldnames = ['id', 'name', 'first_name', 'last_name', 'city', 'province','birth_date', 'death_date', 'publication_date', 'obituary_url','tags', 'funeral_home', 'latitude', 'longitude']
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()
    for obit in obituaries:
        writer.writerow({
            'id': obit.id, 'name': obit.name, 'first_name': obit.first_name,'last_name': obit.last_name, 'city': obit.city, 'province': obit.province,
            'birth_date': obit.birth_date, 'death_date': obit.death_date,'publication_date': obit.publication_date.strftime('%Y-%m-%d') if obit.publication_date else '',
            'obituary_url': obit.obituary_url, 'tags': obit.tags,'funeral_home': obit.funeral_home, 'latitude': obit.latitude,'longitude': obit.longitude,})
    csv_data = output.getvalue()
    output.close()
    return csv_data


def send_report_email(subject, recipients, html_body, attachments=None):
    """Sends email using Flask-Mail."""
    if not recipients:
        logging.warning("No recipients for email.")
        return False

    try:
        # Get sender from config
        sender = current_app.config.get('MAIL_DEFAULT_SENDER')
        if not sender:
            logging.error("Mail sender not configured")
            return False

        # Create message with proper sender
        msg = Message(
            subject,
            sender=sender,
            recipients=recipients,
            html=html_body
        )

        # Attach CSV file
        if attachments:
            for filename, content_type, data in attachments:
                msg.attach(filename, content_type, data)

        mail.send(msg)
        logging.info(f"Email sent successfully to {', '.join(recipients)}")
        return True
    except Exception as e:
        logging.error(f"Failed to send email: {e}", exc_info=True)
        return False

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
            'last_scrape_time': last_scrape_time,
            'datetime': datetime
        }
        return render_template('dashboard.html', **response_data)


@bp.route('/search_obituaries')
def search_obituaries():
    """Return unique obituaries matching search criteria, eliminating duplicates"""
    # Get search parameters
    first_name = request.args.get('firstName', '').strip()
    last_name = request.args.get('lastName', '').strip()
    city = request.args.get('city', '').strip()
    province = request.args.get('province', '').strip()
    query = request.args.get('query', '').strip()

    with current_app.app_context():
        # Subquery to find latest version of each obituary
        grouped_obits = db.session.query(
            DistinctObituary.first_name,
            DistinctObituary.last_name,
            DistinctObituary.birth_date,
            DistinctObituary.death_date,
            func.max(DistinctObituary.id).label('max_id')
        ).filter(
            DistinctObituary.is_alumni == True
        ).group_by(
            DistinctObituary.first_name,
            DistinctObituary.last_name,
            DistinctObituary.birth_date,
            DistinctObituary.death_date
        ).subquery('grouped_obits')

        # Main query joining with grouped results
        base_query = db.session.query(DistinctObituary).join(
            grouped_obits,
            (DistinctObituary.id == grouped_obits.c.max_id)
        )

        # Apply filters cumulatively
        if first_name:
            base_query = base_query.filter(
                DistinctObituary.first_name.ilike(f"%{first_name}%")
            )
        if last_name:
            base_query = base_query.filter(
                DistinctObituary.last_name.ilike(f"%{last_name}%")
            )
        if city:
            base_query = base_query.filter(
                DistinctObituary.city.ilike(f"%{city}%")
            )
        if province:
            base_query = base_query.filter(
                DistinctObituary.province == province
            )
        if query:
            base_query = base_query.filter(
                (DistinctObituary.first_name.ilike(f"%{query}%")) |
                (DistinctObituary.last_name.ilike(f"%{query}%")) |
                (DistinctObituary.family_information.ilike(f"%{query}%"))
            )

        # Execute and format results
        results = base_query.order_by(DistinctObituary.last_name).all()

        return jsonify([{
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
        } for obit in results])


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


def generate_csv_to_file():
    """Helper function to generate a fresh CSV file of ALL data to a temporary file."""
    with current_app.app_context():
        obituaries = DistinctObituary.query.order_by(DistinctObituary.publication_date.desc()).all()
        if not obituaries:
            logging.warning("generate_csv_to_file: No obituaries found.")
            return None # Return None if no data

        # Use tempfile for reliable temporary file creation
        try:
            # delete=False is important so the file isn't deleted when the 'with' block exits
            # It allows send_file to access it later. We clean it up manually in the route.
            with tempfile.NamedTemporaryFile(mode='w', newline='', encoding='utf-8', suffix='.csv', delete=False) as temp_csv_file:
                csv_file_path = temp_csv_file.name # Get the absolute path
                logging.info(f"Generating temporary CSV for all data at: {csv_file_path}")

                fieldnames = ['id', 'name', 'first_name', 'last_name', 'city', 'province',
                              'birth_date', 'death_date', 'publication_date',
                              'obituary_url', 'tags', 'funeral_home',
                              'latitude', 'longitude']
                writer = csv.DictWriter(temp_csv_file, fieldnames=fieldnames, extrasaction='ignore')
                writer.writeheader()
                for obit in obituaries:
                    writer.writerow({
                        'id': obit.id, 'name': obit.name, 'first_name': obit.first_name,
                        'last_name': obit.last_name, 'city': obit.city, 'province': obit.province,
                        'birth_date': obit.birth_date, 'death_date': obit.death_date,
                        'publication_date': obit.publication_date.strftime('%Y-%m-%d') if obit.publication_date else '',
                        'obituary_url': obit.obituary_url, 'tags': obit.tags,
                        'funeral_home': obit.funeral_home, 'latitude': obit.latitude,
                        'longitude': obit.longitude,
                    })
            # File is now written and closed, but still exists because delete=False
            logging.info(f"Successfully generated temporary CSV: {csv_file_path} with {len(obituaries)} entries.")
            return csv_file_path # Return the path

        except IOError as e:
            logging.error(f"Error writing temporary CSV: {e}")
            # Attempt cleanup if file path was obtained and file exists
            if 'csv_file_path' in locals() and os.path.exists(csv_file_path):
                try: os.remove(csv_file_path)
                except OSError as remove_error: logging.error(f"Error removing partial CSV {csv_file_path}: {remove_error}")
            return None # Return None on error
        except Exception as e: # Catch other potential errors during file creation
            logging.error(f"Unexpected error during temp file creation: {e}")
            return None


@bp.route('/download_csv')
def download_csv():
    """Route to generate and download ALL obituaries data as CSV."""
    logging.info("Request received for downloading all data CSV.")
    csv_file_path = generate_csv_to_file() # Uses the helper below
    if not csv_file_path:
        flash('No obituaries available to download.', 'warning')
        logging.warning("No data available for 'Download All CSV'. Redirecting.")
        return redirect(url_for('routes.dashboard'))

    try:
        logging.info(f"Sending temporary CSV file: {csv_file_path}")
        return send_file(
            csv_file_path,
            as_attachment=True,
            download_name="all_lancers_obituaries.csv",
            mimetype="text/csv"
        )
    finally:
        if csv_file_path and os.path.exists(csv_file_path):
             try:
                 os.remove(csv_file_path)
                 logging.info(f"Removed temporary CSV file: {csv_file_path}")
             except OSError as e:
                 logging.error(f"Error removing temporary CSV file {csv_file_path}: {e}")

@bp.route('/download_filtered_csv')
def download_filtered_csv():
    """Route to generate and download FILTERED obituaries data as CSV."""
    status_filter = request.args.get('status', None)
    month_year_filter = request.args.get('month_year', None)
    logging.info(f"Filtered CSV download request. Status: '{status_filter}', Month/Year: '{month_year_filter}'")

    with current_app.app_context():
        query = DistinctObituary.query
        if status_filter in ['new', 'updated']:
            query = query.filter(DistinctObituary.tags == status_filter)
        year_filter, month_filter = None, None
        if month_year_filter:
            try:
                year_filter = int(month_year_filter.split('-')[0])
                month_filter = int(month_year_filter.split('-')[1])
                if not (1 <= month_filter <= 12 and 1990 < year_filter < 2050): raise ValueError("Date range invalid")
                query = query.filter(DistinctObituary.publication_date != None)
                query = query.filter(extract('year', DistinctObituary.publication_date) == year_filter)
                query = query.filter(extract('month', DistinctObituary.publication_date) == month_filter)
            except Exception as e:
                logging.warning(f"Invalid month_year format '{month_year_filter}'. Ignoring filter. Error: {e}")
                year_filter, month_filter = None, None

        filtered_obituaries = query.order_by(DistinctObituary.publication_date.desc()).all()
        logging.info(f"Found {len(filtered_obituaries)} obituaries matching filters.")
        if not filtered_obituaries:
             flash('No obituaries found matching the selected filters.', 'warning')
             return redirect(url_for('routes.dashboard'))

        output = io.StringIO()
        fieldnames = ['id', 'name', 'first_name', 'last_name', 'city', 'province',
                      'birth_date', 'death_date', 'publication_date',
                      'obituary_url', 'tags', 'funeral_home',
                      'latitude', 'longitude']
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for obit in filtered_obituaries:
             writer.writerow({
                 'id': obit.id, 'name': obit.name, 'first_name': obit.first_name,
                 'last_name': obit.last_name, 'city': obit.city, 'province': obit.province,
                 'birth_date': obit.birth_date, 'death_date': obit.death_date,
                 'publication_date': obit.publication_date.strftime('%Y-%m-%d') if obit.publication_date else '',
                 'obituary_url': obit.obituary_url, 'tags': obit.tags,
                 'funeral_home': obit.funeral_home, 'latitude': obit.latitude,
                 'longitude': obit.longitude,
             })

        output.seek(0)
        filename_parts = ["lancers_obituaries"]
        if status_filter: filename_parts.append(status_filter)
        if year_filter and month_filter: filename_parts.append(f"{year_filter}-{month_filter:02d}")
        filename = "_".join(filename_parts) + ".csv"
        logging.info(f"Generating response with filename: {filename}")

        return Response(
            stream_with_context(output.getvalue()),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )

@bp.route('/mail_filtered_report', methods=['POST'])
def mail_filtered_report():
    """Receives filters and recipients, generates CSV, and emails it."""
    if not request.is_json: return jsonify({"error": "Request must be JSON"}), 400
    data = request.get_json()
    recipients = data.get('recipients')
    filters = data.get('filters', {})
    if not recipients or not isinstance(recipients, list): return jsonify({"error": "Invalid recipients"}), 400
    if not isinstance(filters, dict): return jsonify({"error": "Invalid filters"}), 400
    cleaned_recipients = [str(e).strip() for e in recipients if str(e).strip()]
    if not cleaned_recipients: return jsonify({"error": "No valid recipients"}), 400

    logging.info(f"Manual mail report request for: {', '.join(cleaned_recipients)}. Filters: {filters}")
    filtered_obituaries = get_filtered_obituaries(filters) # Use helper
    if not filtered_obituaries: return jsonify({"error": "No data found matching filters."}), 404

    csv_data = generate_csv_in_memory(filtered_obituaries) # Use helper
    if not csv_data: return jsonify({"error": "Failed to generate report data."}), 500

    # Prepare Email
    subject = f"Lancer Obituary Report ({datetime.now().strftime('%Y-%m-%d')})"
    if filters.get('month_year'):
        subject = f"Lancer Monthly Report - {filters['month_year']}"
    filter_desc = ', '.join([f"{k.replace('Name',' Name')}={v}" for k, v in filters.items() if v]) or "None" # Basic formatting
    html_body = f"<p>Attached is the filtered report.</p><p><strong>Filters Applied:</strong> {filter_desc}</p><p><strong>Records Found:</strong> {len(filtered_obituaries)}</p>"
    csv_filename = f"lancer_filtered_report_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    attachments = [(csv_filename, 'text/csv', csv_data)]

    # Send email using helper
    success = send_report_email(subject, cleaned_recipients, html_body, attachments)
    if success: return jsonify({"message": "Report sent successfully!"})
    else: return jsonify({"error": "Failed to send email. Check server logs."}), 500

@bp.route('/about')
def about():
    """Route to display the About page."""
    return render_template('about.html')

def init_app(app): # Initialization function to register blueprint
    app.register_blueprint(bp)