import discord
from discord.ext import commands

mushroom_options = [
    discord.SelectOption(label="Luigi Circuit", value="luigicircuit"),
    discord.SelectOption(label="Moo Moo Meadows", value="moomoomeadows"),
    discord.SelectOption(label="Mushroom Gorge", value="mushroomgorge"),
    discord.SelectOption(label="Toad's Factory", value="toadsfactory"),
]
flower_options = [
    discord.SelectOption(label="Mario Circuit", value="mariocircuit"),
    discord.SelectOption(label="Coconut Mall", value="coconutmall"),
    discord.SelectOption(label="DK Summit", value="dksummit"),
    discord.SelectOption(label="Wario's Gold Mine", value="wariosgoldmine"),
]
star_options = [
    discord.SelectOption(label="Daisy Circuit", value="daisycircuit"),
    discord.SelectOption(label="Koopa Cape", value="koopacape"),
    discord.SelectOption(label="Maple Treeway", value="mapletreeway"),
    discord.SelectOption(label="Grumble Volcano", value="grumblevolcano"),
]
special_options = [
    discord.SelectOption(label="Dry Dry Ruins", value="drydryruins"),
    discord.SelectOption(label="Moonview Highway", value="moonviewhighway"),
    discord.SelectOption(label="Bowser's Castle", value="bowserscastle"),
    discord.SelectOption(label="Rainbow Road", value="rainbowroad"),
]
shell_options = [
    discord.SelectOption(label="GCN Peach Beach", value="gcnpeachbeach"),
    discord.SelectOption(label="DS Yoshi Falls", value="dsyoshifalls"),
    discord.SelectOption(label="SNES Ghost Valley 2", value="snesghostvalley2"),
    discord.SelectOption(label="N64 Mario Raceway", value="n64marioraceway"),
]
banana_options = [
    discord.SelectOption(label="N64 Sherbet Land", value="n64sherbetland"),
    discord.SelectOption(label="GBA Shy Guy Beach", value="gbashyguybeach"),
    discord.SelectOption(label="DS Delfino Square", value="dsdelfinosquare"),
    discord.SelectOption(label="GCN Waluigi Stadium", value="gcnwaluigistadium"),
]
leaf_options = [
    discord.SelectOption(label="DS Desert Hills", value="dsdeserthills"),
    discord.SelectOption(label="GBA Bowser Castle 3", value="gbabowsercastle3"),
    discord.SelectOption(label="N64 DK's Jungle Parkway", value="n64dksjungleparkway"),
    discord.SelectOption(label="GCN Mario Circuit", value="gcnmariocircuit"),
]
lightning_options = [
    discord.SelectOption(label="SNES Mario Circuit 3", value="snesmariocircuit3"),
    discord.SelectOption(label="DS Peach Gardens", value="dspeachgardens"),
    discord.SelectOption(label="GCN DK Mountain", value="gcndkmountain"),
    discord.SelectOption(label="N64 Bowser's Castle", value="n64bowserscastle"),
]

options_dict = {"mushroom": mushroom_options,
                "flower": flower_options,
                "star": star_options,
                "special": special_options,
                "shell": shell_options,
                "banana": banana_options,
                "leaf": leaf_options,
                "lightning": lightning_options}


