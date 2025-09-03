# vydra.py
import os
import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio
import aiohttp
import logging
from dotenv import load_dotenv
from status_handler import update_bot_status
from commands.music import setup_music_commands

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Set up Discord bot intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

async def check_token(token: str) -> bool:
    """Check if the provided Discord bot token is valid."""
    if not token:
        return False
    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://discord.com/api/v10/users/@me",
            headers={"Authorization": f"Bot {token}"}
        ) as response:
            return response.status == 200

def setup_badge_command(bot: commands.Bot):
    """Set up badge-related slash commands."""
    badge_group = app_commands.Group(name="badge", description="Commands for managing Active Developer Badge")

    @badge_group.command(name="active", description="Get the Discord Active Developer Badge")
    async def badge_active(interaction: discord.Interaction):
        """Handle the /active slash command to help users claim the Active Developer Badge."""
        bot.badge_activity["last_command_time"] = discord.utils.utcnow()
        bot.badge_activity["command_count"] += 1
        bot.badge_activity["active_servers"].add(interaction.guild_id)
        
        embed = discord.Embed(
            title="You have successfully ran the slash command!",
            description=(
                "- Go to *https://discord.com/developers/active-developer* and claim your badge\n"
                "- Verification can take up to 24 hours, so wait patiently until you get your badge"
            ),
            color=0x34DB98
        )
        embed.set_author(
            name="Discord Active Developer Badge",
            icon_url="https://cdn.discordapp.com/emojis/1040325165512396830.webp?size=64&quality=lossless"
        )
        embed.set_footer(
            text="Made by @Kyy",
            icon_url="https://cdn.discordapp.com/emojis/1040325165512396830.webp?size=64&quality=lossless"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"Slash command /active used in {interaction.guild.name}")

    bot.tree.add_command(badge_group)

@bot.event
async def on_ready():
    """Handle bot startup, command syncing, and initial setup."""
    print(f"✅ Bot logged in as {bot.user}")
    print("✔ Use this link to add your bot to your server: "
          f"https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&scope=applications.commands%20bot")
    
    # Initialize badge activity tracking
    bot.badge_activity = {
        "last_command_time": None,
        "command_count": 0,
        "active_servers": set()
    }
    
    try:
        # Set up badge and music commands
        setup_badge_command(bot)
        await setup_music_commands(bot)
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} application command(s)")
        print("✔ Go to your Discord Server (where you added your bot) and use the slash command /active")
        update_status.start()
    except Exception as e:
        print(f"⚠️ Failed to start status update task or sync commands: {e}")

@tasks.loop(seconds=30)
async def update_status():
    """Periodically update the bot's status."""
    await update_bot_status(bot)

@bot.event
async def on_command_error(ctx, error):
    """Handle command errors."""
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Command not found. Use `!help` or try slash commands like `/badge active`.")
    else:
        print(f"⚠️ Error in command {ctx.command}: {error}")
        await ctx.send("❌ An error occurred while executing the command.")

@bot.event
async def on_interaction(interaction: discord.Interaction):
    """Track slash command interactions for badge activity."""
    if interaction.type == discord.InteractionType.application_command:
        bot.badge_activity["last_command_time"] = discord.utils.utcnow()
        bot.badge_activity["command_count"] += 1
        bot.badge_activity["active_servers"].add(interaction.guild_id)
        logger.info(f"Slash command used in {interaction.guild.name}, updating activity metrics")

async def main():
    """Main function to start the bot and perform initial checks."""
    print("Discord Active Developer Badge")
    print("Remember to do not share your Discord Bot token with anyone!\n")
    print("This tool will help you to get the Discord Active Developer Badge")
    print("If you have any problem, please contact me on Discord: majonez.exe\n")

    # Check if token is valid
    if not await check_token(TOKEN):
        print("✖ Invalid Discord Bot token!")
        return

    print("\nRunning Discord Bot...")
    try:
        await bot.start(TOKEN)
    except Exception as e:
        print(f"Error while logging in to Discord: {e}")
        return

if __name__ == "__main__":
    if TOKEN is None:
        raise ValueError("⚠️ DISCORD_TOKEN is not set in environment variables")
    asyncio.run(main())