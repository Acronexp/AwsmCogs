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

logger = logging.getLogger("red.AwsmCogs.checkpoint")

class Checkpoint(commands.Cog):
    """Base de données des jeux joués, groupes de jeux et outils liés"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=736144321857978388, force_registration=True)

        default_guild = {"autostream_channels": {}}
        default_user = {"games": [],
                        "private": False}
        default_global = {"Games": {},
                          "Sensib": 2}
        self.config.register_guild(**default_guild)
        self.config.register_user(**default_user)
        self.config.register_global(**default_global)

        try:
            self.social = self.bot.get_cog("Social")
        except:
            self.social = None
            logger.info("Impossible de charger Social.py, la pertinence ne pourra être optimisée")

    async def create_gamekey(self):
        key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        games = await self.config.Games()
        while key in games:
            key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return key

    async def get_game_named(self, name: str, database: str = "verified"):
        games = await self.verified_games() if database == "verified" else await self.config.Games()
        for g in games:
            if games[g]["name"].strip().lower() == name.strip().lower() or \
                    name.strip().lower() in (k.lower() for k in games[g].get("other_names", [])):
                return g
        return None

    async def verified_games(self):
        games = await self.config.Games()
        valid = {}
        for g in games:
            if games[g]["uses"] >= await self.config.Sensib() and not games[g].get("exclude", False):
                valid[g] = games[g]
        return valid

    async def user_verified_games(self, user: discord.Member):
        games = await self.config.user(user).games()
        all_games = await self.config.Games()
        verif = []
        for g in games:
            if all_games[g]["uses"] >= await self.config.Sensib() and not all_games[g].get("exclude", False):
                verif.append(g)
        return verif

    async def get_pertinence(self, members: List[discord.Member]):
        output = []
        if self.social:
            soc = await self.social.config.all_members(members[0].guild)
            for m in members:
                if m.id in soc:
                    output.append((m, len(soc[m.id]["cons_days"])))
                else:
                    output.append((m, 0))
            output = sorted(output, key=operator.itemgetter(1), reverse=True)
            return output
        return [(m, 0) for m in members]

    async def get_gamekey(self, ctx, search: str, *, cutoff: int = 70, database: str = "verified"):
        """Recherche automatiquement la clef du jeu"""
        em_color = await ctx.embed_color()
        games = await self.verified_games() if database == "verified" else await self.config.Games()
        async with ctx.channel.typing():
            if len(search) == 6:
                if search.upper() in games:
                    return search.upper()
            gamenames = (games[game]["name"].lower() for game in games)
            result = process.extractBests(search.lower(), gamenames, score_cutoff=cutoff)
            if result:
                if result[0][1] == 100:
                    gamename = result[0][0]
                    return await self.get_game_named(gamename, database)
                else:
                    table = []
                    for g in result:
                        key = await self.get_game_named(g[0], database)
                        realname = games[key]["name"]
                        score = f"{g[1]}%"
                        table.append([key, realname, score])
                    em = discord.Embed(description="```" + tabulate(
                        table, headers=["ID", "Nom", "Pertinence"]) + "```",
                                       color=em_color)
                    title = f"Recherche Checkpoint · \"{search}\""
                    if database != "verified":
                        title = f"Recherche Checkpoint (avancée) · \"{search}\""
                    em.set_author(name=title, icon_url=ctx.author.avatar_url)
                    em.set_footer(text="» Entrez l'ID du jeu ou 'aucun' s'il n'y figure pas")
                    msg = await ctx.send(embed=em)

                    def check(msg: discord.Message):
                        return msg.author == ctx.author and (len(msg.content) == 6 or msg.content.lower() in ("non", "aucun", "no", "none"))

                    try:
                        resp = await self.bot.wait_for("message", check=check, timeout=30)
                    except asyncio.TimeoutError:
                        await msg.delete()
                        return

                    if resp.content.upper() in games:
                        await msg.delete()
                        return resp.content.upper()
                    else:
                        await msg.delete()
            return None

    async def new_game(self, ctx, search: str):
        """Cherche le jeu à ajouter, sinon en crée un nouveau"""
        em_color = await ctx.embed_color()
        user = ctx.author
        games = await self.config.Games()
        key = await self.get_gamekey(ctx, search)
        if key:
            usergames = await self.config.user(user).games()
            if key not in usergames:
                usergames.append(key)
                games[key]["uses"] += 1
                await self.config.user(user).games.set(usergames)
                await self.config.Games.set(games)
                await ctx.send("**Jeu ajouté à votre bibliothèque** • Consultez-la avec `;cp list`")
            else:
                await ctx.send("**Jeu déjà présent dans votre bibliothèque** • Consultez-la avec `;cp list`")
        else:
            em = discord.Embed(description="**Je n'ai pas trouvé ce jeu dans ceux qui ont été vérifiés**, nous allons donc ajouter votre jeu pour qu'il soit reconnu par Checkpoint. D'abord, choisissez une méthode d'ajout :\n"
                                           "- `detect` : faire détecter le jeu par Checkpoint (PC uniquement)\n"
                                           "- `manuel` : chercher/entrer manuellement le nom du jeu (toutes plateformes)", color=em_color)
            em.set_author(name=f"Checkpoint · Proposer un nouveau jeu",
                          icon_url=ctx.author.avatar_url)
            em.set_footer(text="» Entrez le nom de la méthode que vous voulez utiliser")
            msg = await ctx.send(embed=em)

            def check(msg: discord.Message):
                return msg.author == ctx.author

            try:
                resp = await self.bot.wait_for("message", check=check, timeout=30)
            except asyncio.TimeoutError:
                await msg.delete()
                return

            if resp.content.lower() == "detect":
                await msg.delete()
                return await ctx.send("**Aucune action à réaliser** • Vous n'avez qu'à lancer le jeu sur votre PC en laissant "
                               "Discord affiche votre jeu et il sera automatiquement reconnu.\n"
                               "Sachez que si votre jeu n'a jamais été détecté auparavant, il n'apparaîtra pas dans "
                               "votre bibliothèque puisque Checkpoint a besoin de vérifier que plusieurs joueurs le possède pour le considérer comme un jeu vérifié")

            elif resp.content.lower() in ["manuel", "manual"]:
                await msg.delete()
                keybis = await self.get_gamekey(ctx, search, database="all")
                if keybis:
                    usergames = await self.config.user(user).games()
                    if keybis not in usergames:
                        usergames.append(keybis)
                        games[keybis]["uses"] += 1
                        await self.config.user(user).games.set(usergames)
                        await self.config.Games.set(games)
                        await ctx.send("**Jeu ajouté à votre bibliothèque** • Consultez-la avec `;cp list`")
                    else:
                        await ctx.send("**Jeu déjà présent dans votre bibliothèque** • Consultez-la avec `;cp list`")
                else:
                    em = discord.Embed(
                        description="Entrez le nom du jeu **en entier** que vous voulez ajouter.\nVérifiez son nom complet et officiel sur internet (wikipedia, metacritics etc.).", color=em_color)
                    em.set_author(name=f"Checkpoint · Proposer un nouveau jeu",
                                  icon_url=ctx.author.avatar_url)
                    em.set_footer(text="» Entrez le nom complet du jeu à ajouter")
                    msg = await ctx.send(embed=em)

                    def check(msg: discord.Message):
                        return msg.author == ctx.author

                    try:
                        resp = await self.bot.wait_for("message", check=check, timeout=30)
                    except asyncio.TimeoutError:
                        await msg.delete()
                        return

                    searchbis = resp.content
                    await msg.delete()
                    usergames = await self.config.user(user).games()
                    if not await self.get_game_named(searchbis.strip().lower()):
                        key = await self.create_gamekey()
                        games[key] = {"name": searchbis.strip(),
                                      "uses": 1,
                                      "exclude": False}
                        usergames.append(key)
                        await ctx.send("**Jeu ajouté à Checkpoint** • Il ne figurera pas dans votre bibliothèque tant "
                                       "qu'il n'existe pas au moins {} exemplaires sur tous les serveurs.".format(await self.config.Sensib()))
                    else:
                        key = await self.get_game_named(searchbis.strip().lower())
                        if key not in usergames:
                            usergames.append(key)
                            games[key]["uses"] += 1
                            await ctx.send("**Jeu ajouté à votre bibliothèque** • Consultez-la avec `;cp list`")
                    await self.config.user(user).games.set(usergames)
                    await self.config.Games.set(games)
            else:
                await msg.delete()
                return await ctx.send("**Action annulée**")

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        """Met à jour la liste de jeux reconnus + les jeux du membre"""
        if isinstance(after, discord.Member):
            if not after.bot:
                activities = after.activities
                if activities:
                    playing = [c for c in after.activities if c.type == discord.ActivityType.playing]
                    if playing:
                        all_games = await self.config.Games()
                        for game in playing:
                            if game.name[0] in ["!", "?"]:
                                continue
                            search = await self.get_game_named(game.name.strip(), database="all")
                            if not search:
                                key = await self.create_gamekey()
                                all_games[key] = {"name": game.name.strip(),
                                                  "uses": 1,
                                                  "exclude": False,
                                                  "other_names": []}
                            else:
                                key = search
                                usergames = await self.config.user(after).games()
                                if key not in usergames:
                                    usergames.append(key)
                                    all_games[key]["uses"] += 1
                                    await self.config.user(after).games.set(usergames)
                        await self.config.Games.set(all_games)

    @commands.command(name="playing")
    @commands.guild_only()
    async def cp_playing_now(self, ctx, *gamename):
        """Recherche les membres jouant actuellement au jeu

        Les membres sont triés par pertinence"""
        guild = ctx.guild
        games = {}
        for m in guild.members:
            if m.activities:
                if not await self.config.user(m).private():
                    playing = [c for c in m.activities if c.type == discord.ActivityType.playing]
                    if playing:
                        for game in playing:
                            name = game.name.strip()
                            if name not in games:
                                games[name] = [m]
                            else:
                                games[name].append(m)
        gamename = " ".join(gamename)
        gamename = gamename.strip()
        if gamename not in list(games.keys()):
            result = process.extractOne(gamename, list(games.keys()), score_cutoff=90)
            if result:
                gamename = result[0]
            else:
                return await ctx.send("**Jeu introuvable** • Personne ne semble jouer à votre jeu, sinon vérifiez l'orthographe")
        players = [p for p in games[gamename]]
        players = [i[0] for i in await self.get_pertinence(players)]
        txt = ""
        page = 1
        em_color = await ctx.embed_color()
        for p in players:
            name = str(p)
            chunk = f"*{name}*\n"
            if len(txt) + len(chunk) <= 2000:
                txt += chunk
            else:
                em = discord.Embed(title=f"\🔴 __**Checkpoint**__ · Jouant actuellement à \"{gamename}\"", description=txt,
                                   color=em_color)
                em.set_footer(text=f"Page #{page} (sur ce serveur)")
                await ctx.send(embed=em)
                txt = chunk
                page += 1
        if txt:
            em = discord.Embed(title=f"\🔴 __**Checkpoint**__ · Jouant actuellement à \"{gamename}\"", description=txt,
                               color=em_color)
            em.set_footer(text=f"Page #{page} (sur ce serveur)")
            await ctx.send(embed=em)


    @commands.command(name="players")
    @commands.guild_only()
    async def cp_players(self, ctx, *game):
        """Recherche des membres du serveur possédant le jeu demandé

        Il est possible de rentrer directement l'ID du jeu s'il est connu, sinon la commande lancera une recherche par titre
        Les membres sont triés par pertinence"""
        em_color = await ctx.embed_color()
        if game:
            key = await self.get_gamekey(ctx, " ".join(game))
            games = await self.verified_games()
            if key:
                game = games[key]
                gamename = game["name"]
                players = []
                all_users = await self.config.all_users()
                for m in ctx.guild.members:
                    if m.id in all_users:
                        if not all_users[m.id].get("private", False):
                            if key in all_users[m.id]["games"]:
                                players.append(m)
                if players:
                    players = [i[0] for i in await self.get_pertinence(players)]
                    txt = f"Utilisez `;playing {key}` pour voir les membres qui y jouent actuellement\n\n"
                    page = 1
                    for p in players:
                        name = str(p)
                        chunk = f"*{name}*\n"
                        if len(txt) + len(chunk) <= 2000:
                            txt += chunk
                        else:
                            em = discord.Embed(title=f"__**Checkpoint**__ · Membres possédant \"{gamename}\"", description=txt,
                                               color=em_color)
                            em.set_footer(text=f"Page #{page} (sur ce serveur)")
                            await ctx.send(embed=em)
                            txt = chunk
                            page += 1
                    if txt:
                        em = discord.Embed(title=f"__**Checkpoint**__ · Membres possédant \"{gamename}\"", description=txt,
                                           color=em_color)
                        em.set_footer(text=f"Page #{page} (sur ce serveur)")
                        await ctx.send(embed=em)
                else:
                    await ctx.send("**Aucun joueur** • Personne sur ce serveur ne joue à ce jeu")
            else:
                await ctx.send("**Inconnu** • La recherche n'a pas donné de résultats concluants")
        else:
            await ctx.send("**???** • Entrez l'ID du jeu ou des termes à rechercher")

    @commands.command(name="games")
    async def cp_games(self, ctx, *game):
        """Recherche parmi les jeux reconnus par Checkpoint"""
        em_color = await ctx.embed_color()
        games = await self.verified_games()
        if game:
            key = await self.get_gamekey(ctx, " ".join(game))
            if key:
                game = games[key]
                players = []
                gamename = game["name"]
                other_games = game.get("other_names", [])
                if other_games:
                    others = ", ".join((g for g in other_games))
                else:
                    others = "Aucun"
                if not isinstance(ctx.channel, discord.DMChannel):
                    all_users = await self.config.all_users()
                    for m in ctx.guild.members:
                        if m.id in all_users:
                            if key in all_users[m.id]["games"]:
                                players.append(m)
                    txt = "**Nb. de détections** - {}\n" \
                          "**Estimation du nb. de joueurs ici** - {}\n" \
                          "**Autres noms** - {}".format(game["uses"], len(players), others)
                else:
                    txt = "**Nb. de détections** - {}\n" \
                          "**Autres noms** - {}".format(game["uses"], others)
                em = discord.Embed(title=f"__**Checkpoint**__ · *{gamename}*", description=txt,
                                   color=em_color)
                if players:
                    em.set_footer(text=f"Pour avoir une liste des joueurs, utilisez \";players {key}\"")
                await ctx.send(embed=em)
            else:
                await ctx.send("**Inconnu** • Ce jeu n'est pas encore reconnu par Checkpoint")
        else:
            if not isinstance(ctx.channel, discord.DMChannel):
                options_txt = "📃 · Recevoir une liste des jeux reconnus (MP)\n" \
                              "❌ · Annuler"
                em = discord.Embed(title=f"Voulez-vous recevoir la liste complète des jeux reconnus par **Checkpoint** ?",
                                   description=options_txt, color=em_color)
                em.set_footer(text="⚠️Le bot doit pouvoir vous envoyer un MP")
                msg = await ctx.send(embed=em)
                emojis = ["📃", "❌"]

                start_adding_reactions(msg, emojis)
                try:
                    react, user = await self.bot.wait_for("reaction_add",
                                                          check=lambda r, u: u == ctx.author and r.message.id == msg.id,
                                                          timeout=20)
                except asyncio.TimeoutError:
                    await msg.delete()
                    return
                else:
                    emoji = react.emoji

                if emoji != "📃":
                    await msg.delete()
                    return
                else:
                    await msg.delete()

            date = datetime.now().strftime("%d/%m/%Y %Hh%M")
            txt = f"Liste à jour du {date}\n\n"
            page = 1
            all_games = []
            for g in games:
                all_games.append((g, games[g]["name"].strip(), games[g]["name"].strip().lower()))
            all_games = sorted(all_games, key=operator.itemgetter(2))
            try:
                for g in all_games:
                    chunk = f"**{g[0]}** · *{g[1]}*\n"
                    if len(txt) + len(chunk) <= 2000:
                        txt += chunk
                    else:
                        em = discord.Embed(title=f"__**Checkpoint**__ · Jeux reconnus", description=txt,
                                           color=em_color)
                        em.set_footer(text=f"Page #{page}")
                        await ctx.author.send(embed=em)
                        txt = chunk
                        page += 1
                if txt:
                    em = discord.Embed(title=f"__**Checkpoint**__ · Jeux reconnus", description=txt,
                                       color=em_color)
                    em.set_footer(text=f"Page #{page} · La liste peut aussi contenir des logiciels")
                    await ctx.author.send(embed=em)
            except:
                await ctx.send("**Erreur** • Je n'ai pas accès à vos MP")


    @commands.group(name="checkpoint", aliases=["cp"])
    async def _checkpoint_profile(self, ctx):
        """Paramètres personnels Checkpoint"""

    @_checkpoint_profile.command()
    async def addgame(self, ctx, *game):
        """Ajouter un jeu de votre collection"""
        await self.new_game(ctx, " ".join(game))

    @_checkpoint_profile.command()
    async def delgame(self, ctx, *game):
        """Retirer un jeu"""
        games = await self.config.user(ctx.author).games()
        key = await self.get_gamekey(ctx, " ".join(game), database="all")
        if key:
            if key in games:
                games.remove(key)
                await self.config.user(ctx.author).games.set(games)
                all_games = await self.config.Games()
                all_games[key]["uses"] -= 1
                await self.config.Games.set(all_games)
                await ctx.send("**Jeu retiré** • Il ne figurera plus dans votre collection")
            else:
                await ctx.send("**Non possédé** • Ce jeu ne figure pas dans votre collection")
        else:
            await ctx.send("**Inconnu** • Ce jeu n'existe pas dans la base de données Checkpoint")

    @_checkpoint_profile.command()
    async def list(self, ctx, user: discord.Member = None):
        """Liste les jeux possédés"""
        user = user if user else ctx.author
        jeux = await self.user_verified_games(user)
        all_user_games = await self.config.user(user).games()
        if jeux:
            games = await self.config.Games()
            all_games = []
            not_verified = 0
            for j in jeux:
                all_games.append((j, games[j]["name"].strip(), games[j]["name"].strip().lower()))
            for g in all_user_games:
                if g not in jeux:
                    not_verified += 1
            all_games = sorted(all_games, key=operator.itemgetter(2))
            txt = ""
            page = 1
            plus = ""
            if not_verified == 1:
                plus = f" • +{not_verified} jeu non vérifié"
            elif not_verified > 1:
                plus = f" • +{not_verified} jeux non vérifiés"

            for g in all_games:
                chunk = f"**{g[0]}** · *{g[1]}*\n"
                if len(txt) + len(chunk) <= 2000:
                    txt += chunk
                else:
                    em = discord.Embed(description=txt, color=user.color, timestamp=ctx.message.created_at)
                    em.set_author(name=f"Checkpoint · {user}", icon_url=user.avatar_url)
                    em.set_footer(text=f"Page #{page}{plus}")
                    await ctx.send(embed=em)
                    txt = chunk
                    page += 1
            if txt:
                em = discord.Embed(description=txt, color=user.color, timestamp=ctx.message.created_at)
                em.set_author(name=f"Checkpoint · {user}", icon_url=user.avatar_url)
                em.set_footer(text=f"Page #{page}{plus}")
                await ctx.send(embed=em)
        else:
            await ctx.send("**Bibliothèque vide** • Aucun jeu n'a été détecté ou enregistré avec ce compte")

    @_checkpoint_profile.command()
    async def private(self, ctx):
        """Rendre vos jeux privés, vous effaçant de toutes les commandes liées à Checkpoint sauf `;cp list`

        Cette commande s'applique sur tous les serveurs où vous et le bot se trouvent"""
        author = ctx.author
        priv = await self.config.user(author).private()
        if priv:
            await ctx.send("**Public** • Votre bibliothèque est désormais publique")
        else:
            await ctx.send("**Privé** • Votre bibliothèque est désormais restreinte aux seuls membres cherchant spécifiquement vos jeux")
        await self.config.user(author).private.set(not priv)

    @commands.group(name="checkpointset", aliases=["cpset"])
    @checks.admin_or_permissions(manage_messages=True)
    async def _checkpoint_params(self, ctx):
        """Paramètres Checkpoint"""


    @_checkpoint_params.group(name="autostream")
    async def _checkpoint_autostream(self, ctx):
        """Réglages des salons d'autostream"""

    @_checkpoint_autostream.command(name="add")
    async def autostream_add(self, ctx, channel: discord.VoiceChannel = None, *basename):
        """Ajoute un salon vocal qui sera renommé automatiquement pour les streams

        Le nom du salon s'adaptera automatiquement au nom du jeu joué
        Préciser *basename* permet de définir un nom de "base" qui sera remis entre chaque stream et depuis lequel sera ajouté le nom du jeu"""
        guild = ctx.guild
        basename = " ".join(basename) if basename else channel.name
        chans = await self.config.guild(guild).autostream_channels()
        if channel:
            if channel.id not in chans:
                chans[channel.id] = basename
                await self.config.guild(guild).autostream_channels.set(chans)
                await ctx.send(f"**Salon vocal ajouté** • Le nom du salon sera automatiquement adapté en fonction du nom du jeu streamé")
            else:
                await ctx.send("**Déjà présent** • Ce salon est déjà présent, si vous voulez le retirer utilisez `;cpset autostream remove`")
        elif chans:
            txt = ""
            for c in chans:
                vc = guild.get_channel(c)
                bn = chans[c]
                txt += f"{vc.mention} (*{bn}*)\n"
            em = discord.Embed(title="Salons adaptés automatiquement", description=txt)
            await ctx.send(embed=em)
        else:
            await ctx.send(
                "**Aucun salon** • Aucun salon n'utilise cette fonctionnalité, si vous voulez en ajouter un utilisez `;cpset autostream add`")

    @_checkpoint_autostream.command(name="remove")
    async def autostream_remove(self, ctx, channel: discord.VoiceChannel = None):
        """Retire un salon vocal de la fonction autostream (renommage auto. du salon pendant le stream)"""
        guild = ctx.guild
        chans = await self.config.guild(guild).autostream_channels()
        if channel:
            if channel.id in chans:
                del chans[channel.id]
                await self.config.guild(guild).autostream_channels.set(chans)
                await ctx.send(
                    f"**Salon vocal retiré** • Le salon ne sera plus adapté au stream.")
            else:
                await ctx.send(
                    "**Non présent** • Ce salon n'est pas dans la liste, si vous voulez l'ajouter utilisez `;cpset autostream add`")
        elif chans:
            txt = ""
            for c in chans:
                vc = guild.get_channel(c)
                bn = chans[c]
                txt += f"{vc.mention} (*{bn}*)\n"
            em = discord.Embed(title="Salons adaptés automatiquement", description=txt)
            await ctx.send(embed=em)
        else:
            await ctx.send(
                "**Aucun salon** • Aucun salon n'utilise cette fonctionnalité, si vous voulez en ajouter un utilisez `;cpset autostream add`")


    @_checkpoint_params.command()
    @commands.is_owner()
    async def exclude(self, ctx, key: str):
        """Exclue un jeu de la liste des jeux vérifiés"""
        games = await self.config.Games()
        key = key.upper()
        if key in games:
            if "exclude" in games[key]:
                if games[key]["exclude"]:
                    games[key]["exclude"] = False
                    await self.config.Games.set(games)
                    return await ctx.send("**Modifié** • Ce jeu ne sera plus exclu")
            games[key]["exclude"] = True
            await self.config.Games.set(games)
            return await ctx.send("**Modifié** • Ce jeu est désormais exclu de la liste des jeux vérifiés")
        else:
            await ctx.send("**Erreur** • Identifiant de jeu inconnu")

    @_checkpoint_params.command()
    @commands.is_owner()
    async def sensib(self, ctx, sens: int):
        """Change la sensibilité qui délimite les vrais jeux des faux

        Plus la valeur est haute plus il faut avoir détecté le jeu pour qu'il soit considéré comme vrai"""
        if sens > 1:
            await self.config.Sensib.set(sens)
            await ctx.send(f"**Modifié** • La sensibilité est désormais à {sens}")
        else:
            await ctx.send(f"**Invalide** • La sensibilité doit être supérieure à 1")

    @_checkpoint_params.command()
    @commands.is_owner()
    async def deldetect(self, ctx, key: str):
        """Supprime les données d'un jeu"""
        games = await self.config.Games()
        key = key.upper()
        if key in games:
            del games[key]
            await self.config.Games.set(games)
            await ctx.send(f"**Succès** • Les données du jeu ont été supprimées")
        else:
            await ctx.send(f"**Invalide** • Cet ID est introuvable")

    @_checkpoint_params.command()
    @commands.is_owner()
    async def delstarting(self, ctx, namestart: str):
        """Supprime les données de tous les 'jeux' commençant par..."""
        games = await self.config.Games()
        gcopy = deepcopy(games)
        for g in gcopy:
            if gcopy[g]["name"].lower().startswith(namestart):
                del games[g]
        await self.config.Games.set(games)
        await ctx.send(f"**Succès** • Les données de ces jeux ont été supprimées")

    @_checkpoint_params.command()
    @commands.is_owner()
    async def resetdetect(self, ctx, key: str):
        """Retire un jeu de tous les membres s'il a été détecté chez lui"""
        games = await self.config.Games()
        key = key.upper()
        if key in games:
            async with ctx.channel.typing():
                games["uses"] = await self.config.Sensib()
                all_users = deepcopy(await self.config.all_users())
                for u in all_users:
                    user = self.bot.get_user(u)
                    if key in all_users[u]["games"]:
                        all_users[u]["games"].remove(key)
                        await self.config.user(user).games.set(all_users[u]["games"])
            await ctx.send(f"**Succès** • Les données du jeu ont été reset pour les utilisateurs")
        else:
            await ctx.send(f"**Invalide** • Cet ID est introuvable")

    @_checkpoint_params.command(name="link")
    @commands.is_owner()
    async def link_games(self, ctx, basekey: str, *to_link):
        """Lie plusieurs jeux entre eux pour qu'ils ne soient considérés comme qu'un"""
        games = await self.config.Games()
        basekey = basekey.upper()
        if basekey in games and to_link:
            async with ctx.channel.typing():
                all_users = deepcopy(await self.config.all_users())
                other = []
                if "other_names" in games[basekey]:
                    other = games[basekey]["other_names"]

                for k in to_link:
                    if k.upper() in games:
                        if games[k.upper()]["name"] not in other:
                            other.append(games[k.upper()]["name"])
                            games[basekey]["uses"] += games[k.upper()]["uses"]

                        if "other_names" in games[k.upper()]:
                            for o in games[k.upper()]["other_names"]:
                                if o not in other and o != games[basekey]["name"]:
                                    other.append(o)

                        for u in all_users:
                            user = self.bot.get_user(u)
                            if k.upper() in all_users[u]["games"]:
                                all_users[u]["games"].remove(k.upper())
                                if basekey not in all_users[u]["games"]:
                                    all_users[u]["games"].append(basekey)
                                await self.config.user(user).games.set(all_users[u]["games"])

                        del games[k.upper()]
                    else:
                        return await ctx.send(f"**Erreur** • Une des clef données n'existe pas")

                games[basekey]["other_names"] = other
                await self.config.Games.set(games)
                await ctx.send(f"**Succès** • Les données des jeux sélectionnés ont été transférés sur le jeu de base")
        else:
            await ctx.send(f"**Invalide** • Cet ID de jeu est introuvable")

    @commands.Cog.listener()
    async def on_voice_state_update(self, user, before, after):
        if user.guild:
            if before.self_stream > after.self_stream:
                channel = after.channel
                if channel.id in await self.config.guild(user.guild).autostream_channels():
                    basename = await self.config.guild(user.guild).autostream_channels.get_raw(channel.id)
                    if channel.name != basename:
                        await channel.edit(name=basename, reason="Reset automatique du salon")
            elif before.self_stream < after.self_stream:
                channel = after.channel
                if channel.id in await self.config.guild(user.guild).autostream_channels():
                    playing = [c for c in user.activities if c.type == discord.ActivityType.playing]
                    if playing:
                        game = playing[0]
                        basename = await self.config.guild(user.guild).autostream_channels.get_raw(channel.id)
                        await channel.edit(name=basename + f" · {game.name.strip()}", reason="Adaptation automatique du salon au jeu streamé")