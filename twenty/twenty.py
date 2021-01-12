import asyncio
import os
from copy import copy
import logging
import random
import webcolors
from colorthief import ColorThief

import discord
from discord.utils import get as discord_get
from redbot.core import Config, commands, checks
from redbot.core.data_manager import cog_data_path

logger = logging.getLogger("red.AwsmCogs.twenty")

class Twenty(commands.Cog):
    """Votre résumé de l'année 2020"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=736144321857978388, force_registration=True)

        default_guild = {}
        self.config.register_guild(**default_guild)


