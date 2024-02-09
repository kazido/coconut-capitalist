import random

from datetime import datetime
from logging import getLogger

log = getLogger(__name__)


def format_time(time: int):
    if len(str(time)) == 1:
        time = "0" + str(time)
    return str(time)


def timestamp_to_digital(timestamp):
    # Calculate and format the remaining cooldown
    days = int(timestamp // 86400)
    hours = format_time(int((timestamp % 86400) // 3600))
    minutes = format_time(int((timestamp % 3600) // 60))
    seconds = format_time(int(timestamp % 60))

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


# Delay drops until half hour
def seconds_until_tasks():
    minutes = random.randint(20, 40)
    current_time = datetime.now()
    time_until = minutes - current_time.minute
    if time_until == 0:
        return 0
    elif time_until < 0:
        minutes = current_time.minute + random.randint(5, 20)
        time_until = minutes - current_time.minute
    return (time_until * 60) - current_time.second


async def check_bet(balance: int, bet: int):
    """Ensures that a user is not betting invalid amounts"""
    if int(bet) <= 0:
        return f"I sense something fishy... Quit it.", False
    elif int(bet) > balance:
        return f"Sorry, but no loans. You only have {balance:,} bits.", False
    else:
        return "Passed", True
