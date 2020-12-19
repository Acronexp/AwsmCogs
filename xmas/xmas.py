import asyncio
import logging
import operator
import time

import discord
import random

from fuzzywuzzy import process, fuzz
from redbot.core import Config, checks, commands
from redbot.core.utils.menus import start_adding_reactions
from .content import *

logger = logging.getLogger("red.AwsmCogs.xmas")

# Constantes (ici pour que ce soit facile à changer)

_GIFTS_PTS = {
    1: (5, 15),
    2: (20, 40),
    3: (50, 75)
}

XMAS_COLORS = lambda: random.choice((0xff0000, 0xff7878, 0xfffffe, 0x74d680, 0x378b29))


class Gift:
    def __init__(self, name: str, lvl: int, dest: tuple):
        self.raw = {"name": name, "lvl": lvl, "dest": dest}

    def __str__(self):
        return f"**{self.name}** [{self.lvl}]"

    def __repr__(self):
        return self.__str__()

    def __int__(self):
        return self.lvl

    @property
    def name(self):
        return self.raw["name"]

    @name.setter
    def name(self, new: str):
        self.raw["name"] = new

    @property
    def lvl(self):
        return self.raw["lvl"]

    @lvl.setter
    def lvl(self, val: int):
        if 3 >= val > 0:
            self.raw["lvl"] = val

    @property
    def dest(self):
        return self.raw["dest"]


