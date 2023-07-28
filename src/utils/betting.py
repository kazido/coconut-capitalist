from src.utils.managers import UserManager

# Ensures that the user's bet is valid
def check_bet(user: UserManager, bet):
    balance = user.get_field("purse")
    if int(bet) < 0:
        return f"The oldest trick in the book... Nice try.", False
    elif int(bet) > balance:
        return f"No loans. You have {balance} bits.", False
    elif int(bet) == 0:
        return "What did you think this was going to do?", False
    else:
        return "Passed", True