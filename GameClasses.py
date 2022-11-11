# General python imports
# Discord imports
# Database imports
from ClassLibrary2 import RequestUser
# File import
# Other imports


class Game:
    game_type = None
    def __init__(self, game_user_id, bet) -> None:
        self.game_user_id = game_user_id
        self.reward = bet
            
            
class MultiplayerGame(Game):
    min_players = None
    max_players = None
    def __init__(self, game_user_id, bet=0) -> None:
        super().__init__(game_user_id, bet)
        
        # Add a list of all users, starting with the one who made the game
        self.game_users = [game_user_id]
        while len(self.game_users) < self.max_players:
            self._full = False
        else:
            self._full = True
        self.winner = None
        # Create a row in the 'games' database for the started game
        self.game = dbGames.create(game_type=self.game_type, reward=bet, game_creator_id=game_user_id)
        
    
    def join_game(self, user_id):
        # Check the user's balance to see if they have enough to play
        joining_user = RequestUser(user_id)
        if joining_user.instance.money < self.bet:
            return "You don't have enough bits to join this game.\n" \
                    f"Cost to join: {self.bet}"
        # Don't let the user join the game if the game is full
        if len(self.game_users) == self.max_players:
            return "This game is full!"
        # Add the user to the users list and add their bet to the reward
        self.game_users.append(user_id)
        self.reward += self.bet
        
    def start_game(self):
        if self.min_players:
            if len(self.game_users) < self.min_players:
                return "This game does not meet the minimum players requirement.\n" \
                        f"Needs {self.min_players - len(self.game_users)} more player(s)."
            else:
                return "Game started."
            
    def end_game(self, winner_id):
        self.winner = dbUser[winner_id]
        self.winner.money += self.reward
        self.winner.save()
        for user_id in self.game_users:
            user = dbUser[user_id]
            if user != self.winner:
                user.money -= self.bet
                user.save()
        print("Finished handling bets and rewards.")
    
    def __del__(self):
        if self.game:
            self.game.delete_instance()
            print("Game removed from database.")
            
            
class TestMultiplayerGame(MultiplayerGame):
    min_players = 2
    max_players = 2
    def __init__(self, game_user_id, bet=0) -> None:
        super().__init__(game_user_id, bet)
        