class MarioKart(commands.Cog, name='MarioKart'):
    """Mario Kart!"""

    def __init__(self, bot):
        self.bot = bot

    class VehicleModal(discord.ui.Modal, title="Vehicle Used"):
        vehicle = discord.ui.TextInput(label="Vehicle", placeholder="Bullet Bike, Dragster, etc.", required=True)

        async def on_submit(self, interaction: discord.Interaction):
            vehicle = self.vehicle

    class TimeInputModal(discord.ui.Modal, title="Course Time"):

        time = discord.ui.TextInput(label="Time", placeholder="00:00.000", required=True, min_length=9, max_length=9)

        async def on_submit(self, interaction: discord.Interaction):
            time = self.time

    class CharacterModal(discord.ui.Modal, title="Character Used"):
        character = discord.ui.TextInput(label="Character", placeholder="Waluigi", required=True)

        async def on_submit(self, interaction: discord.Interaction):
            character = self.character

    class CupView(discord.ui.View):
        def __init__(self):
            super().__init__()
            view = MarioKart.CupSelector()

            self.add_item(view)

    class CourseView(discord.ui.View):
        def __init__(self, options):
            super().__init__()
            view = MarioKart.CourseSelector(options)

            self.add_item(view)

    class VehicleView(discord.ui.View):
        def __init__(self):
            super().__init__()

            self.add_item(MarioKart.VehicleSelector())

    class CharacterView(discord.ui.View):
        def __init__(self):
            super().__init__()

            self.add_item(MarioKart.CharacterSelector())

    class CourseSelector(discord.ui.Select):
        def __init__(self, course_options):
            self.course_options = course_options
            self.course = None

            super().__init__(placeholder="Which course is the time for?", min_values=1, max_values=1, options=self.course_options)

        async def callback(self, interaction: discord.Interaction):
            self.course = self.values[0]
            character_view = MarioKart.CharacterView()
            await interaction.response.edit_message(content="Which character did you use?", view=character_view)

    class CupSelector(discord.ui.Select):
        def __init__(self):
            self.cup = None
            options = [
                discord.SelectOption(label="Mushroom Cup", value="mushroom"),
                discord.SelectOption(label="Flower Cup", value="flower"),
                discord.SelectOption(label="Star Cup", value="star"),
                discord.SelectOption(label="Special Cup", value="special"),
                discord.SelectOption(label="Shell Cup", value="shell"),
                discord.SelectOption(label="Banana Cup", value="banana"),
                discord.SelectOption(label="Leaf Cup", value="leaf"),
                discord.SelectOption(label="Lightning Cup", value="lightning"),
            ]

            super().__init__(placeholder='Choose the cup', min_values=1, max_values=1, options=options)

        async def callback(self, interaction: discord.Interaction):
            self.cup = self.values[0]
            view = MarioKart.CourseView(options_dict[self.values[0]])
            await interaction.response.edit_message(content="Choose the course:", view=view)

    class VehicleSelector(discord.ui.Select):
        def __init__(self):
            self.vehicle = None
            options = [
                discord.SelectOption(label="Flame Runner", value="flamerunner"),
                discord.SelectOption(label="Mach Bike", value="machbike"),
                discord.SelectOption(label="Spear", value="spear"),
                discord.SelectOption(label="Other", value="other")
            ]
            super().__init__(placeholder="Choose the vehicle you used", min_values=1, max_values=1, options=options)

        async def callback(self, interaction: discord.Interaction):
            if self.values[0] == "other":
                await interaction.response.send_modal(MarioKart.VehicleModal())
            else:
                self.vehicle = self.values[0]
            await interaction.response.send_modal(MarioKart.TimeInputModal())

    class CharacterSelector(discord.ui.Select):
        def __init__(self):
            self.character = None
            options = [
                discord.SelectOption(label="Funky Kong", value="funkykong"),
                discord.SelectOption(label="Daisy", value="daisy"),
                discord.SelectOption(label="Other", value="other")
            ]
            super().__init__(placeholder="Choose the character you used", min_values=1, max_values=1, options=options)

        async def callback(self, interaction: discord.Interaction):
            if self.values[0] == "other":
                await interaction.response.send_modal(MarioKart.CharacterModal())
            else:
                self.character = self.values[0]
            await interaction.response.edit_message(content="What vehicle did you use?", view=MarioKart.VehicleView())

    mk_commands = discord.app_commands.Group(name="mk", description="Mario Kart related commands..",
                                             guild_ids=[856915776345866240])

    @mk_commands.command(name="upload", description="Upload your fastest time for each course.")
    async def upload(self, interaction: discord.Interaction):
        cup_view = MarioKart.CupView()
        await interaction.response.send_message("Which **cup** is your course in?", view=cup_view)


async def setup(bot):
    await bot.add_cog(MarioKart(bot))
