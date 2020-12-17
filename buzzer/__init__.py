from .buzzer import Buzzer

def setup(bot):
    bot.add_cog(Buzzer(bot))