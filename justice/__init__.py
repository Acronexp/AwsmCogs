from .justice import Justice

__red_end_user_data_statement__ = 'This cog does not persistently store user data.'

def setup(bot):
    bot.add_cog(Justice(bot))