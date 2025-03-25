import logging
from datetime import datetime
import pytz
from dateutil import parser
from geopy.distance import geodesic

# Set up logging
def setup_logging(log_file='app.log'):
    """Sets up the logging configuration."""
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logging.info("Logging setup complete.")

# Date Formatter
def format_date(date_str, input_format='%Y-%m-%d', output_format='%B %d, %Y'):
    """Formats a date string into a more readable format."""
    try:
        date = datetime.strptime(date_str, input_format)
        return date.strftime(output_format)
    except ValueError:
        logging.error(f"Invalid date format: {date_str}")
        return None

# Parse a date string into a datetime object
def parse_date(date_str):
    """Parses a string date into a datetime object."""
    try:
        return parser.parse(date_str)
    except (ValueError, TypeError):
        logging.error(f"Invalid date format: {date_str}")
        return None

# Convert a datetime object to a string
def datetime_to_str(date_time, format='%Y-%m-%d %H:%M:%S'):
    """Converts datetime object to string format."""
    if date_time:
        return date_time.strftime(format)
    return None

# Geographical Distance (in km) between two lat/lon points
def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculates the distance between two geographical coordinates."""
    coord1 = (lat1, lon1)
    coord2 = (lat2, lon2)
    return geodesic(coord1, coord2).km

# Get Current UTC Time
def get_current_utc_time():
    """Returns the current UTC time."""
    return datetime.now(pytz.utc)

# Convert a string date to a datetime object and return current UTC time if invalid
def parse_date_safe(date_str):
    """Safely parse a date string, returning None if invalid."""
    try:
        return parse_date(date_str)
    except:
        logging.warning(f"Failed to parse date: {date_str}, using current UTC time instead.")
        return get_current_utc_time()

# Extract year from a datetime object
def extract_year_from_date(date):
    """Extracts the year from a date."""
    if date:
        return date.year
    return None

# Extract month from a datetime object
def extract_month_from_date(date):
    """Extracts the month from a date."""
    if date:
        return date.month
    return None

# Format a datetime object to a more readable string (e.g., "March 25, 2025")
def format_readable_date(date):
    """Formats datetime to a more human-readable form."""
    if date:
        return date.strftime('%B %d, %Y')
    return None

# Check if a date is within a specified range
def is_date_in_range(date, start_date, end_date):
    """Checks if a given date is between start_date and end_date."""
    if start_date <= date <= end_date:
        return True
    return False

# Generate a unique identifier for each obituary URL
def generate_unique_obituary_id(url):
    """Generates a unique ID based on the obituary URL."""
    return hash(url)

# Remove unnecessary whitespaces from the obituary content
def clean_obituary_content(content):
    """Cleans up unnecessary whitespaces and newlines in obituary content."""
    return ' '.join(content.split())

# Get the current date in UTC
def get_current_utc_date():
    """Returns the current UTC date."""
    return datetime.now(pytz.utc).date()

# Convert a list of coordinates into a readable address using reverse geocoding
def reverse_geocode(lat, lon):
    """Reverse geocode using a geolocation API."""
    # Placeholder function, to be replaced with actual reverse geocoding
    # For example, using Geopy or an API like Google Maps
    return f"CityName, Province"  # Example output
