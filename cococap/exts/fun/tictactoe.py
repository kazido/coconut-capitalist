from typing import List
from discord.ext import commands
from discord import app_commands
import discord


class TicTacToeCog(commands.Cog, name='Tic Tac Toe'):
    """Play tic tac toe with your friends."""

    def __init__(self, bot):
        self.bot = bot
        self.tree = self.bot.tree

    @app_commands.guilds(856915776345866240, 977351545966432306)
    @app_commands.command(name="tictactoe", description="Challenge someone in tictactoe")
    async def tic(self, interaction: discord.Interaction, user: discord.User):
        """Starts a tic-tac-toe game with yourself."""
        await interaction.response.send_message(f'Tic Tac Toe:  ', view=TicTacToeCog.TicTacToe(interaction.user, user))

    # Defines a custom button that contains the logic of the game.
    # The ['TicTacToe'] bit is for type hinting purposes to tell your IDE or linter
    # what the type of `self.view` is. It is not required.
    class TicTacToeButton(discord.ui.Button['TicTacToe']):
        def __init__(self, x: int, y: int):
            # A label is required, but we don't need one so a zero-width space is used
            # The row parameter tells the View which row to place the button under.
            # A View can only contain up to 5 rows -- each row can only have 5 buttons.
            # Since a Tic Tac Toe grid is 3x3 that means we have 3 rows and 3 columns.
            super().__init__(style=discord.ButtonStyle.secondary, label='\u200b', row=y)
            self.x_pos = x
            self.y_pos = y

        # This function is called whenever this particular button is pressed
        # This is part of the "meat" of the game logic
        async def callback(self, button_interaction: discord.Interaction):
            assert self.view is not None
            view: TicTacToeCog.TicTacToe = self.view
            state = view.board[self.y_pos][self.x_pos]
            if state in (view.X_value, view.O_value):
                return

            if button_interaction.user != view.current_player:
                await button_interaction.response.send_message("Wait your turn...", ephemeral=True)
                return

            content = None

            if view.current_player == view.player1:
                self.style = discord.ButtonStyle.red
                self.label = 'X'
                self.disabled = True
                view.board[self.y_pos][self.x_pos] = view.X_value
                view.current_player = view.player2
                content = f"It is now {view.player2.name}'s turn"
            elif view.current_player == view.player2:
                self.style = discord.ButtonStyle.green
                self.label = 'O'
                self.disabled = True
                view.board[self.y_pos][self.x_pos] = view.O_value
                view.current_player = view.player1
                content = f"It is now {view.player1.name}'s turn"

            winner = view.check_board_winner()
            if winner is not None:
                if winner == view.X_value:
                    content = f'**{view.player1.name} won!**'
                elif winner == view.O_value:
                    content = f'**{view.player2.name} won!**'
                else:
                    content = "It's a tie!"

                for child in view.children:
                    child.disabled = True

                view.stop()

            await button_interaction.response.edit_message(content=content, view=view)

    # This is our actual board View
    class TicTacToe(discord.ui.View):
        X_value = -1
        O_value = 1
        Tie = 2

        def __init__(self, player1, player2):
            super().__init__()
            self.player1 = player1
            self.player2 = player2
            self.current_player = self.player1
            self.board = [
                [0, 0, 0],
                [0, 0, 0],
                [0, 0, 0],
            ]

            # Our board is made up of 3 by 3 TicTacToeButtons
            # The TicTacToeButton maintains the callbacks and helps steer
            # the actual game.
            for x in range(3):
                for y in range(3):
                    self.add_item(TicTacToeCog.TicTacToeButton(x, y))

        # This method checks for the board winner -- it is used by the TicTacToeButton
        def check_board_winner(self):
            for across in self.board:
                value = sum(across)
                if value == 3:
                    return self.O_value
                elif value == -3:
                    return self.X_value

            # Check vertical
            for line in range(3):
                value = self.board[0][line] + self.board[1][line] + self.board[2][line]
                if value == 3:
                    return self.O_value
                elif value == -3:
                    return self.X_value

            # Check diagonals
            diag = self.board[0][2] + self.board[1][1] + self.board[2][0]
            if diag == 3:
                return self.O_value
            elif diag == -3:
                return self.X_value

            diag = self.board[0][0] + self.board[1][1] + self.board[2][2]
            if diag == 3:
                return self.O_value
            elif diag == -3:
                return self.X_value

            # If we're here, we need to check if a tie was made
            if all(i != 0 for row in self.board for i in row):
                return self.Tie

            return None


async def setup(bot):
    await bot.add_cog(TicTacToeCog(bot))
