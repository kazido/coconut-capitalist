from datetime import datetime
from dateutil import tz

from cococap.exts.utils.error import InvalidAmount

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


def isfloat(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


def timestamp_to_digital(timestamp):
    # Calculate and format the remaining cooldown
    days = int(timestamp // 86400)
    hours = _format_time(int((timestamp % 86400) // 3600))
    minutes = _format_time(int((timestamp % 3600) // 60))
    seconds = _format_time(int(timestamp % 60))
    cooldown = f"{hours}:{minutes}:{seconds}"
    if days:
        cooldown = f"{days}:" + cooldown

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


def _parse_number(number: int | str):
    suffixes = {"k": 1_000, "m": 1_000_000}
    number = str(number).lower()
    last_char = number[-1]

    if last_char in suffixes and isfloat(number[:-1]):
        return int(float(number[:-1]) * suffixes[last_char])
    if number.isdigit():
        return int(number)
    else:
        return False


async def validate_bits(user, amount: int | str = None, field: str = "purse"):
    # Parse and validate amount
    balance = await user.get_field_fresh(field)
    if amount is None or str(amount).lower() in ["max", "all", "doitall"]:
        return balance

    if amount[-1] == "%" and amount[:-1].isdigit():
        return round(balance * (int(amount[:-1]) / 100))

    amount = _parse_number(amount)
    if not isinstance(amount, int) or amount <= 0:
        raise InvalidAmount("Please enter a valid number or 'max'.")
    if amount > balance:
        raise InvalidAmount(f"Not enough bits! Balance: {balance:,} bits")
    if not amount:
        raise InvalidAmount("You cannot enter 0 bits...")
    return amount
