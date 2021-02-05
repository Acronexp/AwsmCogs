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
    async def multiplemembers(self, ctx):
        """Teste la détection de plusieurs membres dans une commande"""
        members = ctx.message.mentions
        if members:
            txt = ""
            for m in members:
                txt += f"{m}\n"
            return await ctx.send(txt)
        await ctx.send("Vide")