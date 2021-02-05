from .wingman import Wingman

__red_end_user_data_statement__ = 'This cog store data given from users themselves.'

def setup(bot):
    bot.add_cog(Wingman(bot))