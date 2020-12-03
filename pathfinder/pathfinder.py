import asyncio
import logging
import operator
from copy import deepcopy

import discord
import random
import string
from datetime import datetime
from typing import List

from fuzzywuzzy import process
from redbot.core import Config, checks, commands
from redbot.core.utils.menus import start_adding_reactions
from tabulate import tabulate

from .prebaked import *

logger = logging.getLogger("red.AwsmCogs.pathfinder")

class Pathfinder(commands.Cog):
    """Assistance en langage naturel simplifié"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=736144321857978388, force_registration=True)

        default_guild = {"custom_answers": [],
                         "load_packs": ["FR-SMALLTALK", "FR-ACTIONS"]}
        default_user = {}
        self.config.register_guild(**default_guild)
        self.config.register_user(**default_user)
        self.cache = {}

    def get_cache(self, guild: discord.Guild):
        if guild.id not in self.cache:
            self.cache[guild.id] = {"ctx": [],
                                    "qts": []}
        return self.cache[guild.id]

    async def preload_questions(self, guild: discord.Guild):
        questions = []
        to_load = await self.config.guild(guild).load_packs()
        for pack in PREBAKED_ANSWERS:
            if pack in to_load:
                for q in PREBAKED_ANSWERS[pack]:
                    questions = questions + list(q["q"])
        cache = self.get_cache(guild)
        cache["qts"] = questions
        return cache["qts"]

    async def get_matching_answer(self, guild: discord.Guild, question: str):
        to_load = await self.config.guild(guild).load_packs()
        for pack in PREBAKED_ANSWERS:
            if pack in to_load:
                for q in PREBAKED_ANSWERS[pack]:
                    if question in q["q"]:
                        return q
        return None

    async def match_query(self, guild: discord.Guild, query: str):
        cache = self.get_cache(guild)
        if not cache["qts"]:
            await self.preload_questions(guild)
        results = process.extractBests(query, cache["qts"], score_cutoff=80, limit=3)
        if results:
            if results[0][1] == 100:
                return await self.get_matching_answer(guild, results[0][0])
            elif len(results) > 1 and results[0][1] == results[1][1]:
                a = await self.get_matching_answer(guild, results[0][0])
                b = await self.get_matching_answer(guild, results[1][0])
                if cache["ctx"]:
                    score_a = score_b = 0
                    for c in a["ctx_in"]:
                        if c in cache["ctx"]:
                            score_a += 1
                    for c in b["ctx_in"]:
                        if c in cache["ctx"]:
                            score_b += 1
                    if score_a > score_b:
                        return a
                    elif score_b > score_a:
                        return b
                return random.choice([a, b])
            return await self.get_matching_answer(guild, results[0][0])
        return None

    @commands.command()
    async def talk(self, ctx, *txt):
        """Parle avec le bot"""
        if txt:
            txt = " ".join(txt)
            result = await self.match_query(ctx.guild, txt)
            cache = self.get_cache(ctx.guild)
            cache["ctx"] = result["ctx_out"]
            rep = random.choice(result["a"])

            bot = self.bot.user
            ans = rep.format(bot=bot)
            await ctx.send(ans)
        else:
            await ctx.send("???")