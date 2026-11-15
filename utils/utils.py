from datetime import datetime
from dateutil import tz

from cococap.errors import InvalidAmount

"""
An example of how to run a loop at a certain time:

Should run at 1:07 pm EST
time = datetime.time(hour=13, minute=7, tzinfo=est_tz)

@tasks.loop(time=time)
async def debugging_loop(self):
    print("Loop ran.")
"""

est_tz = tz.gettz("US/Michigan")


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


_SUFFIXES = {"k": 1_000, "m": 1_000_000}
_ALL_KEYWORDS = {"max", "all", "doitall"}


def _parse_number(number: int | str) -> int | None:
    """Parse '500', '1,000', '2k', '1.5m' into an int. Returns None if it isn't a number."""
    text = str(number).strip().lower().replace(",", "")
    if not text:
        return None
    if text[-1] in _SUFFIXES and isfloat(text[:-1]):
        return int(float(text[:-1]) * _SUFFIXES[text[-1]])
    if text.isdigit():
        return int(text)
    return None


def parse_bits(amount: int | str | None, balance: int, unit: str = "bits") -> int:
    """Turn user input into a number of bits to spend, validated against `balance`.

    Accepts a number, k/m suffixes, a percentage of the balance ('25%'), or 'max'/'all'.
    Raises InvalidAmount if the result isn't between 1 and `balance`.
    """
    if amount is None or str(amount).strip().lower() in _ALL_KEYWORDS:
        result = balance
    elif str(amount).strip().endswith("%"):
        percent = str(amount).strip()[:-1]
        if not isfloat(percent) or not 0 < float(percent) <= 100:
            raise InvalidAmount("Percentages must be between 1% and 100%.")
        result = round(balance * float(percent) / 100)
    else:
        result = _parse_number(amount)
        if result is None:
            raise InvalidAmount("Please enter a valid number or 'max'.")

    if result <= 0:
        raise InvalidAmount(f"You need to bet at least 1 {unit.rstrip('s')}.")
    if result > balance:
        raise InvalidAmount(f"Not enough {unit}! Balance: {balance:,} {unit}")
    return result


async def validate_bits(user, amount: int | str | None = None, field: str = "purse") -> int:
    """Parse `amount` and check it against the user's current (fresh) `field` balance."""
    await user.refresh()
    return parse_bits(amount, getattr(user, field))
