from pydantic import BaseModel


class Stats(BaseModel):
    drops_claimed: int = 0
    tokens_earned: int = 0
    luckbucks_earned: int = 0
    times_begged: int = 0
    withdraws: int = 0
    deposits: int = 0
    highlow_games: int = 0
    longest_hl_streak: int = 0
    hl_win_streak: int = 0
    hl_wins: int = 0
    longest_hl_loss_streak: int = 0
    hl_loss_streak: int = 0
    biggest_hl_win: int = 0
    biggest_hl_loss: int = 0
    blackjack_games: int = 0
    blackjacks: int = 0
    blackjack_hits: int = 0
    blackjack_stands: int = 0
    blackjack_folds: int = 0
    blackjack_wins: int = 0
    sequence_games: int = 0
    longest_sq_streak: int = 0
    unscramble_games: int = 0
    unscramble_streak: int = 0
    longest_unscramble_streak: int = 0
    flashcard_games: int = 0
    flashcard_streak: int = 0
    longest_flashcard_streak: int = 0
    trivia_wins: int = 0
    trivia_games: int = 0
