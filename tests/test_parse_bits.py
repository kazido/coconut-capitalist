import pytest

from cococap.errors import InvalidAmount
from utils.utils import parse_bits


@pytest.mark.parametrize(
    "raw, balance, expected",
    [
        ("500", 1000, 500),
        (500, 1000, 500),  # ints used to crash (amount[-1] on an int)
        ("1,000", 5000, 1000),
        ("2k", 5000, 2000),
        ("1.5k", 5000, 1500),
        ("1m", 2_000_000, 1_000_000),
        ("max", 1234, 1234),
        ("ALL", 1234, 1234),
        (None, 77, 77),
        ("50%", 1000, 500),
        ("100%", 1000, 1000),
    ],
)
def test_valid(raw, balance, expected):
    assert parse_bits(raw, balance) == expected


@pytest.mark.parametrize(
    "raw",
    ["500%", "101%", "0%", "-5%", "0", "-10", "", "   ", "abc", "1e9", "%", "5k5"],
)
def test_invalid(raw):
    with pytest.raises(InvalidAmount):
        parse_bits(raw, 1000)


def test_cannot_bet_more_than_balance():
    with pytest.raises(InvalidAmount):
        parse_bits("1001", 1000)


def test_percent_rounding_to_zero_is_rejected():
    with pytest.raises(InvalidAmount):
        parse_bits("1%", 10)  # rounds to 0 bits
