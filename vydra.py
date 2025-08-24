# vydra.py
import os
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
from status_handler import update_bot_status
from commands.badge import setup_badge_command
from commands.music import setup_music_commands

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Bot logged in as {bot.user}")
    try:
        # Setup commands
        setup_badge_command(bot)
        await setup_music_commands(bot)
        update_status.start()
    except Exception as e:
        print(f"⚠️ Failed to start status update task: {e}")

@tasks.loop(seconds=30)
async def update_status():
    await update_bot_status(bot)

@bot.event
async def on_command_error(ctx, error):
    """Handle command errors gracefully"""
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Command not found. Use `!help` to see available commands.")
    else:
        print(f"⚠️ Error in command {ctx.command}: {error}")
        await ctx.send("❌ An error occurred while executing the command.")

if TOKEN is None:
    raise ValueError("⚠️ DISCORD_TOKEN is not set in environment variables")

bot.run(TOKEN)