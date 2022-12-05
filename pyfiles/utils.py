from pathlib import Path
from datetime import datetime
from random import randint


def get_project_root() -> Path:
    return Path(__file__).parent.parent


def seconds_until_tasks():  # Delay drops until half hour
    minutes = randint(20, 40)
    current_time = datetime.now()
    time_until = minutes - current_time.minute
    if time_until == 0:
        return 0
    elif time_until < 0:
        minutes = current_time.minute + randint(5, 20)
        time_until = minutes - current_time.minute
    return (time_until * 60) - current_time.second
