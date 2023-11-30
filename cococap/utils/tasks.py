from datetime import datetime, timezone
from dateutil import tz

est_tz = tz.gettz('US/Michigan')

def get_time_until(time: datetime):
    """Return the difference between now and a datetime.

    Args:
        time (datetime): The datetime to compare now with.

    Returns:
        datetime: The time remaining.
    """
    c = datetime.now(tz=est_tz)
    return time - c
