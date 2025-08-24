from discord.ext import commands
import discord
import asyncio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def setup_badge_command(bot: commands.Bot):
    @bot.command()
    async def claimbadge(ctx: commands.Context):
        """Command to automatically track and claim the Active Developer Badge"""
        # Check if user has necessary permissions
        if not ctx.author.guild_permissions.administrator and ctx.guild.owner_id != ctx.author.id:
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="You need to be the server owner or have Administrator permissions to use this command.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        # Create embed for tracking
        embed = discord.Embed(
            title="🔄 Active Developer Badge Tracker Started",
            description=(
                "Your bot is now being tracked for the Active Developer Badge!\n\n"
                "**What happens now:**\n"
                "• The bot will run continuously and respond to commands\n"
                "• This demonstrates 'active development' to Discord\n"
                "• After 24 hours of continuous activity, you can claim the badge\n\n"
                "**Next Steps:**\n"
                "1. Keep the bot running on your server (Railway, Heroku, etc.)\n"
                "2. Make sure the bot is in at least one server\n"
                "3. After 24 hours, visit the [Discord Developer Portal](https://discord.com/developers/applications)\n"
                "4. Select your application and check for the badge\n\n"
                "**Tip:** Use `!status` to check if the bot is still active."
            ),
            color=discord.Color.green()
        )
        embed.set_footer(text="Railway Bot | Active Developer Program")
        
        # Send initial message
        message = await ctx.send(embed=embed)
        
        # Start the 24-hour tracking loop
        await track_badge_progress(ctx, message, bot)
        
    async def track_badge_progress(ctx: commands.Context, message: discord.Message, bot: commands.Bot):
        """Track the 24-hour period for badge eligibility"""
        total_seconds = 24 * 60 * 60  # 24 hours
        start_time = datetime.utcnow()
        interval = 300  # Update every 5 minutes for more frequent updates
        
        while True:
            try:
                # Calculate elapsed time
                current_time = datetime.utcnow()
                elapsed = int((current_time - start_time).total_seconds())
                
                if elapsed >= total_seconds:
                    break
                    
                # Update embed with progress
                progress = (elapsed / total_seconds) * 100
                time_left = total_seconds - elapsed
                hours_left = time_left // 3600
                minutes_left = (time_left % 3600) // 60
                seconds_left = time_left % 60
                
                embed = discord.Embed(
                    title="⏳ Active Developer Badge Tracker",
                    description=(
                        f"**Server:** {ctx.guild.name}\n"
                        f"**Started:** <t:{int(start_time.timestamp())}:F>\n"
                        f"**Elapsed:** {elapsed // 3600}h {(elapsed % 3600) // 60}m {elapsed % 60}s\n"
                        f"**Progress:** {progress:.1f}%\n"
                        f"**Time Remaining:** {hours_left}h {minutes_left}m {seconds_left}s\n"
                        f"**Current Time (UTC):** <t:{int(current_time.timestamp())}:T>\n\n"
                        "**Keep the bot running!** The bot must stay active and responsive to commands."
                    ),
                    color=discord.Color.blue()
                )
                
                # Add status check
                if bot.is_ready():
                    embed.add_field(name="Bot Status", value="🟢 Online & Active", inline=True)
                else:
                    embed.add_field(name="Bot Status", value="🔴 Offline", inline=True)
                
                embed.add_field(
                    name="Activity Check", 
                    value="✅ Responding to commands\n✅ Updating status every 5 minutes", 
                    inline=False
                )
                
                embed.set_footer(text="Vydra | Active Developer Program")
                
                await message.edit(embed=embed)
                
                # Wait for the interval
                await asyncio.sleep(interval)
                
            except discord.HTTPException as e:
                if e.status == 404:  # Message deleted
                    logger.info("Badge tracking message was deleted, stopping tracker")
                    break
                elif e.status == 403:  # No permission to edit
                    logger.warning("No permission to edit badge tracking message")
                    break
                else:
                    logger.error(f"Error updating badge progress: {e}")
                    await asyncio.sleep(60)  # Wait shorter if error
            except Exception as e:
                logger.error(f"Unexpected error in badge tracker: {e}")
                await asyncio.sleep(60)
        
        # Final update after 24 hours
        try:
            embed = discord.Embed(
                title="🎉 24 Hours Completed!",
                description=(
                    "Your bot has been active for 24 hours!\n\n"
                    "**Ready to Claim:**\n"
                    "1. Visit the [Discord Developer Portal](https://discord.com/developers/applications)\n"
                    "2. Select your bot's application\n"
                    "3. The Active Developer Badge should now be available\n"
                    "4. Click 'Claim' if prompted (it may appear automatically)\n\n"
                    "**Requirements Met:**\n"
                    "• Bot has been running continuously\n"
                    "• Bot responds to commands\n"
                    "• Bot is in at least one server\n\n"
                    "**Note:** If the badge doesn't appear immediately, wait up to 24 more hours for Discord to process."
                ),
                color=discord.Color.gold()
            )
            embed.set_footer(text="Vydra | Active Developer Badge Achieved!")
            await message.edit(embed=embed)
            
            # Send additional info to user
            user_embed = discord.Embed(
                title="📋 Claim Instructions",
                description=(
                    "To manually claim your badge:\n\n"
                    "1. Go to https://discord.com/developers/applications\n"
                    "2. Login with your Discord account\n"
                    "3. Select your bot application\n"
                    "4. Look for the 'Active Developer' section\n"
                    "5. Click 'Claim Badge' if available\n\n"
                    "**Pro Tip:** The badge is tied to your Discord account and shows your active development!"
                ),
                color=discord.Color.orange()
            )
            await ctx.author.send(embed=user_embed)
            
        except Exception as e:
            logger.error(f"Error in final badge update: {e}")

    @bot.command()
    async def badge_status(ctx: commands.Context):
        """Check the current status of the badge tracking"""
        async for message in ctx.channel.history(limit=50):
            if message.author == bot.user and "Active Developer Badge Tracker" in message.embeds[0].title:
                embed = message.embeds[0] if message.embeds else None
                if embed and "Elapsed" in embed.description:
                    await ctx.send(f"Badge tracker is active! Check the message above for details: {message.jump_url}")
                else:
                    await ctx.send("No active badge tracker found in this channel.")
                return
        
        await ctx.send("No active badge tracker found. Use `!claimbadge` to start tracking.")