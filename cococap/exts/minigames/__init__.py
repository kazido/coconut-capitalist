from .spectrum import SpectrumCog


async def setup(bot):
    minigames = (SpectrumCog,)
    for cog in minigames:
        await bot.add_cog(cog(bot))