class XMas(commands.Cog):
    """Event de décembre 2020 (pensé pour L'Appart)"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=736144321857978388, force_registration=True)

        default_guild = {"teams": {"r": {"name": "Rouge",
                                         "team_score": 0, "stock": {}, "lvl": 0, "users": {}, "color": 0xfc0303,
                                         "namechange": 0, "leader": None},

                                   "v": {"name": "Verte",
                                         "team_score": 0, "stock": {}, "lvl": 0, "users": {}, "color": 0x2bd914,
                                         "namechange": 0, "leader": None},

                                   "b": {"name": "Bleue",
                                         "team_score": 0, "stock": {}, "lvl": 0, "users": {}, "color": 0x1582e8,
                                         "namechange": 0, "leader": None}},

                         "notif_channel": None,
                         "spawn_channel": None,
                         "counter_trigger": 100,
                         "spawn_cooldown": 300,
                         "dest_time": 600,
                         "between_travels_limits": (600, 1200),
                         "travel_pause_trigger": 600,
                         "travel_limits": (300, 1200),

                         "travel": []}
        default_member = {"user_score": 0,
                          "succes": []}
        default_global = {}
        self.config.register_guild(**default_guild)
        self.config.register_member(**default_member)
        self.config.register_global(**default_global)

        self.cache = {}

    def get_cache(self, guild: discord.Guild):
        if guild.id not in self.cache:
            self.cache[guild.id] = {"spawn_counter": 0,
                                    "last_spawn": 0,

                                    "traveling": False,
                                    "last_triggers": [],
                                    "between_travels": 300,
                                    "last_travel": 0,

                                    "idle": False}
        return self.cache[guild.id]

    def normalize(self, texte: str):
        """Normalise le texte en retirant accents, majuscules et tirets"""
        texte = texte.lower()
        norm = [l for l in "neeecaaiiuuoo "]
        modif = [l for l in "ñéêèçàäîïûùöô-"]
        fin_texte = texte
        for char in texte:
            if char in modif:
                ind = modif.index(char)
                fin_texte = fin_texte.replace(char, norm[ind])
        return fin_texte

    # TRAVEL ------------------

    async def get_travel(self, guild: discord.Guild):
        """Retourne la liste des destinations à venir et la complète si elle n'est inférieure à 10 éléments"""
        dest = await self.config.guild(guild).travel()
        if len(dest) < 10:
            while len(dest) < 10:
                dest.append(random.choice(DESTINATIONS))
            await self.config.guild(guild).travel.set(dest)
        return dest

    async def current_position(self, guild: discord.Guild):
        """Renvoie la position actuelle du traineau, en prenant en compte le voyage et la pause s'il y en a une"""
        travel = await self.get_travel(guild)
        cache = self.get_cache(guild)
        if not cache["traveling"] and not cache["travel_pause"]:
            return travel[0]
        return None

    async def calc_pause(self, guild: discord.Guild, triggers: list):
        params = await self.config.guild(guild).all()
        limit = params["travel_pause_trigger"]
        if len(triggers) > 2:
            if triggers[1] - triggers[0] >= limit and triggers[2] - triggers[1] >= limit:
                return True
        return False

    async def next_location(self, guild: discord.Guild):
        """Voyage vers la prochaine destination + lvl down les cadeaux non-livrés"""
        cache = self.get_cache(guild)
        if not cache["traveling"]:
            if cache["last_travel"] + cache["between_travels"] <= time.time():
                if not await self.calc_pause(guild, cache["last_triggers"]):
                    cache["traveling"] = True
                    if cache["travel_pause"]:
                        cache["travel_pause"] = False
                        await self.bot.change_presence(status=discord.Status.online)

                    params = await self.config.guild(guild).all()
                    travel = await self.get_travel(guild)
                    await self.level_down_gifts(guild, travel[0])
                    new_travel = travel[1:]
                    await self.config.guild(guild).travel.set(new_travel)
                    new_current = new_travel[0]
                    color = XMAS_COLORS()
                    emoji = random.choice(("🎁", "🎄", "☃️", "❄️"))
                    msg = "Voyage vers {}, {}...".format(new_current[0], new_current[1])
                    activ = discord.Activity(name=msg, type=discord.ActivityType.competing)
                    await self.bot.change_presence(status=discord.Status.dnd, activity=activ)
                    await self.send_notif(guild, f"{emoji} Prochaine destination", msg, color)
                    target = time.time() + random.randint(*params["travel_limits"])
                    while time.time() < target and cache["traveling"]:
                        await asyncio.sleep(5)
                    activ = discord.Activity()
                    await self.bot.change_presence(status=discord.Status.online, activity=activ)
                    await self.send_notif(guild, f"{emoji} Arrivée à destination",
                                          "Nous sommes arrivés à **{}**, {}.".format(new_current[0], new_current[1]), color)
                    cache["last_travel"] = time.time()
                    cache["between_travels"] = random.randint(*params["between_travels_limits"])
                    cache["traveling"] = False
                    return await self.get_travel(guild)
                elif self.bot.user.status == discord.Status.online and not cache["travel_pause"]:
                    cache["travel_pause"] = True
                    emoji = random.choice(("🎁", "🎄", "☃️", "❄️"))
                    text = random.choice(("Peu de voyageurs actuellement, faisons une pause.",
                                          "Peu de gens actifs, faisons une pause.",
                                          "Faisons une pause, peu de gens parlent actuellement sur le serveur."))
                    await self.send_notif(guild, f"{emoji} Voyage en pause", text, XMAS_COLORS())
                    activ = discord.Activity(name="Voyage en pause", type=discord.ActivityType.competing)
                    await self.bot.change_presence(status=discord.Status.idle, activity=activ)
            return False
        return False

    # NOTIFS -----------------

    async def send_notif(self, guild: discord.Guild, title: str, msg: str, color: hex = None):
        params = await self.config.guild(guild).all()
        channel = params.get("notif_channel", params["spawn_channel"])
        if channel:
            channel = guild.get_channel(channel)
            em = discord.Embed(title=title, description=msg, color=color if color else XMAS_COLORS())
            await channel.send(embed=em)
        else:
            raise KeyError("Aucun channel n'a été réglé pour les messages Xmas")

    # TEAMS ------------------

    async def get_team(self, guild: discord.Guild, team: str):
        teams = await self.config.guild(guild).teams()
        if team in teams:
            return teams[team]
        raise KeyError("La team n'existe pas")

    async def find_team(self, guild: discord.Guild, name: str):
        teams = await self.config.guild(guild).teams()
        for t in teams:
            if teams[t]["name"] == name:
                return t
        raise KeyError("La team n'existe pas")

    async def user_team(self, user: discord.Member):
        guild = user.guild
        teams = await self.config.guild(guild).teams()
        for team in teams:
            if str(user.id) in teams[team]["users"]:
                return team
        return None

    async def fetch_team_member(self, user: discord.Member):
        teams = await self.config.guild(user.guild).teams()
        team = await self.user_team(user)
        if team:
            return teams[team]["users"][str(user.id)]
        return None

    async def check_perms(self, user: discord.Member, perms: list):
        member = await self.fetch_team_member(user)
        teamname = await self.user_team(user)
        if teamname:
            team = await self.get_team(user.guild, teamname)
            if team["leader"] != user.id:
                for perm in perms:
                    if perm not in member:
                        return False
            return True
        return None

    async def team_users_score(self, guild: discord.Guild, team: str):
        team = await self.get_team(guild, team)
        data = await self.config.all_members(guild)
        users = team["users"]
        total = 0
        for u in users:
            total += data[int(u)]["user_score"]
        return total

    # USER ------------------

    async def get_user(self, user: discord.Member):
        return await self.config.member(user).all()

    # GIFTS -----------------

    def guess_gift(self, query: str, tol: int = 50):
        """Recherche un cadeau parmi la liste de TOUS les cadeaux possibles"""
        glist = [g.lower() for g in GIFTS]
        result = process.extractOne(query.lower(), glist, score_cutoff=tol, scorer=fuzz.partial_ratio)
        if result:
            return result[0]
        return None

    async def new_gift(self, guild: discord.Guild):
        """Génère un cadeau en prenant en compte le parcours à suivre"""
        travel = await self.get_travel(guild)
        dest = random.choice(travel[3:])
        gift = {"name": random.choice(GIFTS),
                "lvl": random.randint(1, 3),
                "dest": dest}
        return Gift(**gift)

    async def add_team_gift(self, guild: discord.Guild, team: str, gift: Gift):
        """Ajouter un cadeau à l'équipe"""
        data = await self.get_team(guild, team)
        if data:
            data["stock"].append(gift.raw)
            await self.config.guild(guild).teams.set_raw(team, value=data)
        else:
            raise KeyError("La team n'existe pas")

    async def remove_team_gift(self, guild: discord.Guild, team: str, gift: Gift):
        """Retirer un cadeau de l'équipe"""
        data = await self.get_team(guild, team)
        if data:
            if gift.raw in data["stock"]:
                data["stock"].remove(gift.raw)
                await self.config.guild(guild).teams.set_raw(team, value=data)
            else:
                r = repr(gift.raw)
                raise KeyError(f"L'item {r} n'est pas chez Team={team}")
        else:
            raise KeyError("La team n'existe pas")

    async def level_down_gifts(self, guild: discord.Guild, dest: tuple, team: str = None):
        """Baisser le niveau des cadeaux (ou les retirer si lvl 1) qui ont loupé leur destination"""
        if not team:
            teams = await self.config.guild(guild).teams()
            for team in teams:
                for g in teams[team]["stock"]:
                    if dest == g["dest"]:
                        if g["lvl"] > 1:
                            g["lvl"] -= 1
                        else:
                            teams[team]["stock"].remove(g)
            await self.config.guild(guild).teams.set(teams)
            return teams
        else:
            data = await self.get_team(guild, team)
            if data:
                for g in data["stock"]:
                    if dest == g["dest"]:
                        if g["lvl"] > 1:
                            g["lvl"] -= 1
                        else:
                            data["stock"].remove(g)
                await self.config.guild(guild).teams.set_raw(team, value=data)
            else:
                raise KeyError("La team n'existe pas")

    async def get_dest_gifts(self, guild: discord.Guild, team: str, dest: tuple):
        """Retourne les cadeaux d'une team prévus pour une destination"""
        team = await self.get_team(guild, team)
        gifts = []
        for g in team["stock"]:
            if g["dest"] == dest:
                gifts.append(Gift(**g))
        return gifts

    # ALGOS ==============================================

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild:
            guild = message.guild
            params = await self.config.guild(guild).all()
            if params["spawn_channel"]:
                cache = self.get_cache(guild)
                cache["last_triggers"].append(message.created_at.timestamp())
                cache["last_triggers"] = cache["last_triggers"][-3:]

                cache["spawn_counter"] += random.randint(0, 1)
                if cache["spawn_counter"] > params["counter_trigger"]:
                    if time.time() > cache["last_spawn"] + params["spawn_cooldown"]:
                        logger.info("Spawn de cadeau")
                        cache["idle"] = True
                        cache["last_spawn"] = time.time()
                        cache["spawn_counter"] = 0
                        await asyncio.sleep(random.randint(1, 10))
                        spawn_channel = guild.get_channel(params["spawn_channel"])

                        if spawn_channel:
                            # TODO: Maj ajoutant les "Rush" (equiv. de la distribution générale en octobre)

                            if random.randint(1, 4) < 4:
                                gift = await self.new_gift(guild)
                                emoji = random.choice(("🎁", "🎄", "☃️", "❄️"))
                                text = random.choice((
                                    f"Les lutins ont terminé de fabriquer {gift} Premier arrivé, premier servi.",
                                    f"Nouvelle livraison ! On a besoin d'une équipe pour livrer {gift} !",
                                    f"Besoin d'une équipe pour livrer {gift} rapidement !"
                                ))
                                emcolor = XMAS_COLORS()
                                em = discord.Embed(title=f"{emoji} La Grande distribution • Nouveau cadeau à livrer",
                                                   description=text, color=emcolor)
                                em.set_footer(text="» Récuperez en premier le cadeau pour votre équipe en cliquant sur la réaction")

                                spawn = await spawn_channel.send(embed=em)
                                start_adding_reactions(spawn, ["🎁"])
                                async def check_msg(r, u):
                                    return r.message.id == spawn.id and not u.bot and await self.user_team(u)

                                try:
                                    react, user = await self.bot.wait_for("reaction_add",
                                                                          check=check_msg,
                                                                          timeout=30)
                                except asyncio.TimeoutError:
                                    await spawn.delete()
                                    cache["spawn_counter"] = params["counter_trigger"] / 2
                                    return
                                else:
                                    userteam = await self.user_team(user)
                                    userscore = await self.config.member(user).user_score() + 10
                                    await self.config.member(user).user_score.set(userscore)
                                    await self.add_team_gift(guild, userteam, gift)
                                    team = await self.get_team(guild, userteam)
                                    wintxt = random.choice((
                                        f"{user.mention} a obtenu {gift} pour son équipe *{team['name']}* !",
                                        f"Bravo à {user.mention} qui permet à *{team['name']}* d'obtenir {gift} !"
                                    ))
                                    post_em = discord.Embed(title=f"{emoji} La Grande distribution • Nouveau cadeau à livrer obtenu",
                                                            description=wintxt, color=emcolor)
                                    post_em.set_footer(text="INFO · " + random.choice(ASTUCES))
                                    await spawn.edit(embed=post_em)
                                    await spawn.clear_reaction("🎁")
                                    await spawn.delete(delay=15)

                            else:
                                gift = await self.new_gift(guild)
                                gift.lvl = 3

                                emoji = random.choice(("🎁", "🎄", "☃️", "❄️"))
                                emcolor = XMAS_COLORS()
                                cap, pays = random.choice(DESTINATIONS)
                                if random.randint(0, 1):  # Trouver le pays
                                    guess = pays
                                    text = random.choice((
                                        f"Un lutin vous demande : si vous vous trouvez dans la ville de **{cap}**, dans quel pays êtes-vous ?",
                                        f"Votre GPS déconne et vous indique **{cap}**, de quel pays cette ville est la capitale ?",
                                        f"Un lutin vous appelle car il s'est perdu dans la ville de **{cap}**, dans quel pays se trouve cette ville ?"
                                    ))
                                    em = discord.Embed(
                                        title=f"{emoji} La Grande distribution • Problème de livraison",
                                        description=text, color=emcolor)
                                    em.set_footer(
                                        text="» Répondez à la question ci-dessous pour tenter d'obtenir un cadeau lvl. 3")
                                else:
                                    guess = cap
                                    text = random.choice((
                                        f"Un lutin est perdu : il est seulement marqué *\"Capitale de **{pays}**\"* sur le carton. Retrouvez le nom de la capitale !",
                                        f"La carte n'est plus à jour, quelle est la capitale de **{pays}** déjà ?",
                                        f"Un colis perdu de **{pays}** a été retrouvé à sa capitale. Retrouvez le nom de la capitale pour qu'il arrive à bonne destination !"
                                    ))
                                    em = discord.Embed(
                                        title=f"{emoji} La Grande distribution • Problème de livraison",
                                        description=text, color=emcolor)
                                    em.set_footer(
                                        text="» Répondez à la question ci-dessous pour tenter d'obtenir un cadeau lvl. 3")

                                spawn = await spawn_channel.send(embed=em)

                                async def check(msg: discord.Message):
                                    return not msg.author.bot and self.normalize(message.content) == self.normalize(
                                        guess) and await self.user_team(msg.author)

                                try:
                                    resp = await self.bot.wait_for("message", check=check, timeout=30)
                                except asyncio.TimeoutError:
                                    await spawn.delete()
                                    return

                                userteam = await self.user_team(resp.author)
                                userscore = await self.config.member(resp.author).user_score() + 30
                                await self.config.member(resp.author).user_score.set(userscore)
                                await self.add_team_gift(guild, userteam, gift)
                                team = await self.get_team(guild, userteam)
                                wintxt = random.choice((
                                    f"{resp.author.mention} a obtenu {gift} pour son équipe *{team['name']}* !",
                                    f"Bravo à {resp.author.mention} qui permet à *{team['name']}* d'obtenir {gift} !"
                                ))
                                post_em = discord.Embed(
                                    title=f"{emoji} La Grande distribution • Problème de livraison résolu",
                                    description=wintxt, color=emcolor)
                                post_em.set_footer(text="INFO · " + random.choice(ASTUCES))
                                await spawn.edit(embed=post_em)
                                await spawn.delete(delay=15)
                            cache["idle"] = False

                elif not cache["idle"] and not cache["traveling"]:
                    await self.next_location(guild)

    # COMMANDES <<<<<<<<<<<<<<<<<<<<<<<<

    @commands.command(name="livrer", aliases=["deliver"])
    @commands.cooldown(1, 30, commands.BucketType.member)
    @commands.guild_only()
    async def deliver_gift(self, ctx, *nom):
        """Livrer un cadeau dans la destination en cours

        Vous devez donner le nom / description (même vague) du cadeau à livrer

        Permission(s) nécessaire(s) : `livraisons`"""
        author = ctx.author
        guild = ctx.guild
        pos = await self.current_position(guild)
        if pos:
            if nom:
                teamname = await self.user_team(author)
                nom = " ".join(nom).lower()
                if teamname:
                    if await self.check_perms(author, ["livraisons"]):
                        guess = self.guess_gift(nom)
                        if guess:
                            dest_gifts = await self.get_dest_gifts(guild, teamname, pos)
                            gift = [g for g in dest_gifts if g.name.lower() == guess]
                            if gift:
                                team = await self.get_team(guild, teamname)
                                user = await self.get_user(author)
                                g = gift[0]
                                await self.remove_team_gift(guild, teamname, g)
                                rdn = random.choice((
                                    f"{g} a été livré avec succès.",
                                    f"Vous avez livré {g} avec succès.",
                                    f"Bien joué, vous avez livré {g} sans encombres."
                                ))
                                if len(gift) > 1:
                                    rdn += "\n**Note :** Vous avez un autre cadeau identique à livrer dans cette ville."
                                em = discord.Embed(description=rdn, color=team["color"])
                                team_pts = random.randint(*_GIFTS_PTS[gift[0].lvl])
                                pers_pts = int(team_pts / 3)
                                team["team_score"] += team_pts
                                await self.config.guild(guild).teams.set_raw(teamname, team)
                                new_score = user["user_score"] + pers_pts
                                await self.config.member(author).user_score.set(new_score)
                                em.set_footer(text=f"Team : +{team_pts} pts | {author.name} : +{pers_pts} pts")
                                await ctx.send(embed=em)
                            else:
                                await ctx.send(f"**Cadeau invalide** • *{guess}* n'est pas à livrer ici.")
                        else:
                            await ctx.send(f"**Permissions manquantes** • Il vous manque la permission `livraisons` pour faire cette action !")
                    else:
                        await ctx.send(f"**Cadeau inconnu** • Donnez le nom de votre cadeau pour le livrer (même vaguement)")
                else:
                    await ctx.send(f"**Aucune team** • Vous n'êtes dans aucune team.")
            else:
                await ctx.send(f"**Aucun nom donné** • N'avez-vous aucun cadeau à livrer à **{pos[0]}** ({pos[1]}) ?")
        else:
            await ctx.send(f"**Localisation inconnue** • Nous sommes en plein voyage ou en pause. Attendez que nous "
                           f"soyons arrivés à destination avant de pouvoir livrer vos cadeaux !")

    @commands.command(name="travel", aliases=["pos"])
    @commands.guild_only()
    async def info_travel(self, ctx):
        """Donne des informations sur notre voyage"""
        guild = ctx.guild
        travel = await self.get_travel(guild)
        if travel:
            txt = ""
            n = 1
            for p in travel[1:]:
                txt += f"{n}. {p[0]} – {p[1]}\n"
                n += 1

            desc = "**Status** · "
            pos = await self.current_position(guild)
            if not pos:
                desc += random.choice(("*Actuellement en voyage...*", "*Dans les airs...*",
                                       "*Nulle part...*", "*Dans le traineau...*"))
                desc += "\n"
            else:
                desc += f"*{pos[0]}*, {pos[1]}\n"
            color = XMAS_COLORS()
            em = discord.Embed(title="Informations sur notre voyage", description=desc, color=color)
            em.add_field(name="Prochaines destinations", value=txt, inline=False)
            await ctx.send(embed=em)
        else:
            await ctx.send(f"**Aucune destination** • Nous sommes à l'arrêt, le jeu a été arrêté.")

    @commands.command(name="top")
    @commands.guild_only()
    async def top_teams(self, ctx):
        """Affiche le top des teams de l'event Xmas"""
        guild = ctx.guild
        teams = await self.config.guild(guild).teams()
        tp = []
        for t in teams:
            pts_team = teams[t]["team_score"]
            pts_members = await self.team_users_score(guild, t)
            total = pts_team + pts_members
            tp.append((t, total, pts_members))
        top = sorted(tp, key=operator.itemgetter(1), reverse=True)
        em = discord.Embed(title="Classement des teams XMas", color=XMAS_COLORS())
        n = 1
        for name, score, fmem in top:
            team = await self.get_team(guild, name)
            em.add_field(name=f"{n}. {team['name']}", value=f"**Score** · {score} pts\n"
                                                            f"- ***Dont provenant des membres*** · {fmem} pts")
        await ctx.send(embed=em)

    @commands.group(name="team")
    @commands.guild_only()
    async def _team_command(self, ctx):
        """Commandes concernant sa team Xmas"""

    @_team_command.command(name="info")
    async def team_info(self, ctx):
        """Affiche les infos importantes sur sa team XMas"""
        guild = ctx.guild
        teamname = await self.user_team(ctx.author)
        if teamname:
            team = await self.get_team(guild, teamname)
            em = discord.Embed(title=f"Infos Team » {team['name']} ({teamname.upper()})", color=team["color"])
            chef = guild.get_member(team["leader"])
            nb = len(team["users"])
            txt = f"**Leader** · {chef.mention}\n" \
                  f"**Nombre de membres** · {nb}"
            em.description = txt
            pts_team = team["team_score"]
            pts_members = await self.team_users_score(guild, teamname)
            total = pts_team + pts_members
            scoretxt = f"```py\n" \
                       f"Points de la team : {pts_team}\n" \
                       f"Points des membres : {pts_members}\n" \
                       f"-------------\n" \
                       f"Total : {total} pts```"
            em.add_field(name="Score", value=scoretxt)
            await ctx.send(embed=em)
        else:
            await ctx.send("**Aucune team** • Vous n'avez pas de team")

    @_team_command.command(name="user")
    async def team_user_info(self, ctx, user: discord.Member = None):
        """Affiche ses propres infos ou ceux d'un autre membre du serveur"""
        user = user if user else ctx.author
        teamname = await self.user_team(user)
        txt = ""
        tips = ""
        if teamname:
            team = await self.get_team(ctx.guild, teamname)
            txt += f"**Team** · *{team['name']}*\n"
        else:
            txt += "**Team** · *Aucune*\n"
            tips = "Pour rejoindre une team, demandez à un leader de vous ajouter à sa team"
        userdata = await self.get_user(user)
        score = userdata["user_score"] if userdata["user_score"] else 0
        txt += f"**Score personnel** · {score} pts\n"
        txt += "**Succès** · ~~Aucun (à venir)~~"
        # TODO : Ajouter les succès personnels
        em = discord.Embed(title="Profil personnel", description=txt, color=user.color)
        em.set_author(name=str(user), icon_url=user.avatar_url)
        user_perms = await self.fetch_team_member(user)
        if user_perms:
            perms = " ".join([f"`{p}`" for p in user_perms])
        else:
            perms = "Aucune permission"
        em.add_field(name="Permissions", value=perms)
        if tips:
            em.set_footer(text=tips)
        await ctx.send(embed=em)

    @_team_command.command(name="quit")
    async def team_quit(self, ctx):
        """Quitter sa team"""
        teamname = await self.user_team(ctx.author)
        if teamname:
            team = await self.get_team(ctx.guild, teamname)
            if ctx.author.id != team["leader"]:
                options_txt = "Quitter votre team vous empêche de participer au jeu mais cela vous permet d'être engagé " \
                              "par une autre team. Sachez que vous conservez votre score personnel (qui est donc soustrait" \
                              " du score total de votre ancienne team). Ce score peut être un atout majeur pour rejoindre " \
                              "une autre team qui récupèrera celui-ci dans ses comptes.\n\n"
                options_txt += f"✅ · Quitter la team *{team['name']}*\n" \
                              "❎ · Annuler"
                em = discord.Embed(title=f"Êtes-vous sûr de vouloir quitter votre team ?",
                                   description=options_txt, color=team["color"])
                em.set_footer(text="⚠️Sans team vous ne pouvez pas participer au jeu")
                msg = await ctx.send(embed=em)
                emojis = ["✅", "❎"]

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

                if emoji != "✅":
                    await msg.delete()
                    return
                else:
                    await msg.delete()

                del team["users"][str(user.id)]
                await self.config.guild(ctx.guild).teams.set_raw(teamname, value=team)
                await ctx.send(
                    f"**Membre retiré** » {user.mention} a quitté son ancienne team ***{team['name']}***")
            else:
                await ctx.send(
                    f"**Impossible** • Etant donné que vous êtes leader, vous devez d'abord demander à un administrateur de changer le leader de votre équipe")
        else:
            await ctx.send(
                f"**Erreur** • Vous n'avez pas de team à quitter")

    @_team_command.command(name="stock", aliases=["inv"])
    async def team_stock(self, ctx):
        """Consulter l'inventaire de votre team"""
        guild = ctx.guild
        teamname = await self.user_team(ctx.author)
        if teamname:
            team = await self.get_team(guild, teamname)
            if team["stock"]:
                em = discord.Embed(title=f"🎁 Inventaire Team » {team['name']}", color=team["color"],
                                   timestamp=ctx.message.created_at)
                travel = await self.get_travel(guild)
                for dest in travel:
                    gifts = await self.get_dest_gifts(guild, team, dest)
                    if gifts:
                        txt = ""
                        for g in gifts:
                            txt += f"- {g}\n"
                    else:
                        txt = "Aucun"
                    em.add_field(name=f"{dest[0]}, {dest[1]}", value=txt)
                em.set_footer(text="Livrez ces cadeaux à bonne destination !")
                await ctx.send(embed=em)
            else:
                await ctx.send("**Inventaire vide** • Il n'y a rien à livrer")
        else:
            await ctx.send("**Aucune team** • Vous n'avez pas de team")

    @_team_command.group(name="admin")
    async def _team_admin(self, ctx):
        """Commandes d'administration de la team (Leader et membres ayant la permission)

        Lisez les permissions nécessaires en bas de l'aide de chaque commande (utiliser `;help team admin X`)"""

    @_team_admin.command(name="add")
    async def add_team_member(self, ctx, user: discord.Member):
        """Ajouter un membre à son équipe

        Permission(s) nécéssaire(s) : `gerer_membres`"""
        guild = ctx.guild
        if user != ctx.author:
            teamname = await self.user_team(ctx.author)
            if teamname:
                team = await self.get_team(guild, teamname)
                if await self.check_perms(ctx.author, ["gerer_membres"]):
                    if not await self.user_team(user):
                        team["users"][str(user.id)] = ["livraisons"]
                        await self.config.guild(guild).teams.set_raw(teamname, value=team)
                        await ctx.send(f"**Membre ajouté** » {user.mention} est désormais dans la team ***{team['name']}***\n"
                                       f"Si vous voulez lui ajouter des permissions, utilisez `;team admin perms`")
                    else:
                        await ctx.send("**Impossible** • Ce membre est déjà dans une autre team")
                else:
                    await ctx.send("**Permissions manquantes** • Vous n'avez pas ces permissions, nécessaires pour réaliser l'action : `gerer_membres`")
            else:
                await ctx.send("**Erreur** • Vous n'avez pas de team")
        else:
            await ctx.send("**Erreur** • Vous ne pouvez pas réaliser d'actions sur vous-même")

    @_team_admin.command(name="remove")
    async def rem_team_member(self, ctx, user: discord.Member):
        """Retirer un membre de son équipe

        Permission(s) nécéssaire(s) : `gerer_membres`"""
        guild = ctx.guild
        if user != ctx.author:
            teamname = await self.user_team(ctx.author)
            if teamname:
                team = await self.get_team(guild, teamname)
                if await self.check_perms(ctx.author, ["gerer_membres"]):
                    if await self.user_team(user) == teamname:
                        del team["users"][str(user.id)]
                        await self.config.guild(guild).teams.set_raw(teamname, value=team)
                        await ctx.send(
                            f"**Membre retiré** » {user.mention} n'est plus dans la team ***{team['name']}***")
                    else:
                        await ctx.send("**Impossible** • Ce membre n'est pas dans votre team")
                else:
                    await ctx.send(
                        "**Permissions manquantes** • Vous n'avez pas ces permissions, nécessaires pour réaliser l'action : `gerer_membres`")
            else:
                await ctx.send("**Erreur** • Vous n'avez pas de team")
        else:
            await ctx.send("**Erreur** • Vous ne pouvez pas réaliser d'actions sur vous-même\n"
                           "Pour quitter la team, utilisez `;team quit`")

    @_team_admin.command(name="perms")
    async def perms_team_member(self, ctx, user: discord.Member, *perms):
        """Retirer un membre de son équipe

        Permission(s) nécéssaire(s) : `gerer_perms`

        __**Permissions disponibles**__
        - `gerer_membres` = permet d'ajouter et retirer des membres de sa team
        - `gerer_perms` = permet d'éditer les permissions de membres de sa team (donc utiliser cette commande)
        - `gerer_props` = permet d'éditer les propriétés (nom etc.) de la team
        - `livraisons` = permet de livrer les cadeaux (accordée par défaut)

        Note : le leader de la team n'a besoin d'aucune permissions pour effectuer toutes les actions"""
        guild = ctx.guild

        def perms_check(permissions: list):
            for p in permissions:
                if p not in ["gerer_membres", "gerer_perms", "gerer_props", "livraisons"]:
                    return p
            return False

        if user != ctx.author:
            teamname = await self.user_team(ctx.author)
            if teamname:
                team = await self.get_team(guild, teamname)
                if await self.check_perms(ctx.author, ["gerer_perms"]):
                    if await self.user_team(user) == teamname:
                        if perms:
                            check = perms_check(list(perms))
                            if not check:
                                team["users"][str(user.id)] = list(perms)
                                await self.config.guild(guild).teams.set_raw(teamname, value=team)
                                liste = " ".join([f"`{i}`" for i in perms])
                                await ctx.send(
                                    f"**Permissions modifiées** » {user.mention} possède désormais les permissions suivantes : {liste}")
                            else:
                                await ctx.send(f"**Erreur** • `{check}` n'est pas une permission valide\n"
                                               f"Consultez les permissions disponibles en faisant `;help team admin perms`")
                        else:
                            team["users"][str(user.id)] = []
                            await self.config.guild(guild).teams.set_raw(teamname, value=team)
                            await ctx.send(
                                f"**Permissions retirées** » {user.mention} n'a plus aucune permissions")
                    else:
                        await ctx.send("**Impossible** • Ce membre n'est pas dans votre team")
                else:
                    await ctx.send(
                        "**Permissions manquantes** • Vous n'avez pas ces permissions, nécessaires pour réaliser l'action : `gerer_membres`")
            else:
                await ctx.send("**Erreur** • Vous n'avez pas de team")
        else:
            await ctx.send("**Erreur** • Vous ne pouvez pas réaliser d'actions sur vous-même")

    @_team_admin.command(name="nom")
    @commands.cooldown(1, 60, commands.BucketType.member)
    async def edit_team_name(self, ctx, *nom):
        """Changer le nom de l'équipe

        Cette action ne peut être réalisée qu'une fois toutes les 12h
        Le nom doit être composé de max. 25 caractères

        Permission(s) nécéssaire(s) : `gerer_props`"""
        guild = ctx.guild
        teamname = await self.user_team(ctx.author)
        if teamname:
            team = await self.get_team(guild, teamname)
            if await self.check_perms(ctx.author, ["gerer_props"]):
                if nom:
                    nom = " ".join(nom)
                    if len(nom) <= 25:
                        if team["namechange"] + 43200 <= time.time():
                            team["namechange"] = time.time()
                            team["name"] = nom
                            await self.config.guild(guild).teams.set_raw(teamname, value=team)
                            await ctx.send(f"**Nom modifié** • Le nouveau nom sera **{nom}**")
                        else:
                            await ctx.send(f"**Cooldown** • Vous avez déjà changé le nom il y a moins de 12h")
                    else:
                        await ctx.send(f"**Nom invalide** • Il doit pas faire plus de 25 caractères (espaces compris)")
                else:
                    await ctx.send(f"**Nom invalide** • Vous n'avez entré aucun nom")
            else:
                await ctx.send(f"**Permissions manquantes** • Vous n'avez pas la permission `gerer_props`")
        else:
            await ctx.send(f"**Aucune team** • Vous n'êtes dans aucune team")

    @commands.group(name="xmasset")
    @checks.admin_or_permissions(manage_messages=True)
    async def _xmas_set(self, ctx):
        """Paramètres de Xmas"""

    @_xmas_set.command()
    async def spawnchannel(self, ctx, channel: discord.TextChannel = None):
        """Définit le salon où apparaissent les cadeaux

        Si aucun salon de notification n'est dédié, ce salon sera aussi celui des notifications"""
        guild = ctx.guild
        if channel:
            await self.config.guild(guild).spawn_channel.set(channel.id)
            await ctx.send(f"**Salon modifié** • Le salon {channel.mention} sera celui où apparaitra les cadeaux (et les notifs. si non spécifié)")
        else:
            await self.config.guild(guild).spawn_channel.set(None)
            await ctx.send(f"**Salon retiré** • Le jeu est désactivé.")

    @_xmas_set.command()
    async def notifchannel(self, ctx, channel: discord.TextChannel = None):
        """Définit un salon séparé de celui de spawn pour les notifications"""
        guild = ctx.guild
        if channel:
            await self.config.guild(guild).notif_channel.set(channel.id)
            await ctx.send(
                f"**Salon modifié** • Le salon {channel.mention} sera celui des notifications.")
        else:
            await self.config.guild(guild).notif_channel.set(None)
            await ctx.send(f"**Salon retiré** • Le salon des notifications sera par défaut le même que pour le spawn des cadeaux.")

    @_xmas_set.command(name="valedit")
    async def edit_value(self, ctx, valname: str, val: int):
        """Modifier une valeur (seulement les int) des paramètres XMas du serveur"""
        guild = ctx.guild
        params = await self.config.guild(guild).all()
        if valname in params:
            if type(params[valname]) == int:
                params[valname] = val
                await self.config.guild(guild).set(params)
                await ctx.send(f"**Valeur modifiée** • `{valname}` » `{val}`")
            else:
                await ctx.send("**Valeur non-modifiable** • Cette valeur est trop complexe pour être modifiée avec cette commande")
        else:
            await ctx.send("**Valeur inconnue** • Ce nom de valeur n'existe pas")

    @_xmas_set.command(name="stoptravel")
    async def stop_travel(self, ctx):
        """Arrête de force le voyage s'il est en cours sur le serveur"""
        guild = ctx.guild
        cache = self.get_cache(guild)
        if cache["traveling"]:
            cache["traveling"] = False
            await ctx.send("**Voyage arrêté** • Celui-ci devrait s'arrêter d'un moment à l'autre...")
        else:
            await ctx.send("**Impossible** • vous n'êtes pas actuellement en train de voyager")

    @_xmas_set.command(name="teamleader")
    async def edit_team_leader(self, ctx, teamid: str, user: discord.Member):
        """Modifier le leader d'une team"""
        guild = ctx.guild
        team = await self.get_team(guild, teamid)
        if team:
            if not await self.user_team(user) or await self.user_team(user) == teamid:
                team["users"][str(user.id)] = ["gerer_membres", "gerer_props", "gerer_perms", "livraisons"]
                if team["leader"]:
                    old_leader = team["leader"]
                    team["users"][str(old_leader)] = ["livraisons"]
                team["leader"] = int(user.id)
                await self.config.guild(guild).teams.set_raw(teamid, value=team)
                await ctx.send(f"**Leader modifié** » {user.mention} est désormais le nouveau leader de la team ***{team['name']}***\n"
                               f"Il n'a besoin d'aucune permission pour réaliser toutes les actions nécessaires à sa "
                               f"team dont le recrutement de membres. Il peut déléguer certains pouvoirs avec la "
                               f"commande d'édition des permissions `;team admin perms`")
            else:
                await ctx.send("**Impossible** • Ce membre est déjà dans une team différente de celle visée")
        else:
            await ctx.send("**Erreur** • Cette team n'existe pas")

    @_xmas_set.command(name="resetteam")
    async def reset_team(self, ctx, teamid: str):
        """Reset les données d'une team

        Mettre 'all' reset les données de toutes les teams"""
        guild = ctx.guild
        if teamid != "all":
            team = await self.get_team(guild, teamid)
            if team:
                await self.config.guild(guild).clear_raw("teams", teamid)
                await ctx.send("**Reset effectué**")
            else:
                await ctx.send("**Team inconnue** • Cet identifiant de team n'existe pas")
        else:
            await self.config.guild(guild).clear_raw("teams")
            await ctx.send("**Reset total effectué**")