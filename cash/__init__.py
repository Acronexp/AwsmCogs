from .cash import Cash

__red_end_user_data_statement__ = 'This cog only stores users IDs as needed for operations.'

def setup(bot):
    bot.add_cog(Cash(bot))