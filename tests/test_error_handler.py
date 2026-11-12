from cococap.errors import CustomError, InvalidAmount
from cococap.exts.utils.error import GENERIC_MESSAGE, build_error_embed
from cococap.user import InsufficientFunds


def test_internal_errors_do_not_leak_to_users():
    leaky = RuntimeError("mongodb+srv://user:hunter2@cluster/db failed")
    assert build_error_embed(leaky).description == GENERIC_MESSAGE


def test_custom_errors_show_message_title_and_footer():
    embed = build_error_embed(CustomError("nope", title="Hold on", footer="try later"))
    assert (embed.description, embed.title, embed.footer.text) == ("nope", "Hold on", "try later")
    assert build_error_embed(InvalidAmount("bad amount")).description == "bad amount"


def test_exceptions_without_args_do_not_crash_the_handler():
    # Previously `e.args[0]` raised IndexError for argument-less exceptions.
    assert build_error_embed(CustomError("")).description == GENERIC_MESSAGE
    assert build_error_embed(KeyError()).description == GENERIC_MESSAGE


def test_insufficient_funds_is_friendly():
    assert "enough bits" in build_error_embed(InsufficientFunds()).description
