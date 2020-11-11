from .checkpoint import Checkpoint

def setup(bot):
    bot.add_cog(Checkpoint(bot))