import asyncio
import logging
import re
from urllib import parse

import discord
import os
import urllib.request

import requests
from redbot.core.data_manager import cog_data_path

from redbot.core import Config, commands, checks, errors


logger = logging.getLogger("red.AwsmCogs.contentcleaner")


class ContentCleaner(commands.Cog):
    """Ensemble de triggers automatiques corrigeant des liens et contenus"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=736144321857978388, force_registration=True)

        default_guild = {"vocaroo": False,
                         "shorten": False}
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

    def shorten_link(self, link: str):
        key = 'a202f4f51e7d72c5826e2fcf649e6c3cc58e1'
        url = parse.quote(link)
        r = requests.get('http://cutt.ly/api/api.php?key={}&short={}'.format(key, url))
        result = r.json()['url']
        if result['status'] == 7:
            return result['shortLink']
        else:
            return None

    @commands.group(name="contentcleaner", aliases=["cclean"])
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

    @_content_cleaner.command()
    async def shorten(self, ctx):
        """Activer/désactiver la réduction auto. des liens trop longs"""
        param = await self.config.guild(ctx.guild).shorten()
        if param:
            await ctx.send("**Désactivé** » Les URL trop longs ne seront pas remplacés")
        else:
            await ctx.send("**Activé** » Les URL trop longs (+ 150 caractères) postés indépendamment seront raccourcis automatiquent")
        await self.config.guild(ctx.guild).shorten.set(not param)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild:
            guild = message.guild
            channel = message.channel
            author = message.author
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
            if params['shorten']:
                content = message.content
                if "http" in content:
                    scan = re.compile(r'(https?://\S*\.\S*)', re.DOTALL | re.IGNORECASE).findall(content)
                    if scan:
                        url = scan[0]
                        if len(content) <= len(url) >= 150:
                            try:
                                await message.delete()
                            except:
                                pass
                            else:
                                await channel.send(f"De **{author}** : " + self.shorten_link(url))

