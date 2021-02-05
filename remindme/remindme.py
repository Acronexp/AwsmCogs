import logging
import re
from copy import copy
from datetime import datetime, timedelta

import discord
from typing import Union

from discord.ext import tasks
from redbot.core import Config, commands

logger = logging.getLogger("red.AwsmCogs.remindme")

class RemindMe(commands.Cog):
    """Système de rappels"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=736144321857978388, force_registration=True)

        default_user = {"reminders": []}
        self.config.register_user(**default_user)

        self.reminders_cache = {}
        self.remindme_loop.start()


    @tasks.loop(minutes=1.0)
    async def remindme_loop(self):
        """Boucle pour toutes les actions automatiques de Wingman"""
        await self.check_reminders()

    @remindme_loop.before_loop
    async def before_remindme_loop(self):
        logger.info('Starting remindme loop...')
        await self.bot.wait_until_ready()
        await self.cache_reminders()


    async def add_reminder(self, user: Union[discord.User, discord.Member], reminder: dict):
        """Ajouter un reminder à un utilisateur"""
        if user.id not in self.reminders_cache:
            self.reminders_cache[user.id] = []
        self.reminders_cache[user.id].append(reminder)
        saved_reminders = await self.config.user(user).reminders()
        saved_reminders.append(reminder)
        await self.config.user(user).reminders.set(saved_reminders)

    async def del_reminder(self, user: Union[discord.User, discord.Member], reminder: dict):
        """Retirer un reminder à un utilisateur"""
        saved_reminders = await self.config.user(user).reminders()
        reminders = copy(saved_reminders)
        if reminder in reminders:
            saved_reminders.remove(reminder)
        await self.config.user(user).reminders.set(saved_reminders)
        if reminder in self.reminders_cache.get(user.id, []):
            self.reminders_cache[user.id].remove(reminder)

    async def cache_reminders(self):
        """Met en cache les rappels pour qu'ils soient accédés plus rapidement"""
        all_users = await self.config.all_users()
        self.reminders_cache = {}
        for uid, uconfig in list(all_users.items()):
            if uid not in self.reminders_cache:
                self.reminders_cache[uid] = []
            for reminder in uconfig['reminders']:
                self.reminders_cache[uid].append(reminder)

    async def check_reminders(self):
        """S'occupe de tous les rappels expirés"""
        cache = copy(self.reminders_cache)
        for user_id, reminders in list(cache.items()):
            for reminder in reminders:
                if reminder['end'] <= datetime.now().timestamp():
                    user = self.bot.get_user(user_id)
                    if user:
                        em = discord.Embed(title="🔔 Rappel", description=reminder['text'], color=0xffac33)
                        try:
                            await user.send(embed=em)
                        except:
                            pass
                        await self.del_reminder(user, reminder)
                    else:
                        self.reminders_cache[user_id].remove(reminder)
                        await self.config.user_from_id(user_id).reminders.set(self.reminders_cache[user.id])


    def parse_timedelta(self, time_string: str) -> timedelta:
        """Renvoie un objet *timedelta* à partir d'un str contenant des informations de durée (Xj Xh Xm Xs)"""
        if not isinstance(time_string, str):
            raise TypeError("Le texte à parser est invalide, {} != str".format(type(time_string)))

        regex = re.compile('^((?P<days>[\\.\\d]+?)j)? *((?P<hours>[\\.\\d]+?)h)? *((?P<minutes>[\\.\\d]+?)m)? *((?P<seconds>[\\.\\d]+?)s)? *$')
        rslt = regex.match(time_string)
        if not rslt:
            raise ValueError("Aucun timedelta n'a pu être déterminé des valeurs fournies")

        parsed = rslt.groupdict()
        return timedelta(**{i: int(parsed[i]) for i in parsed if parsed[i]})


    @commands.group(name='remindme', aliases=['rm', 'rappel'], invoke_without_command=True)
    async def _manage_reminders(self, ctx, time: str, *, text: str):
        """Création et gestion de rappels personnalisés"""
        if ctx.invoked_subcommand is None:
            return await ctx.invoke(self.create_reminder, time=time, text=text)

    @_manage_reminders.command(name='new')
    async def create_reminder(self, ctx, time: str, *, text: str):
        """Créer un rappel

        Exemple de formattage du temps : `2j` `4h10m` `2m30s`"""
        author = ctx.author
        try:
            tmdelta = self.parse_timedelta(time)
            tmstamp = (datetime.now() + tmdelta).timestamp()
        except Exception as e:
            return await ctx.send(f"**Erreur** » `{e}`")

        all_reminders = await self.config.user(author).reminders()
        while tmstamp in all_reminders:
            tmstamp += 1
        reminder = {'text': text, 'start': datetime.now().timestamp(), 'end': tmstamp}
        await self.add_reminder(author, reminder)
        time = datetime.utcfromtimestamp(reminder['end']).strftime('%d/%m/%Y %H:%M')
        await ctx.send(f"**Rappel ajouté** » Votre rappel est prévu pour *{time}*.")

    @_manage_reminders.command(name='del')
    async def delete_reminder(self, ctx, num: int = None):
        """Supprimer un rappel

        Faire la commande sans nombre permet d'obtenir une liste des rappels en attente"""
        author = ctx.author
        reminders = self.reminders_cache.get(author.id, [])
        if not num:
            if reminders:
                text = ""
                n = 1
                for reminder in reminders:
                    time = datetime.fromtimestamp(reminder['end']).strftime('%d/%m/%Y %H:%M')
                    text += f"**{n}.** {time} » *{reminder['text']}*\n"
                em = discord.Embed(title="🔔 Liste des rappels", description=text, color=0xffac33)
                em.set_footer(text="Utilisez \";rm del <num>\" pour en effacer un")
                await ctx.send(embed=em)
            else:
                em = discord.Embed(title="🔔 Liste des rappels", description="Il n'y a aucun rappel en attente", color=0xffac33)
                em.set_footer(text="Utilisez \";rm <temps> [texte]\" pour en créer un")
                await ctx.send(embed=em)
        elif num <= len(reminders):
            reminder = reminders[num - 1]  # Les listes en python commencent à 0
            time = datetime.fromtimestamp(reminder['end']).strftime('%d/%m/%Y %H:%M')
            await self.del_reminder(author, reminder)
            await ctx.send(f"**Rappel effacé** » Votre rappel prévu pour *{time}* a été effacé avec succès.")
        else:
            await ctx.send("**Nombre invalide** » Faîtes la commande sans nombre pour obtenir une liste des rappels")

    @_manage_reminders.command(name='list')
    async def list_reminders(self, ctx):
        """Lister les rappels actifs"""
        author = ctx.author
        reminders = self.reminders_cache.get(author.id, [])
        if reminders:
            text = ""
            n = 1
            for reminder in reminders:
                time = datetime.fromtimestamp(reminder['end']).strftime('%d/%m/%Y %H:%M')
                text += f"**{n}.** {time} » *{reminder['text']}*\n"
            em = discord.Embed(title="🔔 Liste des rappels actifs", description=text, color=0xffac33)
            await ctx.send(embed=em)
        else:
            em = discord.Embed(title="🔔 Liste des rappels actifs", description="Il n'y a aucun rappel en attente",
                               color=0xffac33)
            em.set_footer(text="Utilisez \";rm <temps> [texte]\" pour en créer un")
            await ctx.send(embed=em)