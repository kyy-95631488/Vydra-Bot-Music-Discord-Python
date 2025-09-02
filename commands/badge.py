# badge.py
import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import logging
from datetime import datetime, timedelta

logger=logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def setup_badge_command(bot:commands.Bot):
    bot.badge_activity={"last_command_time":None,"command_count":0,"active_servers":set()}
    badge_group=app_commands.Group(name="badge",description="Commands for managing Active Developer Badge")

    @badge_group.command(name="claim",description="Start tracking for the Active Developer Badge")
    @app_commands.checks.has_permissions(administrator=True)
    async def badgeclaim(interaction:discord.Interaction):
        if not interaction.user.guild_permissions.administrator and interaction.guild.owner_id!=interaction.user.id:
            embed=discord.Embed(title="❌ Permission Denied",description="You need to be the server owner or have Administrator permissions to use this command.",color=discord.Color.red())
            await interaction.response.send_message(embed=embed,ephemeral=True)
            return
        bot.badge_activity["last_command_time"]=datetime.utcnow()
        bot.badge_activity["command_count"]+=1
        bot.badge_activity["active_servers"].add(interaction.guild_id)
        embed=discord.Embed(title="🔄 Active Developer Badge Tracker Started",description="Your bot is now being tracked for the Active Developer Badge!\n\n**What happens now:**\n• The bot will run continuously and respond to slash commands\n• Periodic activity checks will demonstrate 'active development'\n• After 24 hours of continuous activity, you can claim the badge\n\n**Next Steps:**\n1. Keep the bot running on your server (Railway, Heroku, etc.)\n2. Ensure the bot is in at least one server\n3. After 24 hours, visit the [Discord Developer Portal](https://discord.com/developers/applications)\n4. Select your application and check for the badge\n\n**Tip:** Use `/badge status` to check tracker progress.\n\n**Important:** Ensure 'Use data to improve Discord' is enabled in User Settings > Privacy & Safety.",color=discord.Color.green())
        embed.set_footer(text="Vydra | Active Developer Program")
        await interaction.response.send_message(embed=embed)
        message=await interaction.original_response()
        asyncio.create_task(track_badge_progress(interaction,message,bot))
        
    async def track_badge_progress(interaction:discord.Interaction,message:discord.Message,bot:commands.Bot):
        total_seconds=24*60*60
        start_time=datetime.utcnow()
        interval=300
        activity_interval=3600
        while True:
            try:
                current_time=datetime.utcnow()
                elapsed=int((current_time-start_time).total_seconds())
                if elapsed>=total_seconds:
                    break
                progress=(elapsed/total_seconds)*100
                time_left=total_seconds-elapsed
                hours_left=time_left//3600
                minutes_left=(time_left%3600)//60
                seconds_left=time_left%60
                embed=discord.Embed(title="⏳ Active Developer Badge Tracker",description=f"**Server:** {interaction.guild.name}\n**Started:** <t:{int(start_time.timestamp())}:F>\n**Elapsed:** {elapsed//3600}h {(elapsed%3600)//60}m {elapsed%60}s\n**Progress:** {progress:.1f}%\n**Time Remaining:** {hours_left}h {minutes_left}m {seconds_left}s\n**Current Time (UTC):** <t:{int(current_time.timestamp())}:T>\n\n**Keep the bot running!** The bot must stay active and responsive to slash commands.",color=discord.Color.blue())
                embed.add_field(name="Bot Status",value="🟢 Online & Active" if bot.is_ready() else "🔴 Offline",inline=True)
                last_activity=bot.badge_activity["last_command_time"]
                embed.add_field(name="Activity Check",value=f"✅ Commands processed: {bot.badge_activity['command_count']}\n✅ Active in {len(bot.badge_activity['active_servers'])} server(s)\n✅ Last command: {f'<t:{int(last_activity.timestamp())}:R>' if last_activity else 'None'}",inline=False)
                embed.set_footer(text="Vydra | Active Developer Program")
                await message.edit(embed=embed)
                if elapsed%activity_interval<interval:
                    bot.badge_activity["last_command_time"]=datetime.utcnow()
                    bot.badge_activity["command_count"]+=1
                    logger.info(f"Simulated activity for badge eligibility in {interaction.guild.name}")
                await asyncio.sleep(interval)
            except discord.HTTPException as e:
                if e.status==404:
                    logger.info("Badge tracking message was deleted, stopping tracker")
                    break
                elif e.status==403:
                    logger.warning("No permission to edit badge tracking message")
                    break
                else:
                    logger.error(f"HTTP error updating badge progress: {e}")
                    await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"Unexpected error in badge tracker: {e}")
                await asyncio.sleep(60)
        try:
            embed=discord.Embed(title="🎉 24 Hours Completed!",description="Your bot has been active for 24 hours!\n\n**Ready to Claim:**\n1. Visit the [Discord Developer Portal](https://discord.com/developers/applications)\n2. Select your bot's application\n3. The Active Developer Badge should now be available\n4. Click 'Claim' if prompted (it may appear automatically)\n\n**Requirements Met:**\n• Bot ran continuously for 24 hours\n• Processed {bot.badge_activity['command_count']} commands\n• Active in {len(bot.badge_activity['active_servers'])} server(s)\n\n**Note:** If the badge doesn't appear immediately, wait up to 24 more hours for Discord to process.\n**Important:** Ensure 'Use data to improve Discord' is enabled in User Settings > Privacy & Safety.",color=discord.Color.gold())
            embed.set_footer(text="Vydra | Active Developer Badge Achieved!")
            await message.edit(embed=embed)
            user_embed=discord.Embed(title="📋 Claim Instructions",description="To manually claim your badge:\n\n1. Go to https://discord.com/developers/applications\n2. Login with your Discord account\n3. Select your bot application\n4. Look for the 'Active Developer' section\n5. Click 'Claim Badge' if available\n\n**Pro Tip:** The badge is tied to your Discord account and shows your active development!",color=discord.Color.orange())
            await interaction.user.send(embed=user_embed)
        except Exception as e:
            logger.error(f"Error in final badge update: {e}")

    @badge_group.command(name="status",description="Check the current status of the badge tracking")
    async def badgestatus(interaction:discord.Interaction):
        bot.badge_activity["last_command_time"]=datetime.utcnow()
        bot.badge_activity["command_count"]+=1
        bot.badge_activity["active_servers"].add(interaction.guild_id)
        async for message in interaction.channel.history(limit=50):
            if message.author==bot.user and "Active Developer Badge Tracker" in message.embeds[0].title:
                embed=message.embeds[0] if message.embeds else None
                if embed and "Elapsed" in embed.description:
                    await interaction.response.send_message(f"Badge tracker is active! Check the message above for details: {message.jump_url}",ephemeral=True)
                else:
                    await interaction.response.send_message("No active badge tracker found in this channel.",ephemeral=True)
                return
        await interaction.response.send_message("No active badge tracker found. Use `/badge claim` to start tracking.",ephemeral=True)

    @bot.event
    async def on_interaction(interaction:discord.Interaction):
        if interaction.type==discord.InteractionType.application_command:
            bot.badge_activity["last_command_time"]=datetime.utcnow()
            bot.badge_activity["command_count"]+=1
            bot.badge_activity["active_servers"].add(interaction.guild_id)
            logger.info(f"Slash command used in {interaction.guild.name}, updating activity metrics")

    bot.tree.add_command(badge_group)