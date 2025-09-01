# status_handler.py
import discord
import random

async def update_bot_status(bot):
    statuses = [
        {"type": discord.ActivityType.playing, "text": f"in {len(bot.guilds)} server!"},
        {"type": discord.ActivityType.watching, "text": f"{sum(guild.member_count for guild in bot.guilds)} user!"},
        {"type": discord.ActivityType.listening, "text": "Vibes 🎶🎶🎶"},
        {"type": discord.ActivityType.playing, "text": "Vydra 🎶🎶🎶"},
        {"type": discord.ActivityType.streaming, "text": "Hit Youtube! 🚀", "url": "https://www.youtube.com/"},
        {"type": discord.ActivityType.watching, "text": "Create By @kyy-95631488", "url": "https://github.com/kyy-95631488/"}
    ]
    
    status = random.choice(statuses)
    activity = discord.Activity(type=status["type"], name=status["text"])
    await bot.change_presence(activity=activity)