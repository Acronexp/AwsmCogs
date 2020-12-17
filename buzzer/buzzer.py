from datetime import datetime, timedelta
import logging
import random
import string

import discord
from fuzzywuzzy import process
from redbot.core import Config, commands, checks

logger = logging.getLogger("red.AwsmCogs.buzzer")


class Buzzer(commands.Cog):
    """Simple système de buzzer pour les évènements type Quizz etc."""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=736144321857978388, force_registration=True)

        default_guild = {}
        self.config.register_guild(**default_guild)
        self.sessions = {}

    def gen_key(self):
        key = ''.join(random.choices(string.ascii_uppercase, k=3))
        while key in self.sessions:
            key = ''.join(random.choices(string.ascii_uppercase, k=3))
        return key

    def get_channel_buzzer(self, channel: discord.TextChannel):
        for sess in self.sessions:
            if channel.id == self.sessions[sess]["channel"]:
                return self.sessions[sess]
        return None

    def create_buzzer(self, channel: discord.TextChannel, start: bool):
        key = self.gen_key()
        if not self.get_channel_buzzer(channel):
            self.sessions[key] = {"channel": channel.id,
                                  "running": start,
                                  "answer_delay": 20,
                                  "mode": "tour",
                                  "cooldown_delay": 60}
            return key
        raise KeyError("Le channel visé possède déjà un buzzer en cours de fonctionnement.")

    def find_buzzer_team(self, buzzer: str, search: str):
        if buzzer in self.sessions:
            if "teams" in self.sessions[buzzer]:
                names = [i for i in self.sessions[buzzer]]
                result = process.extractOne(search, names, score_cutoff=80)
                if result:
                    return result[0]
                return None
            raise KeyError("Aucune team n'est présente sur ce buzzer")
        raise KeyError("Le buzzer n'existe pas")

    def find_user_team(self, buzzer: str, user: discord.Member):
        if buzzer in self.sessions:
            if "teams" in self.sessions[buzzer]:
                for t in self.sessions[buzzer]["teams"]:
                    if user.id in self.sessions[buzzer]["teams"][t]:
                        return t
                return None
            raise KeyError("Aucune team n'est présente sur ce buzzer")
        raise KeyError("Le buzzer n'existe pas")

    @commands.group(name="buzzer")
    @commands.guild_only()
    async def _buzzer_session(self, ctx):
        """Création et gestion des session de buzzer"""

    @_buzzer_session.command(name="new")
    async def new_buzzer(self, ctx, channel: discord.TextChannel = None):
        """Créer une session de buzzer sur un salon écrit sans le lancer immédiatement

        Par défaut la session est créée sur le salon de la commande"""
        try:
            key = self.create_buzzer(channel, False)
            await ctx.send(f"**Buzzer créé** • L'identifiant de votre buzzer est **{key}**\n"
                           f"Modifiez les paramètres de votre buzzer avec les différentes commandes disponibles dans `;buzzer`")
        except Exception as e:
            await ctx.send(f"**Erreur** • {e}")

    @_buzzer_session.command(name="start", aliases=["stop"])
    async def startstop_buzzer(self, ctx, buzzer: str):
        """Lance/arrête un buzzer préexistant

        Vous pouvez créer en avance un buzzer avec `;buzzer new`
        Cette commande sert à la fois à le lancer et à l'arrêter"""
        if buzzer in self.sessions:
            if self.sessions[buzzer]["running"]:
                self.sessions[buzzer]["running"] = False
                await ctx.send(f"**Buzzer arrêté** • Il ne réagira plus aux messages. Supprimez-le avec `;buzzer delete {buzzer}`")
            else:
                self.sessions[buzzer]["running"] = True
                await ctx.send(
                    f"**Buzzer démarré** • Il va désormais réagir et donner un délai automatiquement à ceux qui commenceront à écrire en premier, selon les paramètres définis.\n"
                    f"Arrêtez-le avec `;buzzer stop {buzzer}` si besoin.")
        else:
            await ctx.send(
                f"**Inconnu** • Cet identifiant de buzzer n'existe pas.")

    @_buzzer_session.command(name="delai")
    async def buzzer_delay(self, ctx, buzzer: str, delai: int = 20):
        """Modifie le temps en secondes pendant lequel la personne ayant 'buzzé' peut répondre avant qu'il expire

        Par défaut cette valeur est à 20s."""
        if buzzer in self.sessions:
            if 0 < delai:
                self.sessions[buzzer]["answer_delay"] = delai
                await ctx.send(
                    f"**Délai de buzzer modifié** • Les membres ayant buzzé auront {delai} secondes pour répondre")
            else:
                await ctx.send(
                    f"**Délai invalide** • Le délai doit être supérieur à 0")
        else:
            await ctx.send(
                f"**Buzzer inconnu** • Cet identifiant de buzzer n'existe pas")

    @_buzzer_session.command(name="mode")
    async def buzzer_mode(self, ctx, buzzer: str, mode: str = None):
        """Modifie le mode de fonctionnement du buzzer

        Ne rien mettre permet d'avoir une liste et une explication des modes de fonctionnement du buzzer"""
        if buzzer in self.sessions:
            if mode:
                if mode.lower() in ["tour", "cooldown"]:
                    self.sessions[buzzer]["mode"] = mode.lower()
                    await ctx.send(
                        f"**Mode modifié** • Le buzzer fonctionnera sous le mode *{mode.lower()}*")
                else:
                    await ctx.send(
                        f"**Mode inconnu** • Ce mode n'existe pas")
            else:
                hlp = "- `Tour` = Chaque membre/team a le droit à une chance à chaque manche, " \
                      "si la réponse est la mauvaise le membre/team ne pourra plus répondre avant la prochaine manche.\n" \
                      "- `Cooldown` = Les membres/teams ont autant de tentatives que nécessaire mais il y a un cooldown (temps de pause) entre deux buzz. " \
                      "Changer de manche reset les cooldown des membres/teams."
                em = discord.Embed(title="Différents modes du Buzzer", description=hlp)
                await ctx.send(embed=em)
        else:
            await ctx.send(
                f"**Buzzer inconnu** • Cet identifiant de buzzer n'existe pas")

    @_buzzer_session.command(name="teams")
    async def buzzer_teams(self, ctx, buzzer: str, *teams):
        """Ajoute/modifie les teams pour le buzzer

        Entrez la liste des teams avec chaque nom séparé par un slash (`/`)
        Si aucune team n'est rentrée, affiche les teams actuellement enregistrées dans le buzzer visé
        Attention : toute modification entraine un reset pur et simple des teams"""
        buzzer = buzzer.upper()
        color = await self.bot.get_embed_color(ctx.channel)
        if teams:
            if "/" in teams:
                if buzzer in self.sessions:
                    teams = [i.strip() for i in " ".join(teams).split("/")]
                    txt = ""
                    for t in teams:
                        txt += f"• {t}\n"
                    if txt:
                        txt += "\n> **Ajouter/retirer des gens aux teams**\n" \
                               "> `;buzzer teamadd buzzerid @user nomteam`\n" \
                               "> `;buzzer teamrem buzzerid @user nomteam`"
                        em = discord.Embed(title=f"Teams du buzzer #{buzzer}", description=txt, color=color)
                        em.set_footer(text="Changements enregistrés avec succès.")
                        await ctx.send(embed=em)
                        self.sessions[buzzer]["teams"] = {t: [] for t in teams}
                    else:
                        await ctx.send("**Erreur** • Noms de teams invalides")
                else:
                    await ctx.send("**Erreur** • Identifiant de buzzer inconnu (il est composé de 3 lettres majuscules)")
            else:
                await ctx.send("**Erreur** • Il ne peut y avoir qu'une seule équipe")
        elif buzzer in self.sessions:
            if "teams" in self.sessions[buzzer]:
                teams = self.sessions[buzzer]["teams"]
                txt = ""
                for t in teams:
                    txt += f"• {t}\n"
                if txt:
                    txt += "\n> **Ajouter/retirer des gens aux teams**\n" \
                           "> `;buzzer teamadd buzzerid @user nomteam`\n" \
                           "> `;buzzer teamrem buzzerid @user`"
                    em = discord.Embed(title=f"Teams du buzzer #{buzzer}", description=txt, color=color)
                    em.set_footer(text="Changements enregistrés avec succès.")
                    await ctx.send(embed=em)
                else:
                    await ctx.send("**Erreur** • Noms de teams invalides")
            else:
                await ctx.send("**Vide** • Aucune team n'a été ajoutée à ce buzzer")
        else:
            await ctx.send("**Inconnu** • Cet identifiant de buzzer est inconnu")

    @_buzzer_session.command(name="teamsreset")
    async def buzzer_teams_reset(self, ctx, buzzer: str):
        """Retire toutes les teams d'un buzzer

        Attention : faire ça supprime les scores des équipes et donc des membres dans ces équipes !"""
        if buzzer in self.sessions:
            if "teams" in self.sessions[buzzer]:
                del self.sessions[buzzer]["teams"]
                await ctx.send("**Succès** • Les teams du buzzer ont été supprimées")
            else:
                await ctx.send("**Vide** • Aucune team n'a été ajoutée à ce buzzer")
        else:
            await ctx.send("**Erreur** • Identifiant de buzzer inconnu")

    @_buzzer_session.command(name="teamadd")
    async def buzzer_team_add(self, ctx, buzzer: str, user: discord.Member, *teamname):
        """Ajoute un membre à une team du buzzer

        Il faut que la team pré-existe à cet ajout, et le membre ne doit pas déjà être dans une autre team"""
        if teamname:
            try:
                teamname = " ".join(teamname)
                team = self.find_buzzer_team(buzzer, teamname)
                if team:
                    if not self.find_user_team(buzzer, user):
                        self.sessions[buzzer]["teams"][team].append(user.id)
                        await ctx.send(f"**Membre ajouté** • {user.mention} est désormais dans ***{team}***")
                    else:
                        await ctx.send(f"**Déjà dans une équipe** • {user.mention} est déjà dans une autre team. Utilisez `;buzzer teamrem @{user.name}` pour l'en retirer")
                else:
                    await ctx.send(f"**Team introuvable** • Essayez de vous rapprocher un peu plus de son orthographe")
            except Exception as e:
                await ctx.send(f"**Erreur** • {e}")
        else:
            await ctx.send("**Erreur** • Vous n'avez pas entré de nom de team (vous n'êtes pas obligé de le rentrer parfaitement)")

    @_buzzer_session.command(name="teamrem")
    async def buzzer_team_remove(self, ctx, buzzer: str, user: discord.Member):
        """Retire un membre d'une team du buzzer (recherche auto. de sa team)

        Il faut que la team pré-existe à cet ajout, et le membre doit être dans une team du buzzer"""
        try:
            team = self.find_user_team(buzzer, user)
            if team:
                self.sessions[buzzer]["teams"][team].remove(user.id)
                await ctx.send(f"**Membre retiré** • {user.mention} n'est plus dans ***{team}***")
            else:
                await ctx.send(f"**Inconnu** • {user.mention} n'est dans aucune team")
        except Exception as e:
            await ctx.send(f"**Erreur** • {e}")

