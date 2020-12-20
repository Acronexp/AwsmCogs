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

logger = logging.getLogger("red.AwsmCogs.xrole")

_CONDITIONS = {
    "created" : "âge minimal du compte",
    "joined": "nb. min. de jours sur le serveur",
    "roles": "rôles nécessaires",
    "noroles": "rôles incompatibles"
}

class XRole(commands.Cog):
    """Gestionnaire avancé de rôles"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=736144321857978388, force_registration=True)

        default_guild = {"selfroles": {},
                         "random_on_member_join": []}
        self.config.register_guild(**default_guild)

    async def get_selfroles(self, guild: discord.Guild):
        data = await self.config.guild(guild).selfroles()
        if data:
            roles = [[data[i]["uses"], i] for i in data]
            roles = sorted(roles, key=operator.itemgetter(0), reverse=True)
            return [r[1] for r in roles]
        return []

    async def disp_selfroles(self, ctx):
        guild = ctx.guild
        color = await self.bot.get_embed_color(ctx.channel)
        liste = await self.get_selfroles(guild)
        update = False
        if liste:
            data = deepcopy(await self.config.guild(guild).selfroles())
            txt = ""
            for r in liste:
                try:
                    role = guild.get_role(int(r))
                except:
                    logger.info(f"Le rôle {r} était inaccessible et a donc été supprimé")
                    del data[r]
                    update = True
                    continue
                rdata = data[r]
                chunk = f"• **@{role.name}**"
                if role.mentionable:
                    chunk = f"• {role.mention}"

                if (c for c in list(_CONDITIONS.keys()) if c in rdata):
                    if rdata.get("created", False):
                        chunk += "\n   » **Âge min. du compte** = {}j".format(rdata["created"])
                    if rdata.get("joined", False):
                        chunk += "\n   » **Ancienneté min. du membre** = {}j".format(rdata["joined"])
                    if rdata.get("roles", False):
                        chunk += "\n   » **Rôles nécéssaires** = {}".format(", ".join([guild.get_role(int(i)).name for i in rdata["roles"]]))
                    if rdata.get("noroles", False):
                        chunk += "\n   » **Rôles incompatibles** = {}".format(", ".join([guild.get_role(int(i)).name for i in rdata["noroles"]]))

                chunk += "\n"
                if len(txt) + len(chunk) < 2000:
                    txt += chunk
                else:
                    em = discord.Embed(title="Liste des rôles auto-attribuables", description=txt, color=color)
                    await ctx.send(embed=em)
                    txt = ""
            if update:
                await self.config.guild(guild).selfroles.set(data)
            if txt:
                em = discord.Embed(title="Liste des rôles auto-attribuables", description=txt, color=color)
                return await ctx.send(embed=em)
        else:
            return await ctx.send("**Liste vide** • Il n'y a aucun rôle auto-attribuable configuré sur ce serveur")

    @commands.command(name="iam", aliases=["iamnot"])
    @commands.max_concurrency(1, commands.BucketType.member)
    async def manage_selfroles(self, ctx, role: discord.Role = None):
        """Ajouter/retirer un rôle auto-attribuable

        Affiche un menu de sélection si aucun rôle n'est rentré"""
        guild = ctx.guild
        data = await self.config.guild(guild).selfroles()
        if not data:
            return await ctx.send(f"**Aucun rôle** • Aucun rôle n'a été configuré pour être auto-attribuable sur ce serveur")
        color = await self.bot.get_embed_color(ctx.channel)
        if not role:
            nbs = []
            update = False
            msg = None
            n = 1
            liste = await self.get_selfroles(guild)
            txt = ""
            for r in liste:
                try:
                    found = guild.get_role(int(r))
                except:
                    logger.info(f"Le rôle {r} était inaccessible et a donc été supprimé")
                    del data[r]
                    update = True
                    continue
                if not found:
                    logger.info(f"Le rôle {r} était inaccessible et a donc été supprimé")
                    del data[r]
                    update = True
                    continue
                rdata = data[r]
                chunk = f"**{n}**. **@{found.name}**"
                if found.mentionable:
                    chunk = f"**{n}**. {found.mention}"

                if (c for c in list(_CONDITIONS.keys()) if c in rdata):
                    if rdata.get("created", False):
                        chunk += "\n   » **Âge min. du compte** = {}j".format(rdata["created"])
                    if rdata.get("joined", False):
                        chunk += "\n   » **Ancienneté min. du membre** = {}j".format(rdata["joined"])
                    if rdata.get("roles", False):
                        chunk += "\n   » **Rôles nécéssaires** = {}".format(
                            ", ".join([guild.get_role(int(i)).name for i in rdata["roles"]]))
                    if rdata.get("noroles", False):
                        chunk += "\n   » **Rôles incompatibles** = {}".format(
                            ", ".join([guild.get_role(int(i)).name for i in rdata["noroles"]]))

                chunk += "\n"
                nbs.append((n, found))
                n += 1
                if len(txt) + len(chunk) < 2000:
                    txt += chunk
                else:
                    em = discord.Embed(title="Rôles auto-attribuables", description=txt, color=color)
                    em.set_footer(text="Entrez le numéro du rôle ou \"aucun\" pour annuler")
                    msg = await ctx.send(embed=em)
                    txt = ""
            if update:
                await self.config.guild(guild).selfroles.set(data)
            if txt:
                em = discord.Embed(title="Rôles auto-attribuables", description=txt, color=color)
                em.set_footer(text="Entrez le numéro du rôle ou \"aucun\" pour annuler")
                msg = await ctx.send(embed=em)

            if msg:
                def check(msg: discord.Message):
                    return msg.author == ctx.author

                try:
                    resp = await self.bot.wait_for("message", check=check, timeout=60)
                except asyncio.TimeoutError:
                    return await msg.delete()

                if resp.content.isdigit():
                    await msg.delete()
                    nb = int(resp.content)
                    if nb in (i[0] for i in nbs):
                        role = [i[1] for i in nbs if i[0] == nb][0]
                    else:
                        role = None
                elif resp.content.lower() in ["non", "no", "aucun", "stop", "quitter", "quit"]:
                    await msg.delete()
                    return
                else:
                    role = None
            else:
                role = None

        if role:
            rid = str(role.id)
            if rid in data:
                if role in (r for r in ctx.author.roles):
                    await ctx.author.remove_roles(role, reason="Auto-retrait du rôle (;iam)")
                    data[rid]["uses"] -= 1
                    await ctx.send(f"**Rôle retiré** • Vous n'avez plus le rôle *{role.name}*")
                else:
                    await ctx.author.add_roles(role, reason="Auto-attribution du rôle (;iam)")
                    data[rid]["uses"] += 1
                    await ctx.send(f"**Rôle ajouté** • Vous avez désormais le rôle *{role.name}*")
                await self.config.guild(guild).selfroles.set(data)
            else:
                await ctx.send(f"**Rôle absent de la liste** • Ce rôle n'est pas auto-attribuable")
        else:
            await ctx.send(f"**Rôle inconnu** • Ce rôle n'existe pas ou n'est pas auto-attribuable")


    @commands.group(name="xrole")
    @checks.admin_or_permissions(manage_messages=True)
    async def manage_xrole(self, ctx):
        """Commandes de gestion des rôles auto-attribuables"""

    @manage_xrole.command(name="add")
    async def add_selfrole(self, ctx, role: discord.Role = None):
        """Ajouter un rôle auto-attribuable

        Donne une liste des rôles auto-attribuables si aucun rôle n'est précisé"""
        guild = ctx.guild
        if role:
            rid = str(role.id)
            data = await self.config.guild(guild).selfroles()
            if role.id not in data:
                data[rid] = {"uses": 0}
                await self.config.guild(guild).selfroles.set(data)
                await ctx.send(f"**Rôle ajouté** • Le rôle *{role.name}* a été ajouté avec succès aux rôles autto-attribuables.")
            else:
                await ctx.send(f"**Impossible** • Le rôle *{role.name}* est déjà présent dans la liste.")
        else:
            await self.disp_selfroles(ctx)

    @manage_xrole.command(name="del")
    async def del_selfrole(self, ctx, role: discord.Role = None):
        """Retirer un rôle auto-attribuable

        Donne une liste des rôles auto-attribuables si aucun rôle n'est précisé"""
        guild = ctx.guild
        if role:
            rid = str(role.id)
            data = await self.config.guild(guild).selfroles()
            if str(rid) in data:
                del data[rid]
                await self.config.guild(guild).selfroles.set(data)
                await ctx.send(f"**Rôle retiré** • Le rôle *{role.name}* a été retiré des rôles auto-attribuables.")
            else:
                await ctx.send(f"**Impossible** • Le rôle *{role.name}* n'est pas dans la liste.")
        else:
            await self.disp_selfroles(ctx)

    """@manage_xrole.command(name="edit")
    async def edit_selfrole(self, ctx, role: discord.Role):
        guild = ctx.guild
        return await ctx.send("**En construction** • L'édition des rôles (+ conditions) arrive dans une prochaine mise à jour !")
        data = await self.config.guild(guild).selfroles()
        em_color = await self.bot.get_embed_color(ctx.channel)
        if role.id in data:
            while True:
                rdata = data[role.id]

                options_txt = "➕ · Ajouter une condition\n" \
                              "➖ · Retirer une condition\n" \
                              "❌ · Quitter"
                emojis = ["➕", "➖", "❌"]
                infos = ""
                if (c for c in list(_CONDITIONS.keys()) if c in rdata):
                    if rdata.get("created", False):
                        infos += "» **Âge min. du compte** = {}j\n".format(rdata["created"])
                    if rdata.get("joined", False):
                        infos += "» **Ancienneté min. du membre** = {}j\n".format(rdata["joined"])
                    if rdata.get("roles", False):
                        infos += "» **Rôles nécéssaires** = {}\n".format(", ".join([guild.get_role(i).name for i in rdata["roles"]]))
                    if rdata.get("noroles", False):
                        infos += "» **Rôles incompatibles** = {}\n".format(", ".join([guild.get_role(i).name for i in rdata["noroles"]]))
                if not infos:
                    infos = "**Aucune condition d'obtention exigée**"
                    options_txt = "➕ · Ajouter une condition\n" \
                                  "➖ · ~~Retirer une condition~~\n" \
                                  "❌ · Quitter"
                    emojis = ["➕", "❌"]
                if len([r for r in rdata if r in list(_CONDITIONS.keys())]) == len(_CONDITIONS):
                    options_txt = "➕ · ~~Ajouter une condition~~\n" \
                                  "➖ · Retirer une condition\n" \
                                  "❌ · Quitter"
                    emojis = ["➖", "❌"]

                em = discord.Embed(title=f"Édition de rôle auto-attribuable • @{role.name}", description=infos,
                                   color=em_color)
                em.add_field(name="Options", value=options_txt, inline=False)
                em.set_footer(text="Cliquez sur la réaction correspondante à l'action voulue")
                msg = await ctx.send(embed=em)
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

                if emoji == "➕":
                    await msg.delete()
                    txt = ""
                    for cond in _CONDITIONS:
                        desc = _CONDITIONS[cond]
                        txt += f"- `{cond}` · *{desc}*\n"

                    em = discord.Embed(title=f"Édition de rôle auto-attribuable • @{role.name}", description=txt,
                                       color=em_color)
                    em.set_footer(text="Entrez le nom de la condition que vous voulez ajouter")
                    msg = await ctx.send(embed=em)

                    def check(msg: discord.Message):
                        return msg.author == ctx.author
                    try:
                        resp = await self.bot.wait_for("message", check=check, timeout=30)
                    except asyncio.TimeoutError:
                        await msg.delete()
                        continue

                    if resp.content.lower() in list(_CONDITIONS.keys()):
                        await msg.delete()
                        cond = resp.content.lower()

                        if cond in ("created", "joined"):
                            if cond == "created":
                                txt = "Quel doit être l'âge du compte Discord du membre pour qu'il obtienne ce rôle ?"
                            else:
                                txt = "Combien de jours le membre doit-il être resté sur ce serveur pour obtenir ce rôle ?"
                            em = discord.Embed(title=f"Édition de rôle auto-attribuable • @{role.name}",
                                               description=txt,
                                               color=em_color)
                            em.set_footer(text="Donnez le nombre de jours min. nécessaires")
                            msg = await ctx.send(embed=em)

                            def check(msg: discord.Message):
                                return msg.author == ctx.author

                            try:
                                resp = await self.bot.wait_for("message", check=check, timeout=20)
                            except asyncio.TimeoutError:
                                await msg.delete()
                                continue

                            if resp.content.isdigit():
                                nb = int(resp.content)
                                if nb > 0:
                                    pass"""

    @manage_xrole.command(name="randomrole")
    async def set_randomrole(self, ctx, *roles: discord.Role):
        """Configurer un ensemble de rôle qui seront attribués aléatoirement aux arrivants"""
        guild = ctx.guild
        if roles:
            liste = []
            txt = ""
            for r in roles:
                if r in guild.roles:
                    liste.append(r.id)
                    txt += f"- {r.mention}\n"
            if liste:
                await self.config.guild(guild).random_on_member_join.set(liste)
                em = discord.Embed(title="Rôles pouvant être attribués aléatoirement à l'arrivée", description=txt)
                await ctx.send(embed=em)
            else:
                await ctx.send("**Erreur** • Aucun rôle valide")
        else:
            await self.config.guild(guild).clear_raw("random_on_member_join")
            await ctx.send("**Fonctionnalité désactivée** • Le bot cessera de donner un rôle aléatoire à l'arrivée")

    @commands.Cog.listener()
    async def on_member_join(self, user):
        if user.guild:
            guild = user.guild
            if await self.config.guild(guild).random_on_member_join():
                roles = await self.config.guild(guild).random_on_member_join()
                try:
                    role = guild.get_role(random.choice(roles))
                    await user.add_roles(role, reason="Rôle attribué aléatoirement à l'arrivée")
                except:
                    pass

