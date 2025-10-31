import datetime
import pytz

def format_datetime_for_response(dt, timezone_str="UTC"):
    """Format datetime for JSON response (ISO format with timezone)"""
    try:
        tz = pytz.timezone(timezone_str)
    except pytz.exceptions.UnknownTimeZoneError:
        tz = pytz.UTC
    
    if isinstance(dt, datetime.datetime):
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)
        dt_tz = dt.astimezone(tz)
        return dt_tz.isoformat()
    return dt

def convert_user_date_to_utc_range(date_str, user_timezone_str="UTC"):
    """
    Convert user's date (DD-MM-YYYY) to UTC date range (start and end of that day in UTC)
    Returns: (start_utc, end_utc) as naive UTC datetimes
    """
    try:
        user_tz = pytz.timezone(user_timezone_str)
    except pytz.exceptions.UnknownTimeZoneError:
        user_tz = pytz.UTC
    
    # Parse the date string (DD-MM-YYYY)
    day, month, year = map(int, date_str.split("-"))
    
    # Create start of day in user's timezone
    start_user_tz = user_tz.localize(datetime.datetime(year, month, day, 0, 0, 0))
    # Create end of day in user's timezone (23:59:59.999999)
    end_user_tz = user_tz.localize(datetime.datetime(year, month, day, 23, 59, 59, 999999))
    
    # Convert to UTC
    start_utc = start_user_tz.astimezone(pytz.UTC).replace(tzinfo=None)
    end_utc = end_user_tz.astimezone(pytz.UTC).replace(tzinfo=None)
    
    return start_utc, end_utc

def convert_user_month_to_utc_range(year, month, user_timezone_str="UTC"):
    """
    Convert user's month to UTC date range (start and end of that month in UTC)
    Returns: (start_utc, end_utc) as naive UTC datetimes
    """
    try:
        user_tz = pytz.timezone(user_timezone_str)
    except pytz.exceptions.UnknownTimeZoneError:
        user_tz = pytz.UTC
    
    # Get start of month (1st day, 00:00:00) in user's timezone
    start_user_tz = user_tz.localize(datetime.datetime(year, month, 1, 0, 0, 0))
    
    # Get end of month (last day, 23:59:59.999999) in user's timezone
    if month == 12:
        last_day = datetime.datetime(year + 1, 1, 1) - datetime.timedelta(days=1)
    else:
        last_day = datetime.datetime(year, month + 1, 1) - datetime.timedelta(days=1)
    
    end_user_tz = user_tz.localize(datetime.datetime(year, month, last_day.day, 23, 59, 59, 999999))
    
    # Convert to UTC
    start_utc = start_user_tz.astimezone(pytz.UTC).replace(tzinfo=None)
    end_utc = end_user_tz.astimezone(pytz.UTC).replace(tzinfo=None)
    
    return start_utc, end_utc

def convert_user_date_to_utc_date_string(date_str, user_timezone_str="UTC"):
    """
    Convert user's date (DD-MM-YYYY) to UTC date string (DD-MM-YYYY)
    Takes the start of the day in user's timezone and converts to UTC date
    Returns: UTC date string in DD-MM-YYYY format
    """
    try:
        user_tz = pytz.timezone(user_timezone_str)
    except pytz.exceptions.UnknownTimeZoneError:
        user_tz = pytz.UTC
    
    # Parse the date string (DD-MM-YYYY)
    day, month, year = map(int, date_str.split("-"))
    
    # Create start of day (00:00:00) in user's timezone
    start_user_tz = user_tz.localize(datetime.datetime(year, month, day, 0, 0, 0))
    
    # Convert to UTC
    start_utc = start_user_tz.astimezone(pytz.UTC)
    
    # Format as DD-MM-YYYY
    return start_utc.strftime("%d-%m-%Y")
