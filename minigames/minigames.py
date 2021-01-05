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
        """Jouer à la machine à sous

        Mise minimale de 5 crédits et maximale de 100"""
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
                   ("⚡", "x3", "Mise x50"),
                   ("Fruits", "x3", "Remboursement")]
            em = discord.Embed(title="Combinaisons possibles",
                               description=box(tabulate(tbl, headers=("Emoji", "Nb.", "Gain"))),
                               color=await ctx.embed_color())
            em.set_footer(text=f"🍒 = Même fruit · La mise doit être comprise entre 5 et 100 {curr}")
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

                    aff = "{a[0]}|{b[0]}|{c[0]}\n" \
                          "{a[1]}|{b[1]}|{c[1]} <= \n" \
                          "{a[2]}|{b[2]}|{c[2]}".format(a=cols[0], b=cols[1], c=cols[2])
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
                    elif fruitcount() == 3:
                        delta = mise * 3
                        txt = "3x fruit · Vous gagnez {}"
                    elif fruitcount() == 2:
                        delta = mise + 50
                        txt = "2x fruit · Vous gagnez {}"
                    else:
                        txt = "Rien · Vous perdez votre mise"

                    await asyncio.sleep(2)

                    ope = delta - mise
                    if ope > 0:
                        await cash.deposit_credits(author, ope)
                        await cash.add_log(author, "Machine à sous", ope)
                    elif ope < 0:
                        await cash.remove_credits(author, mise)
                        await cash.add_log(author, "Machine à sous", ope)

                em = discord.Embed(description=f"**Mise :** {mise} {curr}\n" + box(aff), color=author.color)
                em.set_author(name="🎰 " + author, icon_url=author.avatar_url)
                em.set_footer(text=txt.format(f"{delta} {curr}"))
                await ctx.send(embed=em)
            else:
                await ctx.send("**Fonds insuffisants** • Vous n'avez pas cette somme sur votre compte")
        else:
            await ctx.send(f"**Mise invalide** • Elle doit être comprise entre 5 et 100 {curr}")

    @commands.command()
    async def guess(self, ctx, mise: int):
        """Avez vous plus ou moins que la somme des dés tirés ?

        Vous devez deviner si vous aurez plus ou moins en additionnant vos deux lancés.
        Si les scores sont identiques avec le bot, vous êtes remboursé.

        Mise minimale de 5 crédits et maximale de 100"""
        author = ctx.author
        cash = self.bot.get_cog("Cash")
        curr = await cash.get_currency(ctx.guild)

        if 5 <= mise <= 100:
            if await cash.enough_balance(author, mise):
                user_dices = [random.randint(1, 6), random.randint(1, 6)]
                bot_dices = [random.randint(1, 6), random.randint(1, 6)]
                emdict = {"color": author.color,
                          "author": {"name": "🎲 " + author, "icon_url": author.avatar_url},
                          "fields": [
                              {"name": "Votre lancé", "value": box(f"🎲 {min(user_dices)} ")},
                              {"name": "Mon lancé", "value": box(f"🎲 {max(bot_dices)} ")}],
                          "footer": {"text": "Allez-vous avoir plus ou moins que moi avec le prochain lancé ?"}}
                msg = await ctx.send(embed=discord.Embed().from_dict(emdict))
                emojis = ["➕", "➖"]

                start_adding_reactions(msg, emojis)
                try:
                    react, user = await self.bot.wait_for("reaction_add",
                                                          check=lambda r, u: u == ctx.author and r.message.id == msg.id,
                                                          timeout=30)
                except asyncio.TimeoutError:
                    emoji = random.choice(emojis)
                else:
                    emoji = react.emoji

                emdict["fields"][0]["value"] = box(f"🎲 {min(user_dices)}, {max(user_dices)} ")
                emdict["fields"][1]["value"] = box(f"🎲 {max(bot_dices)}, {min(bot_dices)} ")

                if sum(user_dices) == sum(bot_dices):
                    emdict["footer"]["text"] = f"Egalité ! Vous ne perdez pas votre mise"
                    await msg.edit(embed=discord.Embed().from_dict(emdict))

                await msg.delete()
                if emoji == "➕":
                    if sum(user_dices) > sum(bot_dices):
                        emdict["footer"]["text"] = f"Bravo ! Vous gagnez {mise} {curr}"
                        await cash.deposit_credits(author, mise)
                        await cash.add_log(author, "Gain aux dés", mise)
                        await msg.edit(embed=discord.Embed().from_dict(emdict))
                    else:
                        emdict["footer"]["text"] = f"Loupé ! Vous perdez votre mise"
                        await cash.remove_credits(author, mise)
                        await cash.add_log(author, "Perte aux dés", -mise)
                        await msg.edit(embed=discord.Embed().from_dict(emdict))
                else:
                    if sum(user_dices) < sum(bot_dices):
                        emdict["footer"]["text"] = f"Bravo ! Vous gagnez {mise} {curr}"
                        await cash.deposit_credits(author, mise)
                        await cash.add_log(author, "Gain aux dés", mise)
                        await msg.edit(embed=discord.Embed().from_dict(emdict))
                    else:
                        emdict["footer"]["text"] = f"Loupé ! Vous perdez votre mise"
                        await cash.remove_credits(author, mise)
                        await cash.add_log(author, "Perte aux dés", -mise)
                        await msg.edit(embed=discord.Embed().from_dict(emdict))
            else:
                await ctx.send("**Fonds insuffisants** • Vous n'avez pas cette somme sur votre compte")
        else:
            await ctx.send(f"**Mise invalide** • Elle doit être comprise entre 5 et 100 {curr}")
