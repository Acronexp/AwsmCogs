from .favboard import Favboard

def setup(bot):
    bot.add_cog(Favboard(bot))