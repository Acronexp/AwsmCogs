import asyncio
import logging
import random
import re
import string
import time
from copy import copy
from datetime import datetime, timedelta

import discord
from discord.errors import HTTPException
from typing import Union, List, Tuple
from redbot.core import Config, commands, checks
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.chat_formatting import box, humanize_number, humanize_timedelta
from tabulate import tabulate

logger = logging.getLogger("red.AwsmCogs.cash")


class CashError(Exception):
    """Classe de base pour les erreurs Cash"""


class BalanceTooHigh(CashError):
    """Soulevée lorsque le balance dépasse le seuil fixé"""


class UnauthorizedMember(CashError):
    """Soulevée lorsqu'un membre n'est pas autorisé à réaliser une action"""


class UserNotFound(CashError):
    """Soulevée lorsqu'un membre n'est pas retrouvé sur le serveur"""


class UnknownGiftCode(CashError):
    """Soulevée lorsque le code cadeau donné n'existe pas"""


class GiftCodeExpired(CashError):
    """Soulevée lorsqu'un code cadeau vient d'expirer"""


def _invalid_amount(value: int) -> bool:
    return value < 0


class Account:
    def __init__(self, user: discord.Member, balance: int, logs: list, config: dict):
        self.user = user
        self.guild = user.guild
        self.balance = balance
        self.logs = logs
        self.config = config

    def __str__(self):
        return self.user.mention

    def __int__(self):
        return self.balance


class Log:
    def __init__(self, user: discord.Member, text: str, timestamp: int, delta: int):
        self.user = user
        self.guild = user.guild
        self.text = text
        self.timestamp = timestamp
        self.delta = delta

    def __str__(self):
        return self.text

    def __int__(self):
        return self.timestamp


class GiftCode:
    def __init__(self, code: str, author: discord.Member, expire: int, value: int):
        self.code = code
        self.author, self.guild = author, author.guild
        self.expire = expire
        self.value = value

    def __str__(self):
        return self.code

    def __int__(self):
        return self.value


