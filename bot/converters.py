from discord.ext.commands import Context, Converter, BadArgument
from pydis_core.utils import unqualify
from bot import exts, instance as bot_instance


class Extension(Converter):
    """
    Fully qualify the name of an extension and ensure it exists.

    The * and ** values bypass this when used with the reload command.
    """

    async def convert(self, ctx: Context, argument: str) -> str:
        """Fully qualify the name of an extension and ensure it exists."""
        # Special values to reload all extensions
        if argument == "*" or argument == "**":
            return argument

        argument = argument.lower()

        if argument in bot_instance.all_extensions:
            return argument
        elif (qualified_arg := f"{exts.__name__}.{argument}") in bot_instance.all_extensions:
            return qualified_arg

        matches = []
        for ext in bot_instance.all_extensions:
            if argument == unqualify(ext):
                matches.append(ext)

        if len(matches) > 1:
            matches.sort()
            names = "\n".join(matches)
            raise BadArgument(
                f":x: `{argument}` is an ambiguous extension name. "
                f"Please use one of the following fully-qualified names.```\n{names}```"
            )
        elif matches:
            return matches[0]
        else:
            raise BadArgument(f":x: Could not find the extension `{argument}`.")