from datetime import datetime, timedelta
import logging

import discord
from redbot.core import Config, commands, checks

logger = logging.getLogger("red.AwsmCogs.favboard")

class Favboard(commands.Cog):
    """Compiler sur un salon dédié le meilleur de son serveur"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=736144321857978388, force_registration=True)

        default_guild = {"channel": None,
                         "emoji": "⭐",
                         "target": 5,
                         "mod_override": False,
                         "color": None,

                         "favs": {}}
        self.config.register_guild(**default_guild)

    async def post_fav(self, message: discord.Message, destination: discord.TextChannel):
        guild = message.guild
        data = await self.config.guild(guild).all()
        fav = await self.config.guild(guild).favs.get_raw(message.id)
        color = data["color"] if data["color"] else await self.bot.get_embed_color(destination)

        text = f"[→ Aller au message]({message.jump_url})\n"
        text += message.content
        votes = len(fav["votes"])
        emoji = data["emoji"]
        foot = f"{emoji} {votes}"

        em = discord.Embed(description=text, color=color, timestamp=message.created_at)
        em.set_author(name=message.author.name, icon_url=message.author.avatar_url)
        em.set_footer(text=foot)

        img = emimg = misc = None
        emtxt = ""
        if message.attachments:
            attach = message.attachments[0]
            ext = attach.filename.split(".")[-1]
            if ext.lower() in ["png", "jpg", "jpeg", "gif", "gifv"]:
                img = attach.url
            else:
                misc = attach.url
        if message.embeds:
            msg_em = message.embeds[0]
            emtxt = "> " + msg_em.description if msg_em.description else ""
            if msg_em.image:
                emimg = msg_em.image.url
            elif msg_em.thumbnail:
                emimg = msg_em.thumbnail.url
        if img:
            em.set_image(url=img)
            if emimg:
                emtxt = emtxt + f"\n{emimg}" if emtxt else emimg
        elif emimg:
            em.set_image(url=emimg)
        if misc:
            emtxt = emtxt + f"\n{misc}" if emtxt else misc
        if emtxt:
            em.add_field(name="Inclus dans le message ↓", value=emtxt)

        return await destination.send(embed=em)

    async def edit_fav(self, original: discord.Message, embed_msg: discord.Message):
        guild = embed_msg.guild
        data = await self.config.guild(guild).all()
        fav = await self.config.guild(guild).favs.get_raw(original.id)
        em = embed_msg.embeds[0]
        votes = len(fav["votes"])
        emoji = data["emoji"]
        foot = f"{emoji} {votes}"
        em.set_footer(text=foot)
        try:
            return await embed_msg.edit(embed=em)
        except discord.Forbidden:
            logger.info(f"Impossible d'accéder à MSG_ID={embed_msg.id}")
        except:
            logger.info(f"Suppression des données de {original.id} car impossibilité définitive d'accéder à MSG_ID={embed_msg.id} "
                        f"(message probablement supprimé)")
            await self.config.guild(guild).favs.clear_raw(original.id)
            raise

    @commands.group(name="fav")
    @commands.guild_only()
    @checks.admin_or_permissions(manage_messages=True)
    async def _favboard(self, ctx):
        """Paramètres du FavBoard (salon de messages favoris)"""

    @_favboard.command(name="channel")
    async def fav_channel(self, ctx, channel: discord.TextChannel = None):
        """Configurer le salon receveur des messages favoris et activer la fonctionnalité

        Pour désactiver cette fonctionnalité, rentrez la commande sans aucun salon"""
        guild = ctx.guild
        if channel:
            await self.config.guild(guild).channel.set(channel.id)
            await ctx.send(f"**Salon modifié** • Le salon receveur est désormais {channel.mention}")
        else:
            await self.config.guild(guild).channel.set(None)
            await ctx.send(f"**Salon retiré** • La fonctionnalité est désactivée.")

    @_favboard.command(name="emoji")
    async def fav_emoji(self, ctx, emoji: str = "⭐"):
        """Modifier l'emoji pour mettre un message en favori

        L'emoji doit être un emoji de base Discord de type `string`"""
        guild = ctx.guild
        if type(emoji) == str:
            await self.config.guild(guild).emoji.set(emoji)
            await ctx.send(f"**Emoji modifié** • L'emoji de détection sera désormais {emoji}")
        else:
            await ctx.send("**Erreur** • L'emoji doit être de type `string`, c'est-à-dire qu'il doit être un emoji de base Discord")

    @_favboard.command(name="target")
    async def fav_target(self, ctx, limit: int = 5):
        """Modifier le nombre de votes qu'un message doit atteindre pour être mis en favori

        Si vous voulez que les modérateurs puissent mettre en favori directement, consultez `;help fav override`"""
        guild = ctx.guild
        if limit > 0:
            await self.config.guild(guild).target.set(limit)
            await ctx.send(f"**Valeur modifiée** • Il faudra {limit} votes pour qu'un message soit posté dans le salon des favoris")
        else:
            await ctx.send(f"**Valeur refusée** • Celle-ci doit être supérieure ou égale à 1.")

    @_favboard.command(name="override")
    async def fav_override(self, ctx):
        """Autoriser/refuser aux modérateurs (perm. `manage_messages`) de passer outre les votes pour sélectionner un favori

        Cela signifie qu'un modérateur mettra le message sélectionné en favori peu importe le nombre de votes sur celui-ci"""
        guild = ctx.guild
        override = await self.config.guild(guild).mod_override()
        if override:
            await ctx.send(f"**Override désactivé** • Les modos participeront normalement aux votes comme les autres membres.")
        else:
            await ctx.send(f"**Override activé** • Les modos outrepassent la nécessité d'accumuler les votes pour un message.")
        await self.config.guild(guild).mod_override.set(not override)

    @_favboard.command(name="color")
    async def fav_color(self, ctx, color: str = None):
        """Modifie la couleur des Embeds des favoris postés sur le salon

        Pour remettre la couleur du bot (par défaut) il suffit de ne pas rentrer de couleur"""
        if color:
            try:
                color = color.replace("#", "0x")
                color = int(color, base=16)
                em = discord.Embed(title="Couleur modifiée",
                                   description=f"Ceci est une démonstration de la couleur des Embeds du salon des favoris.",
                                   color=color)
                await self.config.guild(ctx.guild).color.set(color)
            except:
                return await ctx.send("**Erreur** • La couleur est invalide.\n"
                                      "Sachez qu'elle doit être fournie au format hexadécimal (ex. `D5D5D5` ou `0xD5D5D5`) et que certaines couleurs sont réservées par Discord.")
        else:
            em = discord.Embed(title="Couleur retirée",
                               description=f"Ceci est une démonstration de la couleur des Embeds du salon des favoris.",
                               color=color)
            await self.config.guild(ctx.guild).color.set(None)
        await ctx.send(embed=em)

    @_favboard.command(name="reset")
    async def fav_reset(self, ctx, favs_only: bool = True):
        """Reset les données des favoris sur le serveur

        Si vous précisez 'False' après la commande, effacera toutes les données Favboard"""
        if favs_only:
            await self.config.guild(ctx.guild).favs.clear()
            await ctx.send("**Reset effectué** • Les données des favoris ont été réset.\n"
                           "Notez que ça n'efface pas les messages déjà postés sur le salon, mais l'historique ayant été effacé un message peut être reposté.")
        else:
            await self.config.guild(ctx.guild).clear()
            await ctx.send("**Reset effectué** • Les données du serveur ont été reset.\n"
                           "Notez que ça n'efface pas les messages déjà postés sur le salon, mais l'historique ayant été effacé un message peut être reposté.\n"
                           "N'oubliez pas de rétablir vos paramètres si vous voulez réutiliser ce module.")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        channel = self.bot.get_channel(payload.channel_id)
        emoji = payload.emoji.name
        if hasattr(channel, "guild"):
            guild = channel.guild
            data = await self.config.guild(guild).all()
            if emoji == data["emoji"]:
                if data["channel"]:
                    message = await channel.fetch_message(payload.message_id)
                    if message.created_at.timestamp() + 86400 > datetime.utcnow().timestamp():
                        user = guild.get_member(payload.user_id)
                        favchan = guild.get_channel(data["channel"])

                        try:
                            fav = await self.config.guild(guild).favs.get_raw(message.id)
                        except:
                            fav = {"votes": [], "embed": None}
                            await self.config.guild(guild).favs.set_raw(message.id, value=fav)

                        if user.id not in fav["votes"]:
                            fav["votes"].append(user.id)
                            await self.config.guild(guild).favs.set_raw(message.id, value=fav)
                            if len(fav["votes"]) >= data["target"] or (
                                    data["mod_override"] and user.permissions_in(channel).manage_messages):
                                if not fav["embed"]:
                                    embed_msg = await self.post_fav(message, favchan)
                                    fav["embed"] = embed_msg.id
                                else:
                                    embed_msg = await favchan.fetch_message(fav["embed"])
                                    await self.edit_fav(message, embed_msg)
                                await self.config.guild(guild).favs.set_raw(message.id, value=fav)

                    elif message.id in await self.config.guild(guild).favs():  # Suppression des données des MSG de +24h
                        await self.config.guild(guild).favs.clear_raw(message.id)


