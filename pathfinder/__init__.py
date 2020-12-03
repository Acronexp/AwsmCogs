from .pathfinder import Pathfinder

def setup(bot):
    bot.add_cog(Pathfinder(bot))