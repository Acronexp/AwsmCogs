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
        self.raw = self.cog.fetch_channel_game(user.guild)["players"][user.id]

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
                          "medals": {},
                          "unlocked": [],
                          "stats": [0, 0]}
        default_guild = {"season": 1,

                         "register_delay": 90,
                         "insc_fees": 100}
        self.config.register_member(**default_member)
        self.config.register_guild(**default_guild)

        self.cache = {}

    def new_game(self, channel: discord.TextChannel):
        """Créer une nouvelle partie sur le channel donné et renvoie ces données"""
        if channel.id not in self.cache:
            self.cache[channel.id] = {"status": 0, # 0 = Nouveau, 1 = Inscriptions, 2 = Partie en cours
                                      "register_msg": None,

                                      "players": {}}
        return self.cache[channel.id]

    def fetch_channel_game(self, channel: discord.TextChannel):
        """Retrouve les données du la partie liée au salon donné"""
        if channel.id in self.cache:
            return self.cache[channel.id]
        return None

    def add_player(self, channel: discord.TextChannel, user: discord.Member):
        game = self.fetch_channel_game(channel)
        if game:
            game["players"][user] = {"pv": 100,
                                    "base_atk": 20,
                                    "base_def": 5,
                                    "base_crit": 3,
                                    "equip": [],
                                    "inv": {}}
            return game
        return None

    @commands.command()
    async def royale(self, ctx):
        """Démarrer une session de jeu Royale

        Il peut y avoir qu'une partie par salon écrit"""
        guild, channel, author = ctx.guild, ctx.channel, ctx.author
        embed_color = await self.bot.get_embed_color(channel)
        params = await self.config.guild(guild).all()
        cash = self.bot.get_cog("Cash")

        if not self.fetch_channel_game(channel):
            game = self.new_game(channel)

            def disp_players(players):
                season = roman.toRoman(params["season"])
                txt = ""
                for p in players:
                    user = guild.get_member(p)
                    txt += f"• {user.mention}\n"
                em = discord.Embed(title=f"👑 **Royale** » Inscriptions à la saison **{season}**",
                                   description=txt,
                                   color=embed_color)
                fees = params["insc_fees"]
                em.set_footer(text="👑 • Rejoindre la partie ({} {})".format(fees, await cash.get_currency(guild)))
                return em

            if game["status"] == 0:
                game["status"] = 1
                self.add_player(channel, author)

                insc = await ctx.send(embed=disp_players([author.id]))
                game["register_msg"] = insc
                start_adding_reactions(insc, ["👑"])
                cache_users = []
                timeout = time.time() + params["register_delay"]
                while time.time() < timeout and len(game["players"]) < 16 and game["status"] == 1:
                    if list(game["players"].keys()) != cache_users:
                        await insc.edit(embed=disp_players(list(game["players"].keys())))

                if len(game["players"]) >= 4:
                    game["status"] = 2


    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        message = reaction.message
        if message.guild:
            if reaction.emoji == "👑":
                channel = message.channel
                game = self.fetch_channel_game(channel)
                if game:
                    if game["status"] == 1 and game["register_msg"] == message:
                        if user.id not in game["players"]:
                            cash = self.bot.get_cog("Cash")
                            params = await self.config.guild(message.guild).all()
                            if await cash.enough_balance(user, params["insc_fees"]):
                                self.add_player(channel, user)
                            else:
                                try:
                                    await message.remove_reaction("👑", user)
                                except:
                                    pass
                                curr = await cash.get_currency(channel.guild)
                                await channel.send(f"{user.mention} **Fonds insuffisants** • "
                                                   f"L'inscription coûte {params['insc_fees']} {curr}", delete_after=20)
