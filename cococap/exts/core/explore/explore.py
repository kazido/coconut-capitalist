import discord
from discord.ext import commands
import random

class Explore(commands.Cog):
    """Explore the game world! Level up your skills and discover new areas."""
    
    def __init__(self, bot):
        self.bot = bot
        
    class Map:
        grid_size: int = 10
        
        def __init__(self):
            self.map = self.generate_map()
            
        def generate_map():
            # Randomly place skill nodes across the map
            pass
        
        def generate_node(skill):
            # Skill nodes can be 4 tiers, depending on user level
            node_tier = random.randint()
            

    @commands.command(name="explore")
    async def explore(self, interaction: discord.Interaction):
        
        # Create a grid with random emojis
        grid = []
        for _ in range(grid_size):
            row = [random.choice(list(skills_emojis.values())) for _ in range(grid_size)]
            grid.append(row)

        # Convert the grid into a string for the embed
        grid_display = "\n".join([" ".join(row) for row in grid])

        # Create and send the embed
        embed = discord.Embed(
            title="Explore the World!",
            description=f"Here's what you found:\n\n{grid_display}",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

# Setup function to add the cog to the bot
async def setup(bot):
    await bot.add_cog(Explore(bot))