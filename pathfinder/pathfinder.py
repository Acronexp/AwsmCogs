import asyncio
import logging
import os
from copy import copy

import discord
import random
import re

from fuzzywuzzy import process, fuzz
from redbot.core import Config, checks, commands
from redbot.core.data_manager import cog_data_path
from redbot.core.utils.menus import start_adding_reactions

from .prebaked import *

logger = logging.getLogger("red.AwsmCogs.pathfinder")

class Pathfinder(commands.Cog):
    """Assistance en langage naturel simplifié"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=736144321857978388, force_registration=True)

        default_guild = {"custom": [],
                         "load_packs": ["FR-SMALLTALK", "FR-ACTIONS"],
                         "on_mention": False}
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
        custom = await self.config.guild(guild).custom()
        for pack in BASE_DIALOGUES:
            if pack in to_load:
                for q in BASE_DIALOGUES[pack]:
                    if question in q["q"]:
                        return q
        for q in custom:
           if question in q["q"]:
               return q
        return None

    async def match_query(self, guild: discord.Guild, query: str, cutoff: int = 87):
        cache = self.get_cache(guild)
        if not cache["qts"]:
            await self.preload_dialogues(guild)

        def match_scorer(search, choice):
            if "?" in search:
                choice += " ?"
            result = fuzz.token_sort_ratio(search, choice, force_ascii=False)
            if len(search.split()) == len(choice.split()):
                result *= 1.1
            return result

        results = process.extractBests(query, cache["qts"], score_cutoff=cutoff, limit=3, scorer=match_scorer)
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

    async def get_prefix(self, message: discord.Message) -> str:
        content = message.content
        prefix_list = await self.bot.command_prefix(self.bot, message)
        prefixes = sorted(prefix_list, key=lambda pfx: len(pfx), reverse=True)
        for p in prefixes:
            if content.startswith(p):
                return p
        return "n."

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

    async def answer_diag(self, msg: discord.Message, txt = None):
        channel = msg.channel
        if txt:
            txt = " ".join(txt)
            async with channel.typing():
                result = await self.match_query(channel.guild, self.normalize(txt))
                await asyncio.sleep(0.1)
                if result:
                    cache = self.get_cache(channel.guild)
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
                await channel.send(ans)

                if result:
                    if result.get("exe", False):
                        com = random.choice(result["exe"]).strip()
                        prefix = await self.get_prefix(msg)
                        newmsg = copy(msg)
                        com = com.format(author=msg.author, guild=msg.guild, channel=msg.channel, message=msg)
                        newmsg.content = prefix + com
                        logger.info("Commande = " + newmsg.content)
                        await self.bot.process_commands(newmsg)
        else:
            resp = random.choice(["Que puis-je faire pour vous ?", "Oui ?", "Vous m'avez appelé ?", "???",
                                  "Que voulez-vous ?"])
            await channel.send(resp)

    @commands.command(aliases=["parle"])
    @commands.max_concurrency(3, commands.BucketType.guild)
    async def talk(self, ctx, *txt):
        """Parle avec le bot"""
        if not ctx.author.bot:
            await self.answer_diag(ctx.message, txt)
            logger.info(f"Commande = " + repr(txt))

    @commands.group(name="talkset")
    @checks.admin_or_permissions(manage_messages=True)
    async def _pathfinder_talk(self, ctx):
        """Gestion des dialogues du chatbot Pathfinder"""

    def parse_dialogue(self, string):
        dlg = string.split()
        empty = {"q": None,
                 "a": None,
                 "ctx_in": [],
                 "ctx_out": [],
                 "exe": []}
        if "=>" in dlg:
            struc = re.split("=>|&[ioe]", string)
            struc[0] = self.normalize(struc[0])
            empty["q"] = tuple([i.strip() for i in struc[0].split("|")])
            empty["a"] = tuple([i.strip().replace("\\n", "\n") for i in struc[1].split("|")])

            if len(struc) > 2:
                reg = re.compile(r"(&[ioe])\s?([\w\s\|]+)", re.DOTALL | re.IGNORECASE).findall(string)
                if reg:
                    for balise, contenu in reg:
                        contenu = contenu.strip().split("|")
                        if contenu:
                            if balise == "&i":
                                empty["ctx_in"] = contenu
                            elif balise == "&o":
                                empty["ctx_out"] = contenu
                            elif balise == "&e" and not [i for i in contenu if i.startswith("talkset")]:
                                empty["exe"] = contenu
            if empty["q"] and empty["a"]:
                return empty
        return {}

    @_pathfinder_talk.command(name="add")
    async def add_dialogue(self, ctx, *dlg):
        """Ajouter un dialogue

        - Les questions d'exemple ne doivent pas contenir de `?`, n'ont pas besoin de majuscule ni de lettres accentuées
        - Pour insérer des sauts de ligne utilisez `\\n`
        - Balises optionnelles :
           `&i` = Ajouter un contexte d'entrée (mot-clef permettant d'améliorer la pertinence des réponses)
           `&o` = Ajouter un contexte de sortie
           `&e` = Executer une/des commandes (s'il y en a plusieurs, en exécute une au hasard)

        **__Format :__**
        `;talkset add phrase 1|phrase 2|phrase N => reponse 1|reponse 2|reponse N &i ctx1|ctx2|ctxN &o ctx1|ctx2|ctxN &e commande1|commande2|commandeN`

        **Exemple simple :** `;talkset add quelle est la couleur du ciel => Le ciel est bleu`

        **Exemple pro :** `;talkset add comment rejoindre un salon vocal|comment on rejoint le vocal => Cliquez sur le nom du salon vocal dans la liste à gauche &i help &o help|audio`"""
        guild = ctx.guild
        parsed = self.parse_dialogue(" ".join(dlg))
        if parsed:
            result = await self.match_query(ctx.guild, self.normalize(parsed["q"][0]))
            if not result:
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
                    "**Dialogue proche déjà utilisé** • Utilisez une formulation différente ou supprimez l'ancien dialogue avec `;talkset remove`.")
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
                qtxt = "\n".join(("- " + q for q in result["q"]))
                em.add_field(name="Questions (normalisées)", value=qtxt)
                atxt = "\n".join(("- " + q for q in result["a"]))
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

    @_pathfinder_talk.command(name="mention")
    async def talk_on_mention(self, ctx):
        """Activer/désactiver la réponse lors de la mention du bot"""
        guild = ctx.guild
        mention = await self.config.guild(guild).on_mention()
        if mention:
            await ctx.send("**Désactivé** • Le bot ne répondra plus lors de sa mention.")
        else:
            await ctx.send(
                "**Activé** • Le bot répondra à ses mentions.")
        await self.config.guild(guild).on_mention.set(not mention)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild:
            if message.mentions:
                if not message.author.bot:
                    if len(message.mentions) == 1 and message.mentions[0] == self.bot.user:
                        if await self.config.guild(message.guild).on_mention():
                            content = message.content.replace(f"@!{self.bot.user.id}", "")
                            await self.answer_diag(message, tuple(content.split()))
                            logger.info(f"Mention = " + repr(tuple(content.split())))
