import asyncio
import logging
import re

import discord
import os
import urllib.request

from redbot.core.data_manager import cog_data_path

from redbot.core import Config, commands, checks, errors


logger = logging.getLogger("red.AwsmCogs.contentcleaner")


class ContentCleaner(commands.Cog):
    """Ensemble de triggers automatiques corrigeant des liens et contenus"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=736144321857978388, force_registration=True)

        default_guild = {"vocaroo": False}
        self.config.register_guild(**default_guild)

        self.temp = cog_data_path(self) / "temp"
        self.temp.mkdir(exist_ok=True, parents=True)

    def get_vocaroo_mp3(self, url: str):
        key = url.split("/")[-1]
        source = f"https://media1.vocaroo.com/mp3/{key}"
        path = self.temp / f"vocaroo_{key}.mp3"
        try:
            urllib.request.urlretrieve(source, path)
        except:
            raise
        return path

    @commands.group(name="contentcleaner", aliases=["cc"])
    async def _content_cleaner(self, ctx):
        """Commandes de gestion des triggers de correction auto. de liens et contenus"""

    @_content_cleaner.command()
    async def vocaroo(self, ctx):
        """Activer/désactiver l'affichage auto. du MP3 des liens Vocaroo"""
        param = await self.config.guild(ctx.guild).vocaroo()
        if param:
            await ctx.send("**Désactivé** » Les MP3 Vocaroo ne seront plus affichés")
        else:
            await ctx.send("**Activé** » Les MP3 Vocaroo seront téléchargés et uploadés directement sur Discord")
        await self.config.guild(ctx.guild).vocaroo.set(not param)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild:
            guild = message.guild
            params = await self.config.guild(guild).all()
            if params["vocaroo"]:
                urls = re.compile(r'(https?://(?:vocaroo\.com|voca\.ro)/\S*)', re.DOTALL | re.IGNORECASE).findall(message.content)
                if urls:
                    async with message.channel.typing():
                        paths = []
                        for url in urls:
                            file = self.get_vocaroo_mp3(url)
                            paths.append(file)
                            f = discord.File(file)
                            await message.channel.send(file=f)

                        for p in paths:
                            os.remove(p)
