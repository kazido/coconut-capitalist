from datetime import datetime, timezone
from dateutil import tz

"""
An example of how to run a loop at a certain time:

Should run at 1:07 pm EST
time = datetime.time(hour=13, minute=7, tzinfo=est_tz)

@tasks.loop(time=time)
async def debugging_loop(self):
    print("Loop ran.")
"""

est_tz = tz.gettz("US/Michigan")


def get_time_until(time: datetime):
    """Return the difference between now and a datetime.

    Args:
        time (datetime): The datetime to compare now with.

    Returns:
        datetime: The time remaining.
    """
    c = datetime.now(tz=est_tz)
    return time - c
