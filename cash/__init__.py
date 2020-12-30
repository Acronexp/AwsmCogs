from .cash import Cash

def setup(bot):
    bot.add_cog(Cash(bot))