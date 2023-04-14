import threading

# global dictionary to store game state
game_states = {}

# lock to ensure thread safety when accessing game_state
lock = threading.Lock()

# function to check if a user is in game
def is_user_in_game(user_id):
    with lock:
        return user_id in game_states

# function to start a new game for a user
def start_game_for_user(user_id):
    with lock:
        game_states[user_id] = {}

# function to end a game for a user
def end_game_for_user(user_id):
    with lock:
        game_states.pop(user_id, None)  # remove game state information