class Cash(commands.Cog):
    """Economie virtuelle et jeux utilisant celle-ci"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=736144321857978388, force_registration=True)

        default_member = {"balance": 0,
                          "logs": [],
                          "config": {"day_delta": [None, 0],
                                     "cache_daily_bonus": '',
                                     "cache_presence_bonus": 0}
                          }

        default_guild = {"currency": "Ꞥ",

                         "daily_bonus": 100,
                         "presence_bonus": 0,
                         "presence_delay": 600,

                         "gift_codes": {}}

        default_global = {"max_balance": 10**9,
                          "max_logs_length": 3}
        self.config.register_member(**default_member)
        self.config.register_guild(**default_guild)
        self.config.register_global(**default_global)

    async def get_currency(self, guild: discord.Guild) -> str:
        """Obtenir le symbole de la monnaie du serveur"""
        return await self.config.guild(guild).currency()

    async def set_currency(self, guild: discord.Guild, symbol: str) -> str:
        """Modifie le symbole de la monnaie du serveur

        Renvoie le nouveau symbole attribué"""
        if not isinstance(symbol, str):
            raise TypeError("Type du symbole invalide, {} != str".format(type(symbol)))
        if len(symbol) > 5:
            raise ValueError("Le symbole de la monnaie ne peut pas faire plus de 5 caractères de long")
        await self.config.guild(guild).currency.set(symbol)
        return symbol

    async def get_account(self, member: discord.Member) -> Account:
        """Obtenir l'objet Account du membre demandé"""
        userdata = await self.config.member(member).all()
        return Account(member, **userdata)

    async def get_balance(self, member: discord.Member) -> int:
        """Renvoie la valeur actuelle du solde d'un membre"""
        account = await self.get_account(member)
        return account.balance

    async def enough_balance(self, member: discord.Member, cost: int) -> bool:
        """Vérifie si le membre possède assez de fonds pour une dépense"""
        if not isinstance(cost, int):
            raise TypeError("Type de la dépense invalide, {} != int".format(type(cost)))
        if _invalid_amount(cost):
            return False
        return await self.get_balance(member) >= cost

    async def set_balance(self, member: discord.Member, value: int) -> int:
        """Modifier le solde d'un membre

        Renvoie le nouveau solde du compte"""
        if not isinstance(value, int):
            raise TypeError("Type du dépôt invalide, {} != int".format(type(value)))
        if value < 0:
            raise ValueError("Le solde ne peut être négatif")
        max_balance = await self.config.max_balance()
        if value > max_balance:
            raise BalanceTooHigh(f"Il est impossible de dépasser le seuil fixé de {max_balance} crédits")

        oldvalue = await self.config.member(member).balance()
        await self.edit_delta(member, value - oldvalue)

        await self.config.member(member).balance.set(value)
        return value

    async def deposit_credits(self, member: discord.Member, value: int) -> int:
        """Ajouter des crédits au solde d'un membre

        Renvoie le nouveau solde du compte"""
        if not isinstance(value, int):
            raise TypeError("Type du dépôt invalide, {} != int".format(type(value)))
        if _invalid_amount(value):
            raise ValueError(f"Valeur de dépôt invalide, {value} < 0")

        current = await self.get_balance(member)
        return await self.set_balance(member, current + value)

    async def remove_credits(self, member: discord.Member, value: int) -> int:
        """Retirer des crédits au solde d'un membre

        Renvoie le nouveau solde du compte"""
        if not isinstance(value, int):
            raise TypeError("Type de retrait invalide, {} != int".format(type(value)))
        if _invalid_amount(value):
            raise ValueError(f"Valeur de retrait invalide, {value} < 0")

        current = await self.get_balance(member)
        if value > current:
            raise ValueError(f"Fonds insuffisants, {value} > {current}")

        return await self.set_balance(member, current - value)

    async def transfert_credits(self, from_: discord.Member, to_: discord.Member,
                                value: int) -> Tuple[Account, Account]:
        """Transfère des crédits d'un membre à un autre

        Renvoie un tuple contenant les comptes des deux membres"""
        if not isinstance(value, int):
            raise TypeError("Type du transfert invalide, {} != int".format(type(value)))
        if _invalid_amount(value):
            raise ValueError(f"Valeur du transfert invalide, {value} < 0")

        max_balance = await self.config.max_balance()
        if await self.get_balance(to_) + value > max_balance:
            raise BalanceTooHigh(f"Il est impossible de dépasser le seuil fixé de {max_balance} crédits lors d'une "
                                 f"transaction")

        await self.remove_credits(from_, value)
        await self.deposit_credits(to_, value)
        return await self.get_account(from_), await self.get_account(to_)

    async def gen_gcode(self, guild: discord.Guild) -> str:
        """Génère un code unique au format $XX-YYY pour les codes cadeaux

        Cap. max. théorique = 52 521 875 codes uniques"""
        current_codes = await self.config.guild(guild).gift_codes()
        r = lambda long: ''.join(random.choices(string.ascii_uppercase + string.digits, k=long))
        code = f"${r(2)}-{r(3)}"
        while code in current_codes:
            code = f"${r(2)}-{r(3)}"
        return code

    async def new_gift_code(self, from_: discord.Member, value: int, timestamp: int) -> str:
        """Génère un nouveau code cadeau contenant une certaine somme

        Le code est valide seulement sur le serveur du membre ayant généré le code

        Renvoie le code généré"""
        if not isinstance(value, int):
            raise TypeError("Type de valeur invalide, {} != int".format(type(value)))
        if not isinstance(timestamp, int):
            raise TypeError("Type du timestamp d'expiration invalide, {} != int".format(type(timestamp)))
        if value < 0:
            raise ValueError("La valeur de crédits contenus dans le code doit être positif")
        if timestamp < 0:
            raise ValueError("La valeur de l'expiration doit être positive ou nulle")

        guild = from_.guild
        code = await self.gen_gcode(guild)
        current = await self.config.guild(guild).gift_codes()
        current[code] = {"value": value, "expire": timestamp, "author": from_.id}
        await self.config.guild(guild).gift_codes.set(current)
        return code

    async def fetch_gift_code(self, code: str, ref_user: discord.Member = None) -> Union[GiftCode, None]:
        """Retrouve automatiquement le serveur d'un code et renvoie celui-ci si trouvé, sinon None"""
        if not isinstance(code, str):
            raise TypeError("Type du code invalide, {} != str".format(type(code)))

        all_guilds = await self.config.all_guilds()
        for guildid in all_guilds:
            if code in all_guilds[guildid]["gift_codes"]:
                guild = self.bot.get_guild(guildid)
                if guild:
                    if ref_user is not None and ref_user in guild.members:
                        return await self.get_gift_code(guild, code)
                    else:
                        return await self.get_gift_code(guild, code)
        return None

    async def get_gift_code(self, guild: discord.Guild, code: str) -> Union[GiftCode, None]:
        """Renvoie un objet *GiftCode* s'il est trouvé, sinon None"""
        if not isinstance(code, str):
            raise TypeError("Le code est invalide, {} != str".format(type(code)))

        codes = await self.config.guild(guild).gift_codes()
        if code in codes:
            c = codes[code]
            if time.time() > c["expire"]:
                del codes[code]
                await self.config.guild(guild).gift_codes.set(codes)
                raise GiftCodeExpired(f"Le code cadeau {code} vient d'expirer")

            user = guild.get_member(c["author"])
            if not user:
                raise UserNotFound(f"Le membre avec l'ID {c['author']} est introuvable")
            return GiftCode(author=user, value=c["value"], code=code, expire=c["expire"])
        return None

    async def use_gift_code(self, user: discord.Member, code: str) -> Union[int, bool]:
        """Utilise un code et renvoie la valeur qu'il contenait si le membre générateur possède suffisamment de fonds, sinon renvoie False"""
        gift = await self.get_gift_code(user.guild, code)
        if not gift:
            raise UnknownGiftCode(f"Le code cadeau {code} n'existe pas pour GUILD_ID={user.guild.id}")
        if not await self.enough_balance(user, gift.value):
            return False
        await self.transfert_credits(gift.author, user, gift.value)
        return await self.remove_gift_code(user.guild, code)

    async def remove_gift_code(self, guild: discord.Guild, code: str) -> int:
        """Supprime le code et renvoie la valeur contenue dans celui-ci"""
        try:
            gift = await self.get_gift_code(guild, code)
            if not gift:
                raise UnknownGiftCode(f"Le code cadeau {code} n'existe pas pour GUILD_ID={guild.id}")
            await self.config.guild(guild).gift_codes.clear_raw(code)
            return gift.value
        except:
            raise ValueError(f"Le code cadeau {code} n'est pas valide")

    async def get_delta(self, member: discord.Member, yield_date: bool = False) -> Union[int, list]:
        """Renvoie la valeur et date du delta total des opérations du membre"""
        acc = await self.get_account(member)
        delta = acc.config["day_delta"]
        return delta[1] if not yield_date else delta

    async def edit_delta(self, member: discord.Member, value: int) -> int:
        """Modifie la valeur du delta des opérations du jour

        Renvoie la nouvelle valeur du delta"""
        if not isinstance(value, int):
            raise TypeError("Type de la valeur du delta invalide, {} != int".format(type(value)))

        date, delta = await self.get_delta(member, True)
        today = datetime.now().strftime("%Y.%m.%d")
        if date != today:
            delta = 0
        await self.config.member(member).config.set_raw("day_delta", value=[today, delta + value])
        return delta + value

    async def get_log(self, member: discord.Member, timestamp: int) -> Union[Log, None]:
        """Renvoie le (1er) log du membre correspondant au timestamp fourni si trouvé, sinon None"""
        if not isinstance(timestamp, int):
            raise TypeError("Type du timestamp invalide, {} != int".format(type(timestamp)))

        acc = await self.get_account(member)
        for log in acc.logs:
            if log["timestamp"] == timestamp:
                return Log(**log)
        return None

    async def get_member_logs(self, member: discord.Member) -> Union[List[Log], list]:
        """Renvoie tous les logs (sous forme d'objets Log) d'un membre

        Renvoie une liste vide si aucun log n'est présent"""
        acc = await self.get_account(member)
        all_logs = []
        if acc.logs:
            for log in acc.logs:
                all_logs.append(Log(member, **log))
        return all_logs

    async def add_log(self, member: discord.Member, text: str, delta: int) -> list:
        """Ajoute un log au membre visé

        Renvoie le nouvel état des logs"""
        if not isinstance(text, str):
            raise TypeError("Type du contenu du log invalide, {} != str".format(type(text)))
        if not isinstance(delta, int):
            raise TypeError("Type de somme du log invalide, {} != int".format(type(delta)))
        added = {"text": text, "timestamp": int(time.time()), "delta": delta}

        acc = await self.get_account(member)
        logs = acc.logs
        max_logs_length = await self.config.max_logs_length()
        if len(logs) >= max_logs_length:
            logs = logs[-(max_logs_length - 1):]
        logs.append(added)

        await self.config.member(member).logs.set(logs)
        return logs

    async def delete_log(self, member: discord.Member, timestamp: int) -> list:
        """Retire un log (ou plusieurs s'ils ont un timestamp identique) au membre visé

        Typiquement optionnel, les logs étant remplacés au fur et à mesure des ajouts

        Renvoie le nouvel état des logs"""
        if not isinstance(timestamp, int):
            raise TypeError("Type du timestamp du log invalide, {} != int".format(type(timestamp)))
        if not await self.get_log(member, timestamp):
            raise ValueError(f"Log avec le timestamp {timestamp} pour USERID={member.id} introuvable")

        acc = await self.get_account(member)
        logs = acc.logs
        new = copy(logs)
        for log in logs:
            if log["timestamp"] == timestamp:
                new.remove(log)

        await self.config.member(member).logs.set(new)
        return new

    async def wipe_logs(self, member: discord.Member) -> None:
        """Supprime tous les logs d'un membre"""
        await self.config.member(member).clear_raw("logs")

    async def wipe_guild(self, guild: discord.Guild) -> None:
        """Supprime les données bancaires des membres d'un serveur"""
        await self.config.clear_all_members(guild)

    async def wipe_account(self, member: discord.Member) -> None:
        """Supprime les données bancaires d'un membre"""
        await self.config.member(member).clear()

    async def raw_delete_account(self, user_id: int, guild: discord.Guild) -> None:
        """Supprime un compte bancaire par ID du membre"""
        await self.config.member_from_ids(guild.id, user_id).clear()

    async def get_max_balance(self) -> int:
        """Renvoie la valeur maximale que peut atteindre un solde de membre (sur n'importe quel serveur)"""
        return self.config.max_balance()

    async def set_max_balance(self, value: int) -> None:
        """Modifie la valeur maximale qu'un solde de membre peut atteindre"""
        if not isinstance(value, int):
            raise TypeError("Type de la valeur maximale invalide, {} != int".format(type(value)))
        if value <= 0:
            raise ValueError("Valeur invalide, le maximum ne peut pas être négatif ou nul")

        await self.config.max_balance.set(value)

    async def get_max_logs_length(self) -> int:
        """Renvoie le nombre maximal de logs pouvant être stockés dans les données bancaires d'un membre"""
        return self.config.max_logs_length()

    async def set_max_logs_length(self, length: int) -> None:
        """Modifie le nombre de logs stockés pour un membre"""
        if not isinstance(length, int):
            raise TypeError("Type de la longueur maximale invalide, {} != int".format(type(length)))
        if length < 1:
            raise ValueError("Valeur invalide, le maximum ne peut pas être négatif ou nul")

        await self.config.max_logs_length.set(length)

    async def get_guild_leaderboard(self, guild: discord.Guild, cutoff: int = None) -> Union[list, List[Account]]:
        """Renvoie le top des membres les plus riches du serveur (liste d'objets Account)

        Renvoie une liste vide si aucun top n'est générable"""
        users = await self.config.all_members(guild)
        sorted_users = sorted(list(users.items()), key=lambda u: u[1]["balance"], reverse=True)
        top = []
        for uid, acc in sorted_users:
            user = guild.get_member(uid)
            if user:
                top.append(Account(user, **acc))
        return top[:cutoff] if cutoff else top

    async def get_leaderboard_position_for(self, member: discord.Member) -> int:
        """Renvoie la position du membre dans le classement de son serveur

        Renvoie la dernière place du classement si le membre n'est pas trouvé"""
        top = await self.get_guild_leaderboard(member.guild)
        for acc in top:
            if acc.user == member:
                return top.index(acc) + 1
        return len(top)

    async def utils_parse_timedelta(self, time_string: str) -> timedelta:
        """Renvoie un objet *timedelta* à partir d'un str contenant des informations de durée (Xj Xh Xm Xs)"""
        if not isinstance(time_string, str):
            raise TypeError("Le texte à parser est invalide, {} != str".format(type(time_string)))

        regex = re.compile('^((?P<days>[\\.\\d]+?)j)? *((?P<hours>[\\.\\d]+?)h)? *((?P<minutes>[\\.\\d]+?)m)? *((?P<seconds>[\\.\\d]+?)s)? *$')
        sch = regex.match(time_string)
        if not sch:
            raise ValueError("Aucun timedelta n'a pu être déterminé des valeurs fournies")

        parsed = sch.groupdict()
        return timedelta(**{i: int(parsed[i]) for i in parsed if parsed[i]})

    # Commandes -----------------------v

    @commands.group(name="bank", aliases=["b"], invoke_without_command=True)
    async def _bank_actions(self, ctx, user: discord.Member = None):
        """Commandes de gestion du compte bancaire virtuel *Cash*"""
        if ctx.invoked_subcommand is None:
            return await ctx.invoke(self.show_bank, user=user)

    @_bank_actions.command(name="show")
    @commands.guild_only()
    async def show_bank(self, ctx, user: discord.Member = None):
        """Afficher les infos de son compte"""
        user = user if user else ctx.message.author
        acc = await self.get_account(user)
        curr = await self.get_currency(ctx.guild)

        hum_balance = humanize_number(acc.balance)
        em = discord.Embed(color=user.color, timestamp=ctx.message.created_at)
        em.set_author(name="Compte de " + str(user), icon_url=user.avatar_url)
        em.add_field(name="💰 Solde", value=box(f"{hum_balance} {curr}"))
        delta = await self.get_delta(user)
        delta_emoji = "📉" if delta < 0 else "📈"
        em.add_field(name=f"{delta_emoji} Variation", value=box(f"{delta:+}"))
        top = await self.get_leaderboard_position_for(user)
        em.add_field(name="🏅 Position", value=box(f"#{top}"))

        logs = await self.get_member_logs(user)
        if logs:
            txt = "\n".join([f"{log.delta:+} · {log.text[:50]}" for log in logs][::-1])
            em.add_field(name="📃 Historique", value=txt)
        await ctx.send(embed=em)

    @_bank_actions.command(name="give")
    @commands.guild_only()
    @commands.cooldown(1, 60, commands.BucketType.member)
    async def bank_give(self, ctx, receveur: discord.Member, somme: int):
        """Transférer de l'argent à un receveur tiers"""
        try:
            await self.transfert_credits(ctx.author, receveur, int(somme))
            curr = await self.get_currency(ctx.guild)
            await ctx.send(f"**Transfert réalisé** • {receveur.mention} a reçu **{somme}** {curr}")
        except ValueError:
            return await ctx.send("**Impossible** • Vous ne pouvez pas transférer une somme nulle ou négative")
        except BalanceTooHigh:
            plaf = humanize_number(await self.config.max_balance())
            return await ctx.send(f"**Limite atteinte** • {receveur.mention} ne peut pas recevoir cette somme car "
                                  f"il dépasserait le plafond fixé de {plaf}")
        await self.add_log(ctx.author, f"Transfert d'argent à {receveur.name}", -somme)
        await self.add_log(receveur, f"Reception d'argent de {ctx.author.name}", somme)

    @_bank_actions.command(name="gift")
    @commands.guild_only()
    @commands.cooldown(1, 60, commands.BucketType.member)
    async def bank_gift(self, ctx, somme: int, expire: str = "24h"):
        """Générer un code cadeau contenant des crédits (retrait différé)

        Le retrait de crédits sur le compte du membre générateur n'est pas immédiat et l'utilisation du code sera impossible en cas de manque de fonds

        Par défaut les codes expirent au bout de 24h, vous pouvez modifier cela avec le paramètre *<expire>* en utilisant le format `\"Xj Xh Xm Xs\"`"""
        user = ctx.author
        if somme < 1:
            return await ctx.send(
                "**Erreur** • La valeur doit être positive (sup. à 0)")
        try:
            tdelta = await self.utils_parse_timedelta(expire)
        except ValueError:
            return await ctx.send("**Erreur** • Le temps d'expiration n'est pas valide, utilisez le format `\"Xj Xh Xm Xs\"`")

        if await self.enough_balance(user, somme):
            timestamp = (datetime.now() + tdelta).timestamp()
            curr = await self.get_currency(ctx.guild)
            em = discord.Embed(title=f"**Nouveau code-cadeau** · {somme} {curr}",
                               description="**En cours de génération...**")
            em.add_field(name="Information", value="Un membre peut utiliser ce code avec `b open`\n"
                                                   "Vous serez débité de la valeur du code lors de son utilisation\n"
                                                   "L'expiration du code rend impossible son utilisation, pour "
                                                   "détruire le code avant sa date d'expiration utilisez-le vous-même.")
            em.set_footer(text="Ce code expirera dans {}".format(humanize_timedelta(timedelta=tdelta)))
            try:
                dm = await user.send(embed=em)
            except:
                return await ctx.send("**Erreur** • Je ne peux pas générer de code si vous ne me permettez pas de vous envoyer un MP")
            try:
                code = await self.new_gift_code(user, somme, int(timestamp))
                await asyncio.sleep(1)
                em.description = box(code)
                em.colour = user.color
                await dm.edit(embed=em)
            except ValueError as e:
                await ctx.send(
                    f"**Erreur** • La génération du code n'a pas pu se faire en raison d'un problème dans les valeurs fournies : `{e}`")
                em.description = box("Erreur dans la génération du code")
                await dm.edit(embed=em)
        else:
            await ctx.send(
                "**Impossible** • Même si le retrait n'est pas immédiat, vous devez avoir la somme sur votre compte préalablement à la génération d'un code")

    @_bank_actions.command(name="open")
    async def bank_open_gift(self, ctx, code: str):
        """Utiliser un code-cadeau et obtenir son contenu

        Les codes ne fonctionnent que sur le serveur où ils ont été générés"""
        code = code.upper().strip()

        try:
            if ctx.guild:
                gift = await self.get_gift_code(ctx.guild, code)
            else:
                gift = await self.fetch_gift_code(code)
        except ValueError:
            return await ctx.send("**Invalide** • Le code fourni est invalide, vérifiez-le et réessayez")
        except GiftCodeExpired:
            return await ctx.send("**Expiré** • Le code fourni a expiré, consultez le générateur du code pour en obtenir un nouveau")

        if gift:
            guild = gift.guild
            curr = await self.get_currency(guild)
            hum_value = humanize_number(gift.value)
            content = f"{hum_value} {curr}"
            em = discord.Embed(title=f"**Code-cadeau** · {code}",
                               description="Voulez-vous échanger le code contre son contenu ?")
            em.add_field(name="Contenu", value=box(content))
            em.set_footer(text="🎁 Accepter | ❌ Refuser")
            emojis = ["🎁", "❌"]
            msg = await ctx.send(embed=em)

            start_adding_reactions(msg, emojis)
            try:
                react, user = await self.bot.wait_for("reaction_add",
                                                      check=lambda r, u: u == ctx.author and r.message.id == msg.id,
                                                      timeout=20)
            except asyncio.TimeoutError:
                await msg.delete()
                return
            else:
                emoji = react.emoji

            await msg.delete()
            if emoji == "🎁":
                if await self.enough_balance(gift.author, gift.value):
                    try:
                        await self.use_gift_code(ctx.author, code)
                    except Exception as e:
                        logger.error(e, exc_info=True)
                        return await ctx.send("Erreur de transfert de fonds : `{}`".format(str(e).replace('\"', '')))
                    await self.add_log(ctx.author, "Utilisation d'un code-cadeau", gift.value)
                    await self.add_log(gift.author, "Débit du code cadeau utilisé", -gift.value)
                    await ctx.send(f"**Utilisation réussie** • **{humanize_number(gift.value)}** {curr} ont été "
                                   f"transférés sur votre compte.")
                else:
                    await ctx.send(f"**Fonds insuffisants** • L'auteur du code ({str(gift.author)}) n'a plus les "
                                   f"fonds suffisants pour assumer la valeur de ce code")
        else:
            await ctx.send(f"**Code invalide** • Le code est invalide ou celui-ci a peut-être expiré")

    @commands.command(name="bonus")
    @commands.guild_only()
    async def cash_bonus(self, ctx):
        """Recevoir son bonus quotidien de crédits"""
        author = ctx.author
        today = datetime.now().strftime("%Y.%m.%d")
        acc = await self.get_account(author)
        curr = await self.get_currency(ctx.guild)
        bonus = await self.config.guild(ctx.guild).daily_bonus()
        if bonus:
            if acc.config["cache_daily_bonus"] != today:
                await self.config.member(author).config.set_raw("cache_daily_bonus", value=today)
                new = await self.deposit_credits(author, bonus)
                await self.add_log(author, "Bonus quotidien récupéré", bonus)
                em = discord.Embed(color=author.color,
                                   description=f"**+{bonus}** {curr} ont été ajoutés à votre compte au titre du bonus quotidien.",
                                   timestamp=ctx.message.created_at)
                em.set_author(name=str(author), icon_url=author.avatar_url)
                em.set_footer(text=f"Vous avez désormais {new} {curr}")
                await ctx.send(embed=em)
            else:
                await ctx.send("**Déjà récupéré** • Revenez demain pour obtenir votre bonus !")
        else:
            await ctx.send("**Désactivé** • Ce serveur n'offre pas de bonus quotidien")

    @commands.command(name="leaderboard", aliases=["lb"])
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.guild)
    async def display_leaderboard(self, ctx, top: int = 20):
        """Affiche le top des membres les plus riches du serveur

        Vous pouvez modifier la longueur du top en précisant le paramètre *<top>*"""
        lbd = await self.get_guild_leaderboard(ctx.guild, top)
        if lbd:
            tbl = []
            for acc in lbd:
                tbl.append([str(acc.user), acc.balance])
            em = discord.Embed(color=await self.bot.get_embed_color(ctx.channel),
                               description="```" + tabulate(tbl, headers=["Membre", "Solde"]) + "```",)
            em.set_author(name=f"🏆 Leaderboard de {ctx.guild.name}", icon_url=ctx.guild.icon_url)
            try:
                await ctx.send(embed=em)
            except HTTPException:
                await ctx.send("**Erreur** • Le top est trop grand pour être affiché, utilisez une "
                               "valeur de <top> plus réduite")
        else:
            await ctx.send("Il n'y a aucun top à afficher.")

    @commands.group(name="bankset", aliases=["bset"])
    @checks.admin_or_permissions(manage_messages=True)
    async def _bank_set(self, ctx):
        """Commandes de modération de la banque"""

    @_bank_set.command(name="monnaie", aliases=["currency"])
    async def _bank_currency(self, ctx, symbole: str):
        """Changer le symbole utilisé pour la monnaie sur le serveur"""
        try:
            await self.set_currency(ctx.guild, symbole)
            await ctx.send(f"**Changement réalisé** • Le nouveau symbole de la monnaie sera `{symbole}`")
        except ValueError:
            await ctx.send("**Erreur** • Vous ne pouvez pas utiliser une monnaie de plus de 5 caractères de long")

    @_bank_set.command(name="dailybonus")
    async def _bank_daily_bonus(self, ctx, somme: int):
        """Modifier le bonus quotidien octroyé aux membres

        Mettre 0 désactive le bonus quotidien"""
        guild = ctx.guild
        if somme >= 0:
            await self.config.guild(guild).daily_bonus.set(somme)
            curr = await self.get_currency(guild)
            if somme > 0:
                await ctx.send(f"**Somme modifiée** • Les membres auront le droit à {somme} {curr} par jour")
            else:
                await ctx.send("**Bonus désactivé** • Les membres ne pourront plus demander un bonus quotidien de crédits")
        else:
            await ctx.send("**Impossible** • La valeur du bonus doit être positif, ou nulle si vous voulez désactiver la fonctionnalité")

    @_bank_set.command(name="presbonus")
    async def _bank_presence_bonus(self, ctx, somme: int):
        """Modifier le bonus de présence octroyé aux membres parlant sur les salons (par unité de temps)

        Mettre 0 désactive ce bonus"""
        guild = ctx.guild
        if somme >= 0:
            await self.config.guild(guild).presence_bonus.set(somme)
            curr = await self.get_currency(guild)
            delay = await self.config.guild(guild).presence_delay()
            if somme > 0:
                await ctx.send(f"**Somme modifiée** • Les membres recevront {somme} {curr} toutes les {delay} secondes")
            else:
                await ctx.send(
                    "**Bonus désactivé** • Les membres ne recevront plus de crédits lorsqu'ils discutent")
        else:
            await ctx.send(
                "**Impossible** • La valeur du bonus doit être positif, ou nulle si vous voulez désactiver la fonctionnalité")

    @_bank_set.command(name="presdelay")
    async def _bank_presence_delay(self, ctx, secondes: int = 600):
        """Modifier le délai en secondes entre deux bonus de présence (par def. 600s = 10m)"""
        guild = ctx.guild
        if secondes >= 60:
            await self.config.guild(guild).presence_delay.set(secondes)
            curr = await self.get_currency(guild)
            bonus = await self.config.guild(guild).presence_bonus()
            await ctx.send(
                    f"**Délai modifié** • Les membres recevront {bonus} {curr} toutes les {secondes} secondes")
        else:
            await ctx.send(
                "**Invalide** • Le délai doit être supérieur à 60s")

    @_bank_set.command(name="edit")
    async def _bank_edit_account(self, ctx, user: discord.Member, value: int = None):
        """Modifie le solde d'un compte de membre

        Ne rien mettre affiche le solde actuel du membre"""
        acc = await self.get_account(user)
        curr = await self.get_currency(user.guild)
        if value:
            try:
                solde = await self.set_balance(user, value)
                await ctx.send(f"**Succès** • Le solde de {user.mention} est désormais de **{solde}** {curr}")
            except ValueError:
                await ctx.send("**Erreur** • Le solde d'un membre ne peut être négatif")
        else:
            await ctx.send(f"**Info** • Le solde de {str(user)} est de **{humanize_number(acc.balance)}** {curr}")

    @_bank_set.command(name="resetuser")
    async def _bank_reset_account(self, ctx, user: discord.Member):
        """Reset les données bancaires d'un membre (cache compris)"""
        await self.config.member(user).clear()
        await ctx.send(f"**Succès** • Le compte de {user.mention} a été réinitialisé")

    @_bank_set.command(name="resetcache")
    async def _bank_reset_account_cache(self, ctx, user: discord.Member):
        """Reset seulement les données du cache du compte bancaire du membre

        Cela réinitialise les délais des bonus"""
        await self.config.member(user).config.clear_raw("cache_daily_bonus")
        await self.config.member(user).config.clear_raw("cache_presence_bonus")
        await ctx.send(f"**Succès** • Le cache du compte de {user.mention} a été réinitialisé")

    # Bonus de présence ---------------------v

    async def manage_presence_bonus(self, member: discord.Member) -> Union[int, bool]:
        """Gère l'ajout auto. des bonus de présence sur les serveurs ayant activé l'option

        Renvoie le nouveau solde du membre s'il est modifié, sinon False"""
        if member.bot:
            raise UnauthorizedMember("Un bot ne peut pas toucher les bonus de présence")

        guild = member.guild
        conf = await self.config.guild(guild).all()
        if conf["presence_bonus"]:
            acc = await self.get_account(member)
            if acc.config["cache_presence_bonus"] + conf["presence_delay"] < time.time():
                await self.config.member(member).config.set_raw("cache_presence_bonus", value=time.time())
                return await self.deposit_credits(member, conf["presence_bonus"])
        return False

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild:
            if not message.author.bot:
                await self.manage_presence_bonus(message.author)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, author):
        if reaction.message.guild:
            if not author.bot:
                await self.manage_presence_bonus(author)
