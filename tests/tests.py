import discord
from typing import List, Tuple, NewType
import logging
from redbot.core import Config, commands, checks, errors

logger = logging.getLogger("red.AwsmCogs.tests")

Members = NewType('Members', Tuple[discord.Member])

class Tests(commands.Cog):
    """Différents tests"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    @commands.command()
    async def multiplemembers(self, ctx, *members: Members):
        """Teste la détection de plusieurs membres dans une commande"""
        if members:
            txt = ""
            for p in members:
                txt += f"{p.name}\n"
            return await ctx.send(txt)
        await ctx.send("**Rien à afficher**")