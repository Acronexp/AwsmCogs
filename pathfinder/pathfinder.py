import asyncio
import logging
import operator
import os
from copy import deepcopy

import discord
import random
import re
import string
from datetime import datetime
from typing import List

from fuzzywuzzy import process
from redbot.core import Config, checks, commands
from redbot.core.data_manager import cog_data_path
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

        default_guild = {"custom": [],
                         "load_packs": ["FR-SMALLTALK", "FR-ACTIONS"]}
        default_user = {}
        self.config.register_guild(**default_guild)
        self.config.register_user(**default_user)
        self.cache = {}

        self.temp = cog_data_path(self) / "temp"
        self.temp.mkdir(exist_ok=True, parents=True)

    def get_cache(self, guild: discord.Guild):
        if guild.id not in self.cache:
            self.cache[guild.id] = {"ctx": [],
                                    "qts": []}
        return self.cache[guild.id]

    async def preload_dialogues(self, guild: discord.Guild):
        questions = []

        to_load = await self.config.guild(guild).load_packs()
        for pack in BASE_DIALOGUES:
            if pack in to_load:
                for q in BASE_DIALOGUES[pack]:
                    questions.extend(q["q"])

        custom = await self.config.guild(guild).custom()
        for q in custom:
            questions.extend(q["q"])

        cache = self.get_cache(guild)
        cache["qts"] = questions
        return cache["qts"]

    async def get_matching_dialogue(self, guild: discord.Guild, question: str):
        to_load = await self.config.guild(guild).load_packs()
        for pack in BASE_DIALOGUES:
            if pack in to_load:
                for q in BASE_DIALOGUES[pack]:
                    if question in q["q"]:
                        return q
        return None

    async def match_query(self, guild: discord.Guild, query: str):
        cache = self.get_cache(guild)
        if not cache["qts"]:
            await self.preload_dialogues(guild)
        results = process.extractBests(query, cache["qts"], score_cutoff=89, limit=3)
        if results:
            if results[0][1] == 100:
                return await self.get_matching_dialogue(guild, results[0][0])
            elif len(results) > 1 and results[0][1] == results[1][1]:
                a = await self.get_matching_dialogue(guild, results[0][0])
                b = await self.get_matching_dialogue(guild, results[1][0])
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
            return await self.get_matching_dialogue(guild, results[0][0])
        return None

    def normalize(self, texte: str):
        """Normalise le texte en retirant accents, majuscules et tirets"""
        texte = texte.lower()
        norm = [l for l in "neeecaiiuuo"]
        modif = [l for l in "ñéêèçàîïûùö"]
        fin_texte = texte
        for char in texte:
            if char in modif:
                ind = modif.index(char)
                fin_texte = fin_texte.replace(char, norm[ind])
        return fin_texte

    @commands.command(aliases=["parle"])
    @commands.max_concurrency(3, commands.BucketType.channel)
    async def talk(self, ctx, *txt):
        """Parle avec le bot"""
        if txt:
            txt = " ".join(txt)
            async with ctx.channel.typing():
                result = await self.match_query(ctx.guild, self.normalize(txt))
                await asyncio.sleep(0.5) # Ce délai c'est pour éviter le bug de l'écriture qui persiste après le message
                if result:
                    cache = self.get_cache(ctx.guild)
                    cache["ctx"] = result["ctx_out"]
                    rep = random.choice(result["a"])
                else:
                    rep = random.choice([
                        "Je n'ai pas compris la question, désolé.",
                        "Je ne sais pas répondre à ça.",
                        "Je ne sais pas de quoi vous parlez.",
                        "... Pardon ?",
                        "Je... je ne sais pas.",
                        "Je n'ai aucune réponse à vous donner."
                    ])
                bot = self.bot.user
                ans = rep.format(bot=bot)
                await ctx.send(ans)
        else:
            await ctx.send("???")

    @commands.group(name="talkset")
    @checks.admin_or_permissions(manage_messages=True)
    async def _pathfinder_talk(self, ctx):
        """Gestion des dialogues du chatbot Pathfinder"""

    def parse_dialogue(self, string):
        dlg = string.split()
        empty = {"q": None,
                 "a": None,
                 "ctx_in": [],
                 "ctx_out": []}
        if "=>" in dlg:
            struc = re.split("=>|&[io]", string)
            struc[0] = self.normalize(struc[0])
            empty["q"] = (i.strip() for i in struc[0].split("|"))
            empty["a"] = (i.strip() for i in struc[1].split("|"))
            if len(struc) == 3 and "&i" in dlg:
                empty["ctx_in"] = (i.strip() for i in struc[2].split("|"))
            elif len(struc) == 3 and "&o" in dlg:
                empty["ctx_out"] = (i.strip() for i in struc[2].split("|"))
            elif all([len(struc) == 4, "&o" in dlg,"&i" in dlg]):
                if dlg.index("&i") <  dlg.index("&o"):
                    empty["ctx_in"] = (i.strip() for i in struc[2].split("|"))
                    empty["ctx_out"] = (i.strip() for i in struc[3].split("|"))
                else:
                    empty["ctx_in"] = (i.strip() for i in struc[3].split("|"))
                    empty["ctx_out"] = (i.strip() for i in struc[2].split("|"))

            if empty["q"] and empty["a"]:
                return empty
        return {}

    @_pathfinder_talk.command(name="add")
    async def add_dialogue(self, ctx, *dlg):
        """Ajouter un dialogue

        Les questions d'exemple ne doivent pas contenir de `?`

        **__Format :__**
        `;talkset add phrase 1|phrase 2|phrase N => reponse 1|reponse 2|reponse N &i ctx1|ctx2|ctxN &o ctx1|ctx2|ctxN

        **Exemple :** `;talkset add comment rejoindre un salon vocal|comment on rejoint le vocal => Cliquez sur le nom du salon vocal dans la liste à gauche &i help &o help|audio`"""
        guild = ctx.guild
        parsed = self.parse_dialogue(" ".join(dlg))
        if parsed:
            custom = await self.config.guild(guild).custom()
            if parsed not in custom:
                custom.append(parsed)
                await self.config.guild(guild).custom.set(custom)
                await self.preload_dialogues(guild)
                await ctx.send("**Dialogue ajouté** • Le bot réagira désormais à vos questions-exemples en répondant avec les réponses pré-enregistrées.")
            else:
                await ctx.send(
                    "**Dialogue déjà présent** • Un dialogue identique se trouve déjà dans ma base de données.")
        else:
            await ctx.send(
                "**Dialogue refusé** • Le format semble invalide, consultez `;help talkset add`.")

    @_pathfinder_talk.command(name="remove")
    async def rem_dialogue(self, ctx, *dlg):
        """Efface un dialogue

        Pour accéder au dialogue à effacer, donnez une question comme si vous parliez au bot, puis confirmez la suppression du dialogue utilisé"""
        inpt = " ".join(dlg)
        result = await self.match_query(ctx.guild, self.normalize(inpt))
        if result:
            custom = await self.config.guild(ctx.guild).custom()
            if result in custom:
                em = discord.Embed(title="**Dialogue détecté** • Confirmez-vous sa suppression ?", color=discord.Color.red())
                qtxt = "\n".join(("- " + q.title() for q in result["q"]))
                em.add_field(name="Questions (normalisées)", value=qtxt)
                atxt = "\n".join(("- " + q.title() for q in result["a"]))
                em.add_field(name="Réponses", value=atxt)
                em.set_footer(text="Confirmez la suppression avec ✅, sinon ❌")
                msg = await ctx.send(embed=em)
                emojis = ["✅", "❌"]

                start_adding_reactions(msg, emojis)
                try:
                    react, user = await self.bot.wait_for("reaction_add",
                                                          check=lambda r, u: u == ctx.author and r.message.id == msg.id,
                                                          timeout=45)
                except asyncio.TimeoutError:
                    await msg.delete()
                    return
                else:
                    emoji = react.emoji

                await msg.delete()
                if emoji == "✅":
                    custom.remove(result)
                    await self.config.guild(ctx.guild).custom.set(custom)
                    await ctx.send(
                        "**Dialogue supprimé** • Le bot ne réagira plus à ces questions.")
                    await self.preload_dialogues(ctx.guild)
                else:
                    return await ctx.send(
                        "**Action annulée** • Le dialogue n'a pas été supprimé.")
            else:
                await ctx.send(
                    "**Dialogue hors d'atteinte** • J'ai bien détecté ce dialogue mais il ne figure pas dans vos dialogues personnalisés.")
        else:
            await ctx.send(
                "**Dialogue inconnu** • Je n'ai rien reconnu, réessayez.")

    @_pathfinder_talk.command(name="list")
    async def list_dialogue(self, ctx):
        """Liste les dialogues personnalisés du serveur"""
        custom = await self.config.guild(ctx.guild).custom()

        path = str(self.temp)
        filepath = path + "/custom_diag_{}.txt".format(ctx.guild.id)
        async def write(txt: str):
            file = open(filepath, "w")
            file.write(txt)
            file.close()
            return file

        if custom:
            txt = "N.R. = Non renseigné\n\n"
            for d in custom:
                for name, value in d.items():
                    lv = ", ".join(value) if value else "N.R."
                    txt += f"{name}\t{lv}\n"
                txt += "\n"

            try:
                async with ctx.channel.typing():
                    await write(txt)
                await ctx.send("Voici la liste des dialogues personnalisés de ce serveur :",
                               file=discord.File(filepath))
                os.remove(filepath)
            except:
                await ctx.send("**Erreur** • Je n'ai pas réussi à upload le fichier...")
        else:
            await ctx.send("**Liste vide** • Aucun dialogue n'est à afficher")
