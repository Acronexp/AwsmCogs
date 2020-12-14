# Merci à Maglatranir#7175 qui a réalisé toute la partie sur l'extraction de la couleur dominante de la photo de profil

import os
from copy import copy
import logging
import webcolors
from colorthief import ColorThief

import discord
from discord.utils import get as discord_get
from redbot.core import Config, commands, checks
from redbot.core.data_manager import cog_data_path

logger = logging.getLogger("red.AwsmCogs.hex")


class HexError(Exception):
    pass


class AlreadySatisfied(HexError):
    pass


class InvalidCSSColor(HexError):
    pass


class InvalidHexString(HexError):
    pass


class Hex(commands.Cog):
    """Gestion auto. des rôles de couleurs sur les serveurs"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=736144321857978388, force_registration=True)

        default_guild = {"delimiter": None,
                         "autocolor_quality": 1,
                         "whitelist": False,
                         "whitelist_list": [],
                         "roles": {}}
        self.config.register_guild(**default_guild)

        self.temp = cog_data_path(self) / "temp"  # Pour stocker l'img de profil temporairement
        self.temp.mkdir(exist_ok=True, parents=True)

    async def get_color(self, guild: discord.Guild, color: str):
        """Crée la couleur si elle n'existe pas et le positionne correctement dans la liste si un délimiteur est donné

        Retourne le rôle créé ou à défaut le rôle déjà présent"""
        name = self.format_color(color, "#")
        role = discord_get(guild.roles, name=name)
        if not role:
            rolecolor = int(self.format_color(color, "0x"), base=16)
            role = await guild.create_role(name=name, color=discord.Colour(rolecolor),
                                    reason="Création auto. de rôle de couleur nécessaire", mentionable=False)
            await self.cache_color(guild, color)
            delim = await self.config.guild(guild).delimiter()
            if delim:
                delimpos = guild.get_role(delim).position
                setpos = delimpos - 1 if delimpos > 1 else 1
                await role.edit(position=setpos)
        return role

    async def clear_color(self, guild: discord.Guild, color: str):
        """Vérifie s'il y a encore des membres possédant la couleur et supprime le rôle ce n'est pas le cas"""
        name = self.format_color(color, "#")
        role = discord_get(guild.roles, name=name)
        if role:
            for u in guild.members:
                if role in u.roles:
                    return
            await role.delete(reason="Suppression auto. de rôle de couleur obsolète")
            await self.clear_cache_color(guild, color)
        return True

    async def clear_multiple_colors(self, guild: discord.Guild, colors: list):
        for color in colors:
            await self.clear_color(guild, color)
        return True

    async def cache_color(self, guild: discord.Guild, color: str):
        name = self.format_color(color, "#")
        if not name in await self.config.guild(guild).roles():
            rolecolor = self.format_color(color, "0x")
            await self.config.guild(guild).roles.set_raw(name, value=rolecolor)

    async def clear_cache_color(self, guild: discord.Guild, color: str):
        name = self.format_color(color, "#")
        if name in await self.config.guild(guild).roles():
            await self.config.guild(guild).roles.clear_raw(name)

    async def set_user_color(self, user: discord.Member, color: str, check_perms: bool = True):
        """Applique la nouvelle couleur au membre + crée le rôle si nécessaire + retire l'ancien rôle coloré s'il en possède un

        Renvoie le nouveau rôle possédé"""
        guild = user.guild
        all_colors = await self.config.guild(guild).roles()

        if self.format_color(color, "#") not in (r.name for r in user.roles):
            if check_perms and not await self.is_allowed(user):
                return False

            userroles = [r.name for r in user.roles]
            delroles = []
            for col in userroles:
                if col in all_colors:
                    role = discord_get(guild.roles, name=col)
                    delroles.append(role)
            await user.remove_roles(*delroles)
            await self.clear_multiple_colors(guild, [r.name for r in delroles])

            role = await self.get_color(guild, color)
            await user.add_roles(role, reason="Changement de rôle coloré")
            return role
        return discord_get(guild.roles, name=self.format_color(color, "#"))

    async def is_allowed(self, user: discord.Member):
        """Vérifie les permissions s'il y a une whitelist active"""
        guild = user.guild
        if await self.config.guild(guild).whitelist():
            liste = await self.config.guild(guild).whitelist_list()
            urolesid = [r.id for r in user.roles]
            if user.id not in liste and not [i for i in [urolesid] if i in liste] and \
                    not user.guild_permissions.manage_roles:
                return False
        return True

    def format_color(self, color: str, prefixe: str = None):
        """Vérifie que la couleur donnée est un hexadécimal et renvoie la couleur avec ou sans préfixe (0x ou #)"""
        color = color[-6:]
        try:
            int(color, base=16)
            return color.upper() if not prefixe else prefixe + color.upper()
        except ValueError:
            return False

    def css_name_hex(self, name: str):
        """Retrouve l'hex lié au nom de couleur (CSS3/HTML)"""
        try:
            hex = webcolors.name_to_hex(name)
            return self.format_color(hex, "0x")
        except:
            return False

    async def get_prefix(self, message: discord.Message) -> str:
        content = message.content
        prefix_list = await self.bot.command_prefix(self.bot, message)
        prefixes = sorted(prefix_list, key=lambda pfx: len(pfx), reverse=True)
        for p in prefixes:
            if content.startswith(p):
                return p
        return "n."

    @commands.command(name="color")
    @commands.guild_only()
    @commands.bot_has_guild_permissions(manage_roles=True, mention_everyone=True)
    async def set_color(self, ctx, couleur: str = None):
        """Changer manuellement votre rôle de couleur (format hexadécimal)

        Mettre "auto" à la place d'une couleur vous affecte la couleur dominante de votre avatar (v. ;autocolor)
        Affiche les couleurs déjà utilisées par d'autres membres du serveur si aucune couleur n'est donnée"""
        if couleur:
            async def exe(com: str):
                prefix = await self.get_prefix(ctx.message)
                msg = copy(ctx.message)
                msg.content = prefix + com
                return await self.bot.process_commands(msg)

            async with ctx.channel.typing():
                if couleur.lower() == "auto":  # de façon à ce que faire ";color auto" soit équivalent à ";autocolor"
                    await exe("autocolor")
                elif couleur.lower() in ("none", "remove", "rem"):  # idem avec ";remcolor"
                    await exe("remcolor")
                else:
                    if self.format_color(couleur):
                        couleur = self.format_color(couleur, "0x")
                    elif self.css_name_hex(couleur):
                        couleur = self.css_name_hex(couleur)
                    else:
                        return await ctx.send("**Couleur invalide** • La couleur donnée n'est ni une couleur en "
                                              "hexadécimal (ex. `#fefefe`) ni un nom de couleur sous la norme CSS3/HTML")

                    role = await self.set_user_color(ctx.author, couleur)
                    if role:
                        em = discord.Embed(description=f"Vous avez désormais la couleur **{role.name}**", color=role.color)
                        em.set_author(name=str(ctx.author), icon_url=ctx.author.avatar_url)
                        await ctx.send(embed=em)
                    else:
                        await ctx.send("**Impossible** • Vous n'êtes pas autorisé à utiliser cette commande (Whitelist)")
        else:
            all_roles = await self.config.guild(ctx.guild).roles()
            colors = []
            for r in all_roles:
                try:
                    colors.append(ctx.guild.get_role(r))
                except:
                    await self.clear_color(ctx.guild, all_roles[r])
            if colors:
                embed_color = await self.bot.get_embed_color(ctx.channel)

                async def send_embed(desc: str, pg: int):
                    emb = discord.Embed(title="Couleurs déjà utilisées sur ce serveur", description=desc,
                                        color=embed_color)
                    emb.set_footer(text=f"Page #{pg}")
                    await ctx.send(embed=emb)

                txt = ""
                page = 1
                for col in colors:
                    chunk = f"{col.mention}\n"
                    if len(txt) + len(chunk) < 2048:
                        txt += chunk
                    else:
                        await send_embed(txt, page)
                        page += 1
                        txt = ""
                if txt:
                    await send_embed(txt, page)
            else:
                await ctx.send("**Rien à afficher** • Personne n'utilise de couleur générée par ce bot")

    @commands.command(name="autocolor")
    @commands.guild_only()
    @commands.bot_has_guild_permissions(manage_roles=True)
    async def set_autocolor(self, ctx):
        """Détecte la couleur dominante de la photo de profil et applique le rôle coloré correspondant"""
        member = ctx.author
        path = str(self.temp)
        filename = path + "/avatar_{}.jpg".format(member.id)

        await member.avatar_url.save(filename)
        color_thief = ColorThief(filename)

        # Couleur dominante en tuple R V B
        qual = await self.config.guild(ctx.guild).autocolor_quality()
        dominant_color = color_thief.get_color(quality=qual)

        # Conversion R V B en hexa
        def rgb2hex(color):
            return f"#{''.join(f'{hex(c)[2:].upper():0>2}' for c in color)}"

        rolename = rgb2hex(dominant_color)
        try:
            newrole = await self.set_user_color(member, rolename)
            if newrole:
                em = discord.Embed(description=f"Vous avez désormais la couleur **{newrole.name}**", color=newrole.color)
                em.set_author(name=str(member), icon_url=member.avatar_url)
                await ctx.send(embed=em)
            else:
                await ctx.send(f"**Impossible** • Vous n'êtes pas autorisé à utiliser cette commande (Whitelist)")
        except Exception as e:
            await ctx.send(f"**Erreur** • {e}")
        os.remove(filename)

    @commands.command(name="remcolor", aliases=["removecolor"])
    @commands.guild_only()
    @commands.bot_has_guild_permissions(manage_roles=True)
    async def remove_color(self, ctx):
        """Retire votre rôle coloré

        Si vous avez plusieurs rôles colorés (?) cette commande les retire tous peu importe que vous êtes passés par le bot pour les mettre ou non"""
        user = ctx.author
        guild = ctx.guild
        userroles = [r.name for r in user.roles]
        all_colors = await self.config.guild(guild).roles()
        delroles = []
        for col in userroles:
            if col in all_colors:
                role = discord_get(guild.roles, name=col)
                delroles.append(role)
        if delroles:
            await user.remove_roles(*delroles, reason="Retrait du/des rôle(s) sur demande du membre")
            await self.clear_multiple_colors(guild, [i.name for i in delroles])
            await ctx.send("**Couleur(s) retirée(s)** • Vous n'avez plus aucun rôle coloré provenant du bot")
        else:
            await ctx.send("**Aucun rôle** • Aucun rôle coloré que vous possédez ne provient de ce bot")


    @commands.group(name="colorset")
    @commands.guild_only()
    @checks.admin_or_permissions(manage_roles=True)
    async def _color_settings(self, ctx):
        """Paramètres de Hex concernant les rôles colorés"""

    @_color_settings.command()
    async def delim(self, ctx, role: discord.Role = None):
        """Attribue le rôle de délimiteur à un rôle pour ranger auto. les rôles créés

        Les rôles créés seront automatiquement rangés sous le rôle délimiteur si celui-ci est défini
        Si le rôle donné est le même que celui enregistré précédemment, met à jour le positionnement des rôles"""
        guild = ctx.guild
        if role:
            if role.id != await self.config.guild(guild).delimiter():
                await self.config.guild(guild).delimiter.set(role.id)
                await ctx.send(
                        f"**Rôle délimiteur modifié** • Les rôles colorés se rangeront auto. sous ***{role.name}*** "
                        f"dans la liste de rôles lors de leur création")

            delimpos = role.position
            all_roles = await self.config.guild(guild).roles()
            for r in all_roles:
                check = discord_get(guild.roles, name=r)
                if check:
                    setpos = delimpos - 1 if delimpos > 1 else 1
                    await check.edit(position=setpos)
            await ctx.send(
                f"**Rôles rangés** • Les rôles ont été rangés conformément aux paramètres")

        else:
            await self.config.guild(guild).delimiter.set(None)
            await ctx.send(
                f"**Rôle délimiteur retiré** • Les rôles colorés ne se rangeront plus automatiquement (déconseillé)")

    @_color_settings.command(name="clear")
    async def clear_colors(self, ctx):
        """Lance manuellement une vérification et suppression des rôles de couleurs qui ne sont plus utilisés par personne"""
        guild = ctx.guild
        all_roles = await self.config.guild(guild).roles()
        count = 0
        for role in all_roles:
            await self.clear_color(guild, all_roles[role])
            count += 1
        await ctx.send(f"**Vérification terminée** • {count} rôles obsolètes ont été supprimés")

    @_color_settings.command(name="deleteall")
    async def deleteall_colors(self, ctx):
        """Supprime tous les rôles colorés créés par le bot"""
        guild = ctx.guild
        aut = str(ctx.author)
        all_roles = await self.config.guild(guild).roles()
        count = 0
        for r in all_roles:
            role = discord_get(guild.roles, name=r)
            if role:
                await role.delete(reason=f"Suppression du rôle sur demande de {aut}")
                count += 1
        await self.config.guild(guild).clear_raw("roles")
        await ctx.send(f"**Suppression réalisée** • {count} rôles ont été supprimés")

    @_color_settings.command(name="give")
    async def give_color(self, ctx, user: discord.Member, couleur: str):
        """Donne la couleur voulue au membre, même si celui-ci n'est pas autorisé à le faire lui-même"""
        if self.format_color(couleur):
            couleur = self.format_color(couleur, "#")
            role = await self.set_user_color(user, couleur, check_perms=False)
            if role:
                em = discord.Embed(description=f"{ctx.author.mention} a donné la couleur **{role.name}** à {user.mention}",
                                   color=role.color)
                em.set_author(name=str(ctx.author), icon_url=ctx.author.avatar_url)
                await ctx.send(embed=em)
            else:
                await ctx.send("**Erreur** • Impossible de lui donner cette couleur")

    @_color_settings.command(name="refresh")
    async def refresh_colors(self, ctx):
        """Rafraichit le cache des rôles manuellement si celui-ci est corrompu ou incomplet"""
        guild = ctx.guild
        count = 0
        await self.config.guild(guild).clear_raw("roles")
        for role in guild.roles:
            if role.name.startswith("#") and self.format_color(role.name):
                await self.cache_color(guild, role.name)
                count += 1
        await ctx.send(f"**Rafrachissement terminé** • {count} rôles ont été rajoutés au cache et sont maintenant considérés par le bot")


    @_color_settings.group(name="whitelist")
    async def _color_whitelist(self, ctx):
        """Gestion de la whitelist pour utiliser les commandes de rôles colorés"""

    @_color_whitelist.command(name="toggle")
    async def color_whitelist_toggle(self, ctx):
        """Active/désactive la whitelist d'utilisation des commandes de rôles colorés

        Si la whitelist est activée, seul les membres ou rôles whitelistés (+ les modos) pourront utiliser les commandes de rôles colorés"""
        guild = ctx.guild
        wl = await self.config.guild(guild).whitelist()
        if wl:
            await ctx.send(
                "**Whitelist désactivée** • Tout le monde pourra utiliser les commandes pour obtenir un rôle coloré.")
        else:
            await ctx.send(
                "**Whitelist activée** • Seuls les membres whitelistés ou les membres possédant un rôle whitelisté "
                "et les modos pourront utiliser les commandes de rôles colorés.")
        await self.config.guild(guild).whitelist.set(not wl)

    @_color_whitelist.command(name="adduser")
    async def color_whitelist_adduser(self, ctx, user: discord.Member):
        """Ajouter un membre à la whitelist"""
        guild = ctx.guild
        liste = await self.config.guild(guild).whitelist_list()
        if user.id not in liste:
            liste.append(user.id)
            await self.config.guild(guild).whitelist_list.set(liste)
            await ctx.send(
                f"**Membre ajouté** • **{user.name}** pourra utiliser les commandes de rôles colorés (si la whitelist est activée).")
        else:
            await ctx.send(
                f"**Membre déjà présent** • Ce membre est déjà dans la whitelist, utilisez `;colorset whitelist deluser` pour le retirer.")

    @_color_whitelist.command(name="deluser")
    async def color_whitelist_deluser(self, ctx, user: discord.Member):
        """Retirer un membre de la whitelist"""
        guild = ctx.guild
        liste = await self.config.guild(guild).whitelist_list()
        if user.id in liste:
            liste.remove(user.id)
            await self.config.guild(guild).whitelist_list.set(liste)
            await ctx.send(
                f"**Membre retiré** • **{user.name}** ne pourra plus utiliser les commandes de rôles colorés (si la whitelist est activée).")
        else:
            await ctx.send(
                f"**Membre absent** • Ce membre n'est pas dans la whitelist, utilisez `;colorset whitelist adduser` pour l'ajouter.")

    @_color_whitelist.command(name="addrole")
    async def color_whitelist_addrole(self, ctx, role: discord.Role):
        """Ajouter un rôle à la whitelist

        Tous les membres possédant ce rôle pourront utiliser les commandes"""
        guild = ctx.guild
        liste = await self.config.guild(guild).whitelist_list()
        if role.id not in liste:
            liste.append(role.id)
            await self.config.guild(guild).whitelist_list.set(liste)
            await ctx.send(
                f"**Rôle ajouté** • Les membres possédant **{role.name}** pourront utiliser les commandes de rôles colorés (si la whitelist est activée).")
        else:
            await ctx.send(
                f"**Rôle déjà présent** • Ce rôle est déjà whitelisté, utilisez `;colorset whitelist delrole` pour le retirer.")

    @_color_whitelist.command(name="delrole")
    async def color_whitelist_delrole(self, ctx, role: discord.Role):
        """Retirer un rôle de la whitelist"""
        guild = ctx.guild
        liste = await self.config.guild(guild).whitelist_list()
        if role.id in liste:
            liste.remove(role.id)
            await self.config.guild(guild).whitelist_list.set(liste)
            await ctx.send(
                f"**Rôle retiré** • Les membres possédant **{role.name}** ne pourront pas utiliser les commandes de rôles colorés (si la whitelist est activée).")
        else:
            await ctx.send(
                f"**Rôle absent** • Ce rôle n'est pas whitelisté, utilisez `;colorset whitelist addrole` pour l'ajouter.")

    @_color_whitelist.command(name="clear")
    async def color_whitelist_clear(self, ctx):
        """Efface toute la whitelist (membres et rôles)"""
        guild = ctx.guild
        await self.config.guild(guild).clear_raw("whitelist_list")
        await ctx.send(
            f"**Reset effectué** • La whitelist a été reset.")