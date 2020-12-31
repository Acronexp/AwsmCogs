import asyncio
import logging
import time
from datetime import datetime

import discord
from typing import Union
from redbot.core import Config, commands, checks, errors
from redbot.core.utils.chat_formatting import box, humanize_number
from tabulate import tabulate

logger = logging.getLogger("red.AwsmCogs.bet")

class BetError(Exception):
    """Erreurs liées au module Bet"""


class CashNotLoaded(BetError):
    """Soulevée lorsque le module Cash n'est pas chargé"""


class Bet(commands.Cog):
    """Système de paris exploitant l'économie du module Cash"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=736144321857978388, force_registration=True)

        default_guild = {"bets": {}}
        self.config.register_guild(**default_guild)

        self.bets = {}

        try:
            self.bot.get_cog("Cash")
        except errors.CogLoadError:
            raise CashNotLoaded("Le module Cash est nécessaire au fonctionnement de ce module Bet")

    async def gen_new_bet(self, channel: discord.TextChannel, a: str, b: str, votes_exp: int, title: str):
        """Génère un nouveau pari sur le salon écrit donné"""
        if not await self.get_bet(channel):
            data = {"a": {"choice": a,
                          "votes": {}},
                    "b": {"choice": b,
                          "votes": {}},
                    "vote_exp": votes_exp,
                    "title": title,
                    "votes_open": True,
                    "betmsg": None}
            self.bets[channel.id] = data
            return self.bets[channel.id]
        raise ValueError(f"Un pari est déjà en cours sur #{channel.name}")

    async def get_bet(self, channel: discord.TextChannel) -> Union[dict, None]:
        """Renvoie les données du pari lié au salon écrit s'il y en a un, sinon renvoie None"""
        if not isinstance(channel, discord.TextChannel):
            raise TypeError("Type de channel invalide, {} != discord.TextChannel".format(type(channel)))

        if channel.id in self.bets:
            return self.bets[channel.id]
        return None

    async def get_bet_embed(self, channel: discord.TextChannel, footer_txt: str, winner: str = None) -> Union[discord.Embed, None]:
        """Renvoie un embed tout prêt pour le pari en cours sur le salon, sinon None s'il n'y en a pas"""
        data = await self.get_bet(channel)
        if data:
            color = await self.bot.get_embed_color(channel)
            title = data["title"]
            em = discord.Embed(title=f"🎲 **Pari** · {title}", color=color)

            somme_a = sum([data["a"]["votes"][i] for i in data["a"]["votes"]])
            nb_a = len(data["a"]["votes"])

            somme_b = sum([data["b"]["votes"][i] for i in data["b"]["votes"]])
            nb_b = len(data["b"]["votes"])

            rdm_a = round(1 + (somme_b / somme_a), 2) if somme_a > 0 else 1.1
            rdm_b = round(1 + (somme_a / somme_b), 2) if somme_b > 0 else 1.1

            totalvotes = nb_a + nb_b
            prc_a = round(nb_a / totalvotes * 100) if totalvotes > 0 else 0
            prc_b = round(nb_b / totalvotes * 100) if totalvotes > 0 else 0

            tbla = [("Crédits misés", humanize_number(somme_a)),
                    ("Rendement", f'1:{rdm_a}'),
                    ("Votants", f'{nb_a} [{prc_a}%]')]

            choicetxt_a = data['a']['choice']
            if winner and winner.lower() != 'a':
                choicetxt_a = f'~~{choicetxt_a}~~'
            em.add_field(name=f"**A** · {choicetxt_a}", value=box(tabulate(tbla, tablefmt="plain")))

            tblb = [("Crédits misés", humanize_number(somme_b)),
                    ("Rendement", f'1:{rdm_b}'),
                    ("Votants", f'{nb_b} [{prc_b}%]')]

            choicetxt_b = data['b']['choice']
            if winner and winner.lower() != 'b':
                choicetxt_b = f'~~{choicetxt_b}~~'
            em.add_field(name=f"**B** · {choicetxt_b}", value=box(tabulate(tblb, tablefmt="plain")))
            em.set_footer(text=footer_txt)
            return em
        return None

    @commands.group(name="bet", aliases=["pari"])
    @commands.guild_only()
    async def _bet_main(self, ctx):
        """Commandes de gestion des paris"""

    @commands.group(name="bet", invoke_without_command=True)
    async def _bet_main(self, ctx, choix: str, somme: int):
        """Commandes de gestion du compte bancaire virtuel *Cash*"""
        if ctx.invoked_subcommand is None:
            return await ctx.invoke(self.vote_bet, choix, somme)

    @_bet_main.command(name="new")
    @checks.admin_or_permissions(manage_messages=True)
    async def new_bet(self, ctx, title: str, choix_1: str, choix_2: str, votes: str = "5m"):
        """Créer un nouveau pari sur ce salon

        **Exemple :** `bet new "Qui va gagner ?" "Choix numéro 1" "Choix numéro 2" 10m`

        Le délai par défaut d'arrêt des votes si celui-ci n'est pas précisé est de 5m"""
        channel = ctx.channel
        cash = self.bot.get_cog("Cash")
        if not await self.get_bet(channel):
            tdelta = await cash.utils_parse_timedelta(votes)
            if len(title) > 1 and len(choix_1) > 0 and len(choix_2) > 0 and tdelta:
                timestamp = (datetime.now() + tdelta).timestamp()
                try:
                    data = await self.gen_new_bet(channel, choix_1, choix_2, timestamp, title)
                except ValueError:
                    return await ctx.send("**Erreur** • Un pari est déjà en cours sur ce salon écrit")

                betmsg = await ctx.send(embed=await self.get_bet_embed(
                    channel, "Votes ouverts ! Faîtes 'bet A|B <somme>' pour parier !"))
                await betmsg.pin()
                data["betmsg"] = betmsg.id
                while time.time() < timestamp and data["votes_open"]:
                    await asyncio.sleep(1)
                nem = await self.get_bet_embed(
                    channel, "Les votes sont fermés | Résultat en attente...")
                await betmsg.edit(embed=nem)
                if data["votes_open"]:
                    data["votes_open"] = False
                await ctx.send("**Fermeture des paris** • Les votes pour le pari en cours sont désormais fermés. "
                               "Que les meilleurs gagnent !")
            else:
                await ctx.send("**Erreur** • Il semblerait que les arguments de la commande soient invalides, "
                               "vérifiez que vous ayez mis le titre et les choix entre guillemets")
        else:
            await ctx.send("**Erreur** • Un pari est déjà en cours sur ce salon écrit")

    @_bet_main.command(name="stop")
    @checks.admin_or_permissions(manage_messages=True)
    async def stop_bet(self, ctx):
        """Arrête les votes du pari en cours avant l'expiration automatique"""
        channel = ctx.channel
        data = await self.get_bet(channel)
        if data:
            if data["votes_open"]:
                data["votes_open"] = False
            else:
                await ctx.send("**Inutile** • Les votes sont déjà fermés pour ce pari (consultez l'épingle)")
        else:
            await ctx.send("**Erreur** • Il n'y a aucun pari en cours sur ce serveur")

    @_bet_main.command(name="result")
    @checks.admin_or_permissions(manage_messages=True)
    async def result_bet(self, ctx, choix: str):
        """Indiquer le résultat du pari pour le terminer

        Vous devez rentrer l'ID du choix (A/1 ou B/2)"""
        channel = ctx.channel
        choix = choix.upper()
        data = await self.get_bet(channel)
        if data:
            cash = self.bot.get_cog("Cash")
            curr = await cash.get_currency(ctx.guild)
            if choix in ("1", "A", "2", "B"):
                choix = "A" if choix in ["A", "1"] else "B"
                if not data["votes_open"]:
                    em = await self.get_bet_embed(channel, f"Le choix {choix} remporte le pari !", choix)
                    betmsg = await channel.fetch_message(data["betmsg"])
                    await betmsg.edit(embed=em)

                    votes = data[choix.lower()]["votes"]
                    somme_a = sum([data["a"]["votes"][i] for i in data["a"]["votes"]])
                    somme_b = sum([data["b"]["votes"][i] for i in data["b"]["votes"]])
                    rdm = round(1 + (somme_a / somme_b), 2)
                    for v in votes:
                        user = ctx.guild.get_member(v)
                        if user:
                            retour = int(votes[v] * rdm)
                            solde = await cash.deposit_credits(user, retour)
                            try:
                                em = discord.Embed(title="🎲 **Pari remporté**", description=f"Vous repartez avec **{retour}** {curr}")
                                em.set_footer(text=f"Vous avez désormais {solde} {curr}")
                                await user.send(embed=em)
                            except:
                                pass
                            await cash.add_log(user, "Pari remporté", retour)
                    try:
                        await betmsg.delete()
                    except Exception as e:
                        logger.warning(e, exc_info=True)
                    del self.bets[channel.id]
                else:
                    await ctx.send("**Impossible** • Arrêtez d'abord les votes avec `bet stop` avant d'arrêter les paris")
            else:
                await ctx.send("**Inconnu** • Vous devez désigner un résultat avec 'A' ou 'B' (ou '1' et '2')")
        else:
            await ctx.send("**Aucun pari en cours** • Vous pouvez en démarrer un avec `bet new`")

    @_bet_main.command(name="vote")
    async def vote_bet(self, ctx, choix: str, somme: int):
        """Parier une somme sur un choix (A ou B) d'un pari en cours

        Refaire la commande alors que vous avez déjà voté ajoute la somme à celle déjà pariée pour cette session"""
        choix = choix.upper()
        channel = ctx.channel
        data = await self.get_bet(channel)
        if data:
            cash = self.bot.get_cog("Cash")
            curr = await cash.get_currency(ctx.guild)
            if choix in ("1", "A", "2", "B"):
                choix = "A" if choix in ["A", "1"] else "B"
                if data["votes_open"]:
                    all_votes = [i for i in data["a"]["votes"]] + [i for i in data["b"]["votes"]]
                    if ctx.author.id not in all_votes:
                        if await cash.enough_balance(ctx.author, somme):
                            try:
                                await cash.remove_credits(ctx.author, somme)
                            except:
                                return await ctx.send(f"{ctx.author.mention} **Erreur** • La transaction a échouée")
                            await cash.add_log(ctx.author, "Participation à un pari", -somme)
                            data[choix.lower()]["votes"][ctx.author.id] = somme
                            await ctx.send(f"{ctx.author.mention} **Pari pris en compte** • "
                                           f"Vous avez parié {humanize_number(somme)} {curr} sur **{choix}**")

                            betmsg = await channel.fetch_message(data["betmsg"])
                            await betmsg.edit(embed=await self.get_bet_embed(
                                channel, "Les votes sont fermés | Résultat en attente..."))
                        else:
                            await ctx.send(f"{ctx.author.mention} **Impossible** • Fonds insuffisants dans votre compte")
                    else:
                        if ctx.author.id in [i for i in data[choix.lower()]["votes"]]:
                            if await cash.enough_balance(ctx.author, somme):
                                try:
                                    await cash.remove_credits(ctx.author, somme)
                                except:
                                    return await ctx.send(f"{ctx.author.mention} **Erreur** • La transaction a échouée")
                                await cash.add_log(ctx.author, "Ajout de fonds à un pari", -somme)
                                before = data[choix.lower()]["votes"][ctx.author.id]
                                new = before + somme
                                data[choix.lower()]["votes"][ctx.author.id] = new
                                await ctx.send(f"{ctx.author.mention} **Pari pris en compte** • "
                                               f"Vous avez ajouté {humanize_number(somme)} {curr} à votre pari sur "
                                               f"**{choix}** ({humanize_number(new)} en tout)")

                                betmsg = await channel.fetch_message(data["betmsg"])
                                await betmsg.edit(embed=await self.get_bet_embed(
                                    channel, "Les votes sont fermés | Résultat en attente..."))
                            else:
                                await ctx.send(
                                    f"{ctx.author.mention} **Impossible** • Fonds insuffisants dans votre compte")
                        else:
                            await ctx.send(
                                f"{ctx.author.mention} **Refusé** • Vous pouvez ajouter des fonds à votre premier choix "
                                f"mais pas parier sur les deux choix en même temps ou changer de choix")
                else:
                    await ctx.send(
                        f"{ctx.author.mention} **Impossible** • Les votes sont fermés")
            else:
                await ctx.send(
                    f"{ctx.author.mention} **Invalide** • Choisissez entre A ou B (ou 1/2)")
        else:
            await ctx.send(
                f"{ctx.author.mention} **Aucun pari en cours** • Un modérateur peut en lancer un avec `bet new`")
