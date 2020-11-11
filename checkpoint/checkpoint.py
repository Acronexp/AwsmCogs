import asyncio
import logging

import discord
import random
import string
from datetime import datetime

from fuzzywuzzy import process
from redbot.core import Config, checks, commands
from redbot.core.utils.menus import start_adding_reactions
from tabulate import tabulate

logger = logging.getLogger("red.AwsmCogs.checkpoint")

class Checkpoint(commands.Cog):
    """Système de groupes de jeux"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=736144321857978388, force_registration=True)

        default_guild = {}
        default_user = {"games": []}
        default_global = {"Games": {}}
        self.config.register_guild(**default_guild)
        self.config.register_user(**default_user)
        self.config.register_global(**default_global)

    async def create_gamekey(self):
        key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        games = await self.config.Games()
        while key in games:
            key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return key

    async def get_game_named(self, name: str):
        games = await self.config.Games()
        for g in games:
            if games[g]["name"].lower() == name.lower():
                return g
        return None

    async def get_gamekey(self, ctx, search: str):
        """Recherche automatiquement la clef du jeu"""
        em_color = await ctx.embed_color()
        games = await self.config.Games()
        async with ctx.channel.typing():
            key = None
            if len(search) == 6:
                if search in games:
                    return search
            gamenames = (game["name"].lower() for game in games)
            result = process.extractBests(search.lower(), gamenames, score_cutoff=50)
            if result:
                if result[0][1] == 100:
                    gamename = result[0][0]
                    return await self.get_game_named(gamename)
                else:
                    table = []
                    for g in result:
                        key = await self.get_game_named(g[0])
                        realname = games[key]["name"]
                        score = f"{g[1]}%"
                        table.append([key, realname, score])
                    em = discord.Embed(description="```" + tabulate(
                        table, headers=["ID", "Nom", "Score"]) + "```",
                                       color=em_color)
                    em.set_author(name=f"__**Recherche Checkpoint**__ · \"{search}\"",
                                  icon_url=ctx.author.avatar_url)
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
                        return resp.content
                    else:
                        await msg.delete()
            return None

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        """Met à jour la liste de jeux reconnus + les jeux du membre"""
        if isinstance(after, discord.Member):
            activities = after.activities
            if activities:
                playing = [c for c in after.activities if c.type == discord.ActivityType.playing]
                if playing:
                    all_games = await self.config.Games()
                    for game in playing:
                        if game.name.lower() not in [all_games[g]["name"].lower() for g in all_games]:
                            key = await self.create_gamekey()
                            all_games[key] = {"name": game.name,
                                              "uses": 1}
                        else:
                            key = [g for g in all_games if all_games[g]["name"].lower() == game.name.lower()][0]
                            all_games[key]["uses"] += 1
                            usergames = await self.config.user(after).games()
                            if key not in usergames:
                                usergames.append(key)
                                await self.config.user(after).games.set(usergames)
                        await self.config.Games.set(all_games)

    @commands.group(name="players", aliases=["gs"])
    @commands.guild_only()
    async def cp_players(self, ctx, *game):
        """Recherche des membres du serveur possédant le jeu demandé

        Il est possible de rentrer directement l'ID du jeu s'il est connu, sinon la commande lancera une recherche par titre"""
        em_color = await ctx.embed_color()
        if game:
            key = await self.get_gamekey(ctx, " ".join(game))
            if key:
                game = await self.config.Games()[key]
                gamename = game["name"]
                players = []
                all_users = await self.config.all_users()
                for m in ctx.guild.members:
                    if m.id in all_users:
                        if key in all_users[m.id]["games"]:
                            players.append(m)
                if players:
                    txt = ""
                    page = 1
                    for p in players:
                        chunk = f"{p.mention}\n"
                        if len(txt) + len(chunk) <= 2000:
                            txt += chunk
                        else:
                            em = discord.Embed(title=f"__**Checkpoint**__ · Joueurs de \"{gamename}\"", description=txt,
                                               color=em_color)
                            em.set_footer(text=f"Page #{page}")
                            await ctx.send(embed=em)
                            txt = chunk
                            page += 1
                    if txt:
                        em = discord.Embed(title=f"__**Checkpoint**__ · Joueurs de \"{gamename}\"", description=txt,
                                           color=em_color)
                        em.set_footer(text=f"Page #{page}")
                        await ctx.send(embed=em)
                else:
                    await ctx.send("**Aucun joueur** • Personne sur ce serveur ne joue à ce jeu")
            else:
                await ctx.send("**Inconnu** • La recherche n'a pas donné de résultats concluants")
        else:
            await ctx.send("**???** • Entrez l'ID du jeu ou des termes à rechercher")

    @commands.group(name="games")
    async def cp_games(self, ctx, *game):
        """Recherche parmi les jeux reconnus par Checkpoint"""
        em_color = await ctx.embed_color()
        if game:
            key = await self.get_gamekey(ctx, " ".join(game))
            if key:
                game = await self.config.Games()[key]
                gamename = game["name"]
                players = []
                all_users = await self.config.all_users()
                for m in ctx.guild.members:
                    if m.id in all_users:
                        if key in all_users[m.id]["games"]:
                            players.append(m)
                txt = "**Détections** - {}\n" \
                      "**Estimation du nb. de joueurs ici** - {}".format(game["uses"], len(players))
                em = discord.Embed(title=f"__**Checkpoint**__ · *{gamename}*", description=txt,
                                   color=em_color)
                if players:
                    em.set_footer(text=f"Pour avoir une liste des joueurs, utilisez \";players {key}\"")
                await ctx.send(embed=em)
            else:
                await ctx.send("**Inconnu** • Ce jeu n'est pas encore reconnu par Checkpoint")
        else:
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

            if emoji == "📃":
                await msg.delete()
                games = await self.config.Games()
                date = datetime.now().strftime("%d/%m/%Y")
                txt = f"Liste à jour du {date}\n\n"
                page = 1
                try:
                    for g in games:
                        gamename = games[g]["name"]
                        chunk = f"**{g}** · *{gamename}*\n"
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
                        em.set_footer(text=f"Page #{page}")
                        await ctx.author.send(embed=em)
                except:
                    await ctx.send("**Erreur** • Je n'ai pas accès à vos MP")
            else:
                await msg.delete()
                return