from .bet import Bet

def setup(bot):
    bot.add_cog(Bet(bot))