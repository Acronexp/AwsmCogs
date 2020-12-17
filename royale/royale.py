import asyncio
import logging
import operator
import random
import time
import roman

import discord
from fuzzywuzzy import process
from redbot.core import Config, commands, checks
from redbot.core.utils.menus import start_adding_reactions
from tabulate import tabulate
from .content import *

logger = logging.getLogger("red.AwsmCogs.royale")

class RoyaleException(Exception):
    pass

class InvalidAction(RoyaleException):
    pass


class Player:
    def __init__(self, cog, user: discord.Member):
        self.cog = cog
        self.user = user
        self.raw = self.cog.get_guild_cache(user.guild)["players"][user.id]

    def __str__(self):
        return self.user.mention

    def __int__(self):
        return self.user.id

    @property
    def xp(self):
        return self.raw["xp"]


class Royale(commands.Cog):
    """Bienvenue dans le nouveau Battle Royale"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=736144321857978388, force_registration=True)

        default_member = {"exp": 0,
                          "achievements": {},
                          "unlocked": []}
        default_guild = {"season": 1,

                         "insc_delay": 90}
        self.config.register_member(**default_member)
        self.config.register_guild(**default_guild)

        self.cache = {}

    def get_guild_cache(self, guild: discord.Guild):
        if guild.id not in self.cache:
            self.cache[guild.id] = {"register": False,
                                    "playing": False,
                                    "register_msg": None,

                                    "players": {}}
        return self.cache[guild.id]

    @commands.command()
    async def royale(self, ctx):
        """Démarrer une session de jeu Royale"""
        guild = ctx.guild
        author = ctx.author
        cache = self.get_guild_cache(guild)
        data = await self.config.guild(guild)
        color = await self.bot.get_embed_color(ctx.channel)
        if not cache["playing"]:

            def disp_players(players):
                season = roman.toRoman(data["season"])
                txt = ""
                for p in players:
                    user = guild.get_member(p)
                    txt += f"• {user.mention}\n"
                em = discord.Embed(title=f"👑 **Royale** » Inscriptions à la saison #{season}",
                                   description=txt,
                                   color=color)
                em.set_footer(text="Cliquez sur 👑 pour rejoindre la partie")
                return em


            if not cache["register"]:
                cache["register"] = True
                cache["players"][author.id] = {"health": 100,
                                               "base_atk": 20,
                                               "base_def": 5,
                                               "base_crit": 3,
                                               "equip": [],
                                               "inv": {}}

                insc = await ctx.send(embed=disp_players([author.id]))
                start_adding_reactions(insc, ["👑"])
                cache_users = []
                timeout = time.time() + data["insc_delay"]
                while time.time() < timeout and len(cache["players"]) < 16:
                    if list(cache["players"].keys()) != cache_users:
                        await insc.edit(embed=disp_players(list(cache["players"].keys())))

