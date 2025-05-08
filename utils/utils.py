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


def _format_time(time: int):
    if len(str(time)) == 1:
        time = "0" + str(time)
    return str(time)


def timestamp_to_digital(timestamp):
    # Calculate and format the remaining cooldown
    days = int(timestamp // 86400)
    hours = _format_time(int((timestamp % 86400) // 3600))
    minutes = _format_time(int((timestamp % 3600) // 60))
    seconds = _format_time(int(timestamp % 60))

    cooldown = f"{days}d" if days != 0 else ""
    cooldown += f"{hours}:{minutes}:{seconds}"

    return cooldown


def timestamp_to_english(timestamp):

    # Calculate and format the remaining cooldown
    days = int(timestamp // 86400)
    hours = int((timestamp % 86400) // 3600)
    minutes = int((timestamp % 3600) // 60)
    seconds = int(timestamp % 60)

    cooldown = f"{days:,} days " if days != 0 else ""
    cooldown += f"{hours} hours " if hours else ""
    cooldown += f"{minutes} minutes " if minutes else ""
    cooldown += f"{seconds} seconds" if seconds else ""

    return cooldown
