# Merci à Maglatranir#7175 qui a réalisé toute la partie sur l'extraction de la couleur dominante de la photo de profil
import os
from datetime import datetime, timedelta
import logging
import random
import string
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


class Hex(commands.Cog):
    """Gestion auto. des rôles de couleurs sur les serveurs"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=736144321857978388, force_registration=True)

        default_guild = {"delimiter": None,
                         "roles": {}}
        self.config.register_guild(**default_guild)

        self.temp = cog_data_path(self) / "temp"  # Pour stocker l'img de profil temporairement
        self.temp.mkdir(exist_ok=True, parents=True)

    async def get_color(self, guild: discord.Guild, color: str):
        """Crée la couleur si elle n'existe pas et le positionne correctement dans la liste si un délimiteur est donné

        Retourne le rôle créé ou à défaut le rôle déjà présent"""
        name = color.replace("0x", "#")
        role = discord_get(guild.roles, name=name)
        if not role:
            rolecolor = int(color.replace("#", "0x"), base=16)
            role = await guild.create_role(name=name, color=discord.Colour(rolecolor),
                                    reason="Création auto. de rôle de couleur", mentionnable=False)
            await self.cache_color(guild, color)
            delim = await self.config.guild(guild).delimiter()
            if delim:
                delimpos = guild.get_role(delim).position
                setpos = delimpos - 1 if delimpos > 0 else 0
                await role.edit(position=setpos)
        return role

    async def clear_color(self, guild: discord.Guild, color: str):
        """Vérifie s'il y a encore des membres possédant la couleur et supprime le rôle ce n'est pas le cas"""
        name = color.replace("0x", "#")
        role = discord_get(guild.roles, name=name)
        if role:
            for u in guild.members:
                if role in u.roles:
                    return
            await role.delete(reason="Suppression auto. de rôle de couleur")
            await self.clear_cache_color(guild, color)
        else:
            raise AlreadySatisfied("Rôle non-existant")

    async def cache_color(self, guild: discord.Guild, color: str):
        name = color.replace("0x", "#")
        if not name in await self.config.guild(guild).roles():
            rolecolor = int(color.replace("#", "0x"), base=16)
            await self.config.guild(guild).roles.set_raw(name, value=rolecolor)

    async def clear_cache_color(self, guild: discord.Guild, color: str):
        name = color.replace("0x", "#")
        if name in await self.config.guild(guild).roles():
            await self.config.guild(guild).roles.clear_raw(name)

    async def set_user_color(self, user: discord.Member, color: str):
        """Applique la nouvelle couleur au membre + crée le rôle si nécessaire + retire l'ancien rôle coloré s'il en possède un

        Renvoie le nouveau rôle possédé"""
        guild = user.guild
        all_colors = await self.config.guild(guild).roles()
        for col in all_colors:  # Long mais au moins si le membre a plusieurs couleurs ça les supprime toutes
            if col in (r.name for r in user.roles):
                role = discord_get(guild.roles, name=col)
                await user.remove_roles(role)
                await self.clear_color(guild, col)

        role = await self.get_color(guild, color)
        await user.add_roles(role, reason="Changement de rôle coloré")
        return role

    @commands.command()
    @commands.bot_has_guild_permissions(manage_roles=True)
    async def color(self, ctx, couleur: str):
        """Change manuellement de rôle de couleur"""

    @commands.command()
    @commands.bot_has_guild_permissions(manage_roles=True)
    async def autocolor(self, ctx):
        """Détecte la couleur dominante de la photo de profil et applique le rôle coloré correspondant"""
        member = ctx.author
        path = str(self.temp)
        filename = path + "/avatar_{}.txt".format(member.id)

        await member.avatar_url.save(filename)
        color_thief = ColorThief(filename)

        # Couleur dominante en tuple R V B
        dominant_color = color_thief.get_color(quality=1)

        # Conversion R V B en hexa
        def rgb2hex(color):
            return f"#{''.join(f'{hex(c)[2:].upper():0>2}' for c in color)}"

        rolename = rgb2hex(dominant_color)
        try:
            newrole = await self.set_user_color(member, rolename)
            em = discord.Embed(description=f"Vous avez désormais la couleur {newrole.name}", color=newrole.color)
            em.set_author(name=str(member), icon_url=member.avatar_url)
            await ctx.send(embed=em)
        except Exception as e:
            await ctx.send(f"**Erreur** • {e}")
        os.remove(filename)
