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

class XRole(commands.Cog):
    """Gestionnaire avancé de rôles"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=736144321857978388, force_registration=True)

        default_guild = {}
        self.config.register_guild(**default_guild)

    @commands.command(name="iam", aliases=["iamnot"])
    async def manage_selfroles(self, ctx, role: discord.Role = None):
        """Ajouter/retirer un rôle auto-attribuable

        Affiche un menu de sélection si aucun rôle n'est rentré"""

    @commands.group(name="xrole")
    async def manage_xrole(self, ctx):
        """Commandes de gestion des rôles auto-attribuables"""

    @manage_xrole.command(name="add")
    async def add_selfrole(self, ctx, role: discord.Role = None):
        """Ajouter un rôle auto-attribuable

        Donne une liste des rôles auto-attribuables si aucun rôle n'est précisé"""

    @manage_xrole.command(name="del")
    async def del_selfrole(self, ctx, role: discord.Role = None):
        """Retirer un rôle auto-attribuable

        Donne une liste des rôles auto-attribuables si aucun rôle n'est précisé"""




