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
from redbot.core.utils.chat_formatting import box
from redbot.core.utils.menus import start_adding_reactions
from tabulate import tabulate

logger = logging.getLogger("red.AwsmCogs.minigames")

class MiniGames(commands.Cog):
    """Mini-jeux exploitant l'économie du module Cash"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=736144321857978388, force_registration=True)

        default_guild = {}
        self.config.register_guild(**default_guild)

    @commands.command()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def slot(self, ctx, mise: int = None):
        """Jouer à la machine à sous"""
        author = ctx.author
        cash = self.bot.get_cog("Cash")
        curr = await cash.get_currency(ctx.guild)

        if not mise:
            tbl = [("🍒", "x2", "Mise + 50"),
                   ("🍒", "x3", "Mise x3"),
                   ("🍀", "x2", "Mise + 200"),
                   ("🍀", "x3", "Mise x5"),
                   ("💎", "x2", "Mise x10"),
                   ("💎", "x3", "Mise x30"),
                   ("⚡", "<3", "Mise perdue"),
                   ("⚡", "x3", "Mise x50")]
            em = discord.Embed(title="Combinaisons possibles",
                               description=box(tabulate(tbl, headers=("Emoji", "Nb.", "Gain"))),
                               color=await ctx.embed_color())
            em.set_footer(text=f"🍒 = Fruit · La mise doit être comprise entre 5 et 100 {curr}")
            return await ctx.send(embed=em)

        if 5 <= mise <= 100:
            if await cash.enough_balance(author, mise):
                async with ctx.channel.typing():
                    delta = 0

                    col = ["🍎", "🍊", "🍋", "🍒", "🍉", "⚡", "💎", "🍀"]
                    fruits = ["🍎", "🍊", "🍋", "🍒", "🍉"]
                    col = col[-3:] + col + col[:3]
                    cols = []
                    mid = []
                    for i in range(3):
                        n = random.randint(3, 10)
                        cols.append((col[n-1], col[n], col[n+1]))
                        mid.append(col[n])

                    aff = "{a[0]} | {b[0]} | {c[0]}\n" \
                          "{a[1]} | {b[1]} | {c[1]} <= \n" \
                          "{a[2]} | {b[2]} | {c[2]}".format(a=cols[0], b=cols[1], c=cols[2])
                    count = lambda e: mid.count(e)

                    def fruitcount():
                        for f in fruits:
                            if count(f) >= 2:
                                return count(f)
                        return 0

                    if count("⚡") == 3:
                        delta = mise * 50
                        txt = "3x ⚡ · Vous gagnez {}"
                    elif count("⚡") in (1, 2):
                        txt = "Zap ⚡ · Vous perdez votre mise"
                    elif count("💎") == 3:
                        delta = mise * 30
                        txt = "3x 💎 · Vous gagnez {}"
                    elif count("💎") == 2:
                        delta = mise * 10
                        txt = "2x 💎 · Vous gagnez {}"
                    elif count("🍀") == 3:
                        delta = mise * 5
                        txt = "3x 🍀 · Vous gagnez {}"
                    elif count("🍀") == 2:
                        delta = mise + 200
                        txt = "2x 🍀 · Vous gagnez {}"
                    elif fruitcount == 3:
                        delta = mise * 3
                        txt = "3x fruit · Vous gagnez {}"
                    elif fruitcount == 2:
                        delta = mise + 50
                        txt = "2x fruit · Vous gagnez {}"
                    else:
                        txt = "Rien · Vous perdez votre mise"

                    await asyncio.sleep(2)

                    ope = delta - mise
                    if ope > 0:
                        await cash.deposit_credits(author, ope)
                    elif ope < 0:
                        await cash.remove_credits(author, mise)
                    await cash.add_log(author, "Machine à sous", ope)

                em = discord.Embed(description=f"**Mise :** {mise} {curr}\n\n" + box(aff), color=author.color)
                em.set_author(name=author, icon_url=author.avatar_url)
                em.set_footer(text=txt.format(f"{delta} {curr}"))
                await ctx.send(embed=em)
            else:
                await ctx.send("**Fonds insuffisants** • Vous n'avez pas cette somme sur votre compte")
        else:
            await ctx.send(f"**Mise invalide** • Elle doit être comprise entre 5 et 100 {curr}")

    # TODO Jeu de dés
