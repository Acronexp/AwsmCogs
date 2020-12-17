import asyncio
import time
from collections import namedtuple
from copy import copy
import logging
import random
from datetime import datetime

import discord
from discord.utils import get as discord_get
from redbot.core import Config, commands, checks

logger = logging.getLogger("red.AwsmCogs.justice")


class JusticeError(Exception):
    pass


class InvalidJailRegister(JusticeError):
    pass


class Justice(commands.Cog):
    """Commandes avancées de modération"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=736144321857978388, force_registration=True)

        default_guild = {"jail": {"active": True,
                                  "role": None,
                                  "channels": [],
                                  "reactions_allowed": True,
                                  "default_time": 300}}
        self.config.register_guild(**default_guild)
        self.cache = {}

    def get_cache(self, guild: discord.Guild):
        if guild.id not in self.cache:
            self.cache[guild.id] = {"users": {},
                                    "loop": [],
                                    "save": {}}
        return self.cache[guild.id]

    async def check_jail_role_perms(self, role: discord.Role):
        guild = role.guild
        params = await self.config.guild(guild).jail()
        if params["reactions_allowed"]:
            to_apply = discord.Permissions(read_messages=True, view_channel=True, send_messages=False)
        else:
            to_apply = discord.Permissions(read_messages=True, view_channel=True, send_messages=False,
                                                   add_reactions=False)
        await role.edit(permissions=to_apply, reason="Vérif. permissions de rôle")

    async def user_jail(self, user: discord.Member):
        guild = user.guild
        cache = self.get_cache(guild)
        opt = await self.config.guild(guild).jail()
        if opt["role"]:
            role = guild.get_role(opt["role"])
            if role in user.roles:
                if user.id in cache["users"]:
                    return cache["users"][user.id]
                return True
        return False

    def parse_params(self, params: list):
        convtable = {"j": 86400, "h": 3600, "m": 60, "s": 1}
        parsed = {}
        other = []
        for p in params:
            time = False
            if params.startswith("+"):
                params = params.replace("+", "", 1).rstrip()
                parsed["ope"] = "add"
                time = True
            elif params.startswith("-"):
                params = params.replace("-", "", 1).rstrip()
                parsed["ope"] = "rem"
                time = True
            elif params.isdigit():
                parsed["ope"] = "set"
                time = True
            if time and not parsed.get("time", False):
                try:
                    form = params[-1]
                    val = int(params[:-1])
                    parsed["time"] = val * convtable[form]
                except:
                    pass
            elif p.lower() == "??":
                parsed["info"] = True
            else:
                other.append(p)
        if other:
            parsed["reason"] = " ".join(other)
        return parsed

    def humanize_time(self, val: int):
        """Converti automatiquement les secondes en unités plus pratiques"""
        j = h = m = 0
        while val >= 60:
            m += 1
            val -= 60
            if m == 60:
                h += 1
                m = 0
                if h == 24:
                    j += 1
                    h = 0
        txt = ""
        if j: txt += str(j) + "J "
        if h: txt += str(h) + "h "
        if m: txt += str(m) + "m "
        if val > 0: txt += str(val) + "s"
        TimeConv = namedtuple('TimeConv', ['jours', 'heures', 'minutes', 'secondes', 'string'])
        return TimeConv(j, h, m, val, txt if txt else "< 1s")

    async def register_jail(self, user: discord.Member, sec: int):
        guild = user.guild
        cache = self.get_cache(guild)
        if sec > 1:
            if user.id not in cache["users"]:
                cache["users"][user.id] = time.time() + sec
                return cache["users"][user.id]
            raise InvalidJailRegister(f"La mise en prison de {user.name} est invalide car il est déjà dans mes registres")
        else:
            raise InvalidJailRegister(
                f"La mise en prison de {user.name} est invalide car le temps de prison est inférieur à une seconde")

    async def unregister_jail(self, user: discord.Member):
        guild = user.guild
        cache = self.get_cache(guild)
        if user.id in cache["users"]:
            del cache["users"][user.id]
            return True
        return False  # S'il n'est pas dans les registres c'est pas grave

    async def edit_jail_time(self, user: discord.Member, value: int):
        guild = user.guild
        cache = self.get_cache(guild)
        if user.id in cache["users"]:
            cache["users"][user.id] = cache["users"][user.id] + value
            return cache["users"][user.id]
        raise InvalidJailRegister(
            f"{user.name} n'est pas dans mes registres et je ne peux donc pas l'éditer")

    async def auto_jail_loop(self, user: discord.Member):
        guild = user.guild
        opt = await self.config.guild(guild).jail()
        cache = self.get_cache(guild)
        if user.id in cache["users"] and opt["role"]:
            role = guild.get_role(opt["role"])
            if user.id not in cache["loop"]:
                cache["loop"].append(user.id)
                try:
                    while time.time() < cache["users"][user.id] and role in user.roles:
                        await asyncio.sleep(1)
                except:
                    if user.id in cache["users"]:
                        if time.time() < cache["users"][user.id]:
                            cache["save"][user.id] = cache["users"][user.id] - time.time()
                cache["loop"].remove(user.id)
                if user:
                    if type(await self.user_jail(user)) != bool:
                        await self.unregister_jail(user)
                    if role in user.roles:
                        await user.remove_roles(role, reason=f"Sortie auto. de prison")
                        msg = random.choice((
                            f"{user.mention} est désormais libre",
                            f"{user.mention} goûte de nouveau à la liberté",
                            f"{user.mention} a purgé sa peine",
                            f"{user.mention} a terminé son temps de prison",
                            f"{user.mention} est de nouveau libre"
                        ))
                        return msg
                    else:
                        msg = random.choice((
                            f"{user.mention} a été manuellement libéré",
                            f"Sortie de {user.mention} manuelle",
                            f"{user.mention} a perdu son rôle de prisonnier pendant sa peine"
                        ))
                        return msg
                else:
                    if user.id in cache["users"]:
                        del cache["users"][user.id]
                    return f"{user.mention} a quitté le serveur avant d'avoir fini sa peine"
        else:
            return False

    async def get_prefix(self, message: discord.Message) -> str:
        content = message.content
        prefix_list = await self.bot.command_prefix(self.bot, message)
        prefixes = sorted(prefix_list, key=lambda pfx: len(pfx), reverse=True)
        for p in prefixes:
            if content.startswith(p):
                return p
        return "n."

    @commands.command(name="prison", aliases=["p"])
    @checks.admin_or_permissions(manage_messages=True)
    async def manage_jail(self, ctx, user: discord.Member = None, *params):
        """Ajouter/retirer des membres de la prison"""
        guild = ctx.guild
        opt = await self.config.guild(guild).jail()
        mod = ctx.author
        moddisc = str(mod)
        color = await self.bot.get_embed_color(ctx.channel)

        if user.id == self.bot.user.id:
            rand = random.choice(("Il est hors de question que je me mette moi-même en prison ! 😭",
                                  "Non, vous ne pouvez pas me faire ça ! 😥",
                                  "Non mais ça ne va pas ? Et puis quoi encore ? 😡",
                                  "Bip boop, je ne peux pas faire ça, ça violerait les 3 lois de la robotique 🤖"))
            await ctx.send(rand)
            return

        if opt["role"]:
            jail_role = guild.get_role(opt["role"])

            async def notif(msg):
                em = discord.Embed(description=msg, color=color)
                await ctx.send(embed=em)

            if user:
                if not params:
                    userjail = await self.user_jail(user)
                    if userjail:
                        await self.unregister_jail(user)
                    else:
                        default_time = opt["default_time"]
                        await self.register_jail(user, default_time)
                        await user.add_roles(jail_role, reason=f"Envoyé en prison par {moddisc}")
                        human = self.humanize_time(default_time)
                        await notif(f"🔒 {user.mention} a été envoyé en prison par {mod.mention} pour {human.string}")
                        msg = await self.auto_jail_loop(user)
                        if msg:
                            await notif("🔓 " + msg)
                        else:
                            await notif("⚠️ Mise en prison impossible : rôle non configuré ou membre invalide")
                else:
                    userjail = await self.user_jail(user)
                    parsed = self.parse_params(list(params))
                    secs = parsed.get("time", opt["default_time"])
                    reason = parsed.get("reason", "N.R.")
                    if parsed.get("ope", None) == "add" and userjail:
                        await self.edit_jail_time(user, abs(secs))
                        human = self.humanize_time(secs)
                        await notif(f"🔏 Temps de prison de {user.mention} édité (+{human}) par {mod.mention}\n"
                                    f"Raison : {reason}")
                    elif parsed.get("ope", None) == "rem" and userjail:
                        await self.edit_jail_time(user, -secs)
                        human = self.humanize_time(secs)
                        await notif(f"🔏 Temps de prison de {user.mention} édité (-{human}) par {mod.mention}\n"
                                    f"Raison : {reason}")
                    elif parsed.get("ope", None) in ["add", "set"] and not userjail:
                        await self.register_jail(user, secs)
                        human = self.humanize_time(secs)
                        await user.add_roles(jail_role, reason=f"Envoyé en prison par {moddisc} | Raison : {reason}")
                        await notif(f"🔒 {user.mention} a été envoyé en prison par {mod.mention} pour {human.string}")
                        msg = await self.auto_jail_loop(user)
                        if msg:
                            await notif("🔓 " + msg)
                        else:
                            await notif("⚠️ Mise en prison impossible : rôle non configuré ou membre invalide")
                    elif userjail and reason != "N.R.":
                        await self.unregister_jail(user)
                    elif parsed.get("info", False):
                        jail = await self.user_jail(user)
                        if jail:
                            if type(jail) != bool:
                                libe = datetime.fromtimestamp(jail).strftime("le %d/%m/%Y à %H:%M")
                                txt = f"**Libération auto.** · Prévue {libe}"
                            else:
                                txt = f"**Libération auto.** · Aucune (emprisonné manuellement)"
                        else:
                            txt = f"Ce membre n'est pas emprisonné"
                        await notif(txt)
                    else:
                        txt = "• `s` pour les **secondes**\n" \
                              "• `m` pour les **minutes**\n" \
                              "• `h` pour les **heures**\n" \
                              "• `j` pour les **jours**\n" \
                              "Ces unités doivent être ajoutées après la valeur (ex. `;p @membre 3h`)"
                        em = discord.Embed(title="Aide » Formattage des paramètres de prison",
                                           description=txt, color=color)
                        return await ctx.send(embed=em)
            else:
                txt = "• `s` pour les **secondes**\n" \
                      "• `m` pour les **minutes**\n" \
                      "• `h` pour les **heures**\n" \
                      "• `j` pour les **jours**\n" \
                      "Ces unités doivent être ajoutées après la valeur (ex. `;p @membre 3h`)"
                em = discord.Embed(title="Aide » Formattage des paramètres de prison",
                                   description=txt, color=color)
                return await ctx.send(embed=em)
        else:
            await ctx.send("**Impossible** » Configurez d'abord un rôle de prisonnier")

    @commands.group(name="pset")
    @checks.admin_or_permissions(manage_messages=True)
    async def _jail_settings(self, ctx):
        """Paramètres de la prison"""

    @_jail_settings.command(name="toggle")
    async def jail_toggle(self, ctx):
        """Activer/désactiver la prison"""
        guild = ctx.guild
        jail = await self.config.guild(guild).jail()
        if jail["active"]:
            jail["active"] = False
            await ctx.send("**Prison désactivée** » Vous ne pouvez plus utiliser les commandes de la prison")
        else:
            jail["active"] = True
            await ctx.send("**Prison activée** » Vous pouvez désormais utiliser les commandes de prison (v. `;help Justice`)")
        await self.config.guild(guild).jail.set(jail)

    @_jail_settings.command(name="role")
    async def jail_role(self, ctx, role: discord.Role = None):
        """Définir le rôle de la prison

        Si aucun rôle n'est donné, celui-ci est créé automatiquement (si non déjà présent)"""
        guild = ctx.guild
        jail = await self.config.guild(guild).jail()
        if role:
            jail["role"] = role.id
            await ctx.send(f"**Rôle modifié** » Le rôle {role.mention} sera désormais utilisé pour la prison\n"
                           f"Faîtes `;pset check` pour régler automatiquement les permissions. "
                           f"Sachez que vous devez manuellement monter le rôle à sa place appropriée dans la hiérarchie.")
        else:
            maybe_role = discord_get(guild.roles, name="Prisonnier")
            if maybe_role:
                jail["role"] = maybe_role.id
                await ctx.send(f"**Rôle détecté** » Le rôle {maybe_role.mention} sera désormais utilisé pour la prison\n"
                               f"Faîtes `;pset check` pour régler automatiquement les permissions. "
                               f"Sachez que vous devez manuellement monter le rôle à sa place appropriée dans la hiérarchie.")
            else:
                role = await guild.create_role(name="Prisonnier", color=discord.Colour.default(),
                                               reason="Création auto. du rôle de prisonnier")
                jail["role"] = role.id
                await ctx.send(f"**Rôle créé** » Le rôle {role.mention} sera désormais utilisé pour la prison\n"
                               f"Faîtes `;pset check` pour régler automatiquement les permissions. "
                               f"Sachez que vous devez manuellement monter le rôle à sa place appropriée dans la hiérarchie.")
        await self.config.guild(guild).jail.set(jail)
        if jail["role"]:
            role = guild.get_role(jail["role"])
            await self.check_jail_role_perms(role)

    @_jail_settings.command(name="channels")
    async def jail_channels(self, ctx, *channels: discord.TextChannel):
        """Accorde un/des channel(s) écrits dans le(s)quel les prisonniers peuvent parler librement

        Régler un tel channel va faire en sorte de lock tous les autres salons du serveur pour le rôle de prisonnier
        Ne rien mettre retire ce salon des exceptions"""
        guild = ctx.guild
        jail = await self.config.guild(guild).jail()
        if channels:
            if jail["role"]:
                role = guild.get_role(jail["role"])
                await self.check_jail_role_perms(role)
                tb = ""
                chans = []
                for channel in channels:
                    overwrite = discord.PermissionOverwrite(send_messages=True, add_reactions=True, read_messages=True,
                                                            view_channel=True)
                    try:
                        await channel.set_permissions(role, overwrite=overwrite, reason="Réglage des permissions pour la prison")
                        tb += f"- {channel.mention}\n"
                        chans.append(channel.id)
                    except:
                        pass
                if tb:
                    await ctx.send("**Channels adaptés pour la prison :**\n" + tb)
                    await self.config.guild(guild).jail.set_raw("channels", value=chans)
                else:
                    await ctx.send("Aucun channel n'a été modifié (manques de permissions probablement).")
            else:
                await ctx.send("**Impossible** » Configurez d'abord un rôle de prisonnier avant de lui accorder des exceptions")
        elif jail["role"]:
            role = guild.get_role(jail["role"])
            for channel in guild.text_channels:
                await channel.set_permissions(role, overwrite=None)
            await ctx.send("**Channels retirés** » Plus aucun channel n'accorde d'exception aux prisonniers")
            await self.config.guild(guild).jail.clear_raw("channels")
        else:
            await ctx.send(
                "**Impossible** » Je n'ai pas de permissions à retirer si je n'ai pas de rôle cible (configurez un rôle prisonnier d'abord)")

    @_jail_settings.command(name="allowreact")
    async def jail_allow_reactions(self, ctx):
        """Accepte/refuse l'utilisation de réactions aux prisonniers"""
        guild = ctx.guild
        jail = await self.config.guild(guild).jail()
        if jail["reactions_allowed"]:
            jail["reactions_allowed"] = False
            await ctx.send("**Réactions refusées** » Les prisonniers ne pourront pas utiliser de réactions (sauf sur les channels d'exception)")
        else:
            jail["reactions_allowed"] = True
            await ctx.send(
                "**Réactions accordées** » Les prisonniers peuvent librement utiliser les réactions")
        await self.config.guild(guild).jail.set(jail)
        if jail["role"]:
            role = guild.get_role(jail["role"])
            await self.check_jail_role_perms(role)

    @_jail_settings.command(name="delay")
    async def jail_default_delay(self, ctx, val: int):
        """Règle le délai par défaut (en secondes) de la prison si aucune durée n'est spécifiée

        Doit être supérieure à 5 et inférieure à 86400 (1 jour)
        Par défaut 300s (5 minutes)"""
        guild = ctx.guild
        jail = await self.config.guild(guild).jail()
        if 5 <= val <= 86400:
            jail["default_time"] = val
            await ctx.send(
                f"**Délai modifié** » Par défaut les prisonniers seront emprisonnés {val} secondes")
            await self.config.guild(guild).jail.set(jail)
        else:
            await ctx.send(
                f"**Délai invalide** » La valeur du délai doit se situer entre 5 et 86400 secondes")

    @_jail_settings.command(name="check")
    async def jail_check_perms(self, ctx):
        """Vérifie auto. les permissions du rôle de prisonnier"""
        guild = ctx.guild
        jail = await self.config.guild(guild).jail()
        if jail["role"]:
            role = guild.get_role(jail["role"])
            await self.check_jail_role_perms(role)
            overwrite = discord.PermissionOverwrite(send_messages=True, add_reactions=True, read_messages=True,
                                                    view_channel=True)
            prisons = jail["channels"]
            allow_reactions = jail["reactions_allowed"]
            for channel in guild.text_channels:
                if channel.id in prisons:
                    try:
                        await channel.set_permissions(role, overwrite=overwrite,
                                                      reason="Réglage auto. des permissions pour la prison")
                    except Exception as e:
                        logger.error(e, exc_info=True)
                else:
                    try:
                        await channel.set_permissions(role, read_messages=True, send_messages=False,
                                                      add_reactions=allow_reactions)
                    except Exception as e:
                        logger.error(e, exc_info=True)
            await ctx.send("**Vérification terminée** » Les permissions du rôle ont été mis à jour en prenant en compte les exceptions des salons de prison")
        else:
            await ctx.send("**Vérification impossible** » Aucun rôle de prisonnier n'a été configuré")

