# music.py
# music.py
import os
import discord
from discord.ext import commands
import yt_dlp
import asyncio
import logging
from discord.ui import Button, View
import random
import subprocess
import signal
import time

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(__name__)

class AnimatedMusicControls(View):
    def __init__(self, cog, guild_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id
        self.is_playing = False

        # Custom button styles with emojis
        self.play_button = Button(label="Play", style=discord.ButtonStyle.green, emoji="▶️")
        self.play_button.callback = self.play_button_callback

        self.pause_button = Button(label="Pause", style=discord.ButtonStyle.blurple, emoji="⏸️")
        self.pause_button.callback = self.pause_button_callback

        self.skip_button = Button(label="Skip", style=discord.ButtonStyle.red, emoji="⏭️")
        self.skip_button.callback = self.skip_button_callback

        self.stop_button = Button(label="Stop", style=discord.ButtonStyle.red, emoji="⏹️")
        self.stop_button.callback = self.stop_button_callback

        self.volume_up_button = Button(label="Vol Up", style=discord.ButtonStyle.grey, emoji="🔊")
        self.volume_up_button.callback = self.volume_up_button_callback

        self.volume_down_button = Button(label="Vol Down", style=discord.ButtonStyle.grey, emoji="🔉")
        self.volume_down_button.callback = self.volume_down_button_callback

        self.loop_button = Button(label="Loop", style=discord.ButtonStyle.green, emoji="🔁")
        self.loop_button.callback = self.loop_button_callback

        # Set rows for responsive layout
        self.play_button.row = 0
        self.pause_button.row = 0
        self.skip_button.row = 0
        self.stop_button.row = 0
        self.volume_down_button.row = 1
        self.volume_up_button.row = 1
        self.loop_button.row = 1

        self.add_item(self.play_button)
        self.add_item(self.pause_button)
        self.add_item(self.skip_button)
        self.add_item(self.stop_button)
        self.add_item(self.volume_down_button)
        self.add_item(self.volume_up_button)
        self.add_item(self.loop_button)

    async def update_button_states(self, interaction: discord.Interaction):
        voice_client = self.cog.voice_clients.get(self.guild_id)
        self.is_playing = voice_client and voice_client.is_playing()
        self.play_button.disabled = self.is_playing
        self.pause_button.disabled = not self.is_playing
        try:
            await interaction.response.edit_message(view=self)
        except Exception as e:
            logger.error(f"Error updating button states: {e}")

    async def play_button_callback(self, interaction: discord.Interaction):
        voice_client = self.cog.voice_clients.get(self.guild_id)
        if voice_client and voice_client.is_paused():
            voice_client.resume()
            await interaction.response.send_message("Resumed playback", ephemeral=True)
            await self.update_button_states(interaction)
        else:
            await interaction.response.send_message("Nothing is paused", ephemeral=True)

    async def pause_button_callback(self, interaction: discord.Interaction):
        voice_client = self.cog.voice_clients.get(self.guild_id)
        if voice_client and voice_client.is_playing():
            voice_client.pause()
            await interaction.response.send_message("Paused playback", ephemeral=True)
            await self.update_button_states(interaction)
        else:
            await interaction.response.send_message("Nothing is playing", ephemeral=True)

    async def skip_button_callback(self, interaction: discord.Interaction):
        voice_client = self.cog.voice_clients.get(self.guild_id)
        if voice_client:
            voice_client.stop()
            await interaction.response.send_message("Skipped to next track", ephemeral=True)
            await self.update_button_states(interaction)
        else:
            await interaction.response.send_message("No track playing", ephemeral=True)

    async def stop_button_callback(self, interaction: discord.Interaction):
        await self.cog.stop_music(self.guild_id)
        await interaction.response.send_message("Stopped playback and cleared queue", ephemeral=True)
        await self.update_button_states(interaction)

    async def volume_up_button_callback(self, interaction: discord.Interaction):
        self.cog.volumes[self.guild_id] = min(2.0, self.cog.volumes.get(self.guild_id, 1.0) + 0.1)
        voice_client = self.cog.voice_clients.get(self.guild_id)
        if voice_client and voice_client.source:
            voice_client.source.volume = self.cog.volumes[self.guild_id]
            await interaction.response.send_message(f"Volume: {self.cog.volumes[self.guild_id] * 100:.0f}%", ephemeral=True)
        else:
            await interaction.response.send_message("No audio playing", ephemeral=True)

    async def volume_down_button_callback(self, interaction: discord.Interaction):
        self.cog.volumes[self.guild_id] = max(0.0, self.cog.volumes.get(self.guild_id, 1.0) - 0.1)
        voice_client = self.cog.voice_clients.get(self.guild_id)
        if voice_client and voice_client.source:
            voice_client.source.volume = self.cog.volumes[self.guild_id]
            await interaction.response.send_message(f"Volume: {self.cog.volumes[self.guild_id] * 100:.0f}%", ephemeral=True)
        else:
            await interaction.response.send_message("No audio playing", ephemeral=True)

    async def loop_button_callback(self, interaction: discord.Interaction):
        current_mode = self.cog.loop_modes.get(self.guild_id, 0)
        next_mode = (current_mode + 1) % 3
        modes = {0: "Off", 1: "Single", 2: "Queue"}
        self.cog.loop_modes[self.guild_id] = next_mode
        self.loop_button.label = f"Loop {modes[next_mode]}"
        await interaction.response.send_message(f"Loop mode: {modes[next_mode]}", ephemeral=True)
        await interaction.message.edit(view=self)

class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}  # guild_id: list of {'title': str, 'source': PCMVolumeTransformer, 'thumbnail': str, 'duration': int, 'process': Popen}
        self.currents = {}  # guild_id: {'title': str, 'source': PCMVolumeTransformer, 'thumbnail': str, 'duration': int, 'process': Popen}
        self.voice_clients = {}  # guild_id: VoiceClient
        self.loop_modes = {}  # guild_id: 0(off), 1(single), 2(queue)
        self.volumes = {}  # guild_id: float (0.0 - 2.0)
        self.play_messages = {}  # guild_id: Message
        self.animation_tasks = {}  # guild_id: Task for animation
        self.ffmpeg_processes = {}  # guild_id: subprocess.Popen for FFmpeg

    async def get_audio_source(self, query, retries=3):
        for attempt in range(retries):
            try:
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'quiet': True,
                    'no_warnings': True,
                    'noplaylist': True,
                    'source_address': '0.0.0.0',
                    'default_search': 'ytsearch',
                    'max_downloads': 1,
                    'outtmpl': '%(id)s.%(ext)s',
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(query, download=False)
                    if 'entries' in info and info['entries']:
                        entry = info['entries'][0]
                        audio_url = entry.get('url')
                        title = entry.get('title', 'Unknown Title')
                        thumbnail = entry['thumbnails'][0]['url'] if 'thumbnails' in entry and entry['thumbnails'] else None
                        duration = entry.get('duration')
                        if not audio_url:
                            raise Exception("No valid audio URL found in search results")
                    else:
                        audio_url = info.get('url')
                        title = info.get('title', 'Unknown Title')
                        thumbnail = info['thumbnails'][0]['url'] if 'thumbnails' in info and info['thumbnails'] else None
                        duration = info.get('duration')
                        if not audio_url:
                            raise Exception("Could not extract audio URL")
                    logger.info(f"Extracted audio URL: {audio_url} for title: {title}")

                ffmpeg_options = {
                    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -reconnect_on_network_error 1',
                    'options': '-vn -bufsize 32k -maxrate 128k'  # Reduced buffer and bitrate for lower resource usage
                }
                process = subprocess.Popen(
                    ['ffmpeg', '-i', audio_url, '-f', 's16le', '-ar', '48000', '-ac', '2', 'pipe:1'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    preexec_fn=os.setsid  # Use process group for proper cleanup
                )
                # Check if process started successfully
                time.sleep(0.5)  # Short wait to check if process dies immediately
                if process.poll() is not None:
                    err = process.stderr.read().decode()
                    raise Exception(f"FFmpeg process failed to start: {err}")
                source = discord.PCMVolumeTransformer(
                    discord.FFmpegPCMAudio(
                        process.stdout,
                        pipe=True,
                        executable="ffmpeg",
                        **ffmpeg_options
                    ),
                    volume=1.0
                )
                return {'title': title, 'source': source, 'thumbnail': thumbnail, 'duration': duration, 'process': process}
            except Exception as e:
                logger.error(f"Attempt {attempt+1}/{retries} failed for query '{query}': {str(e)}")
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise Exception(f"Failed to create audio source after {retries} attempts: {str(e)}")

    def cleanup_ffmpeg(self, guild_id):
        """Clean up FFmpeg process for a guild with improved handling"""
        if guild_id in self.ffmpeg_processes:
            process = self.ffmpeg_processes[guild_id]
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                process.terminate()
                process.wait(timeout=10)  # Increased timeout
            except subprocess.TimeoutExpired:
                logger.warning(f"Terminate timed out for guild {guild_id}, killing process")
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                process.kill()
                process.wait(timeout=5)
            except Exception as e:
                logger.error(f"Error cleaning up FFmpeg process for guild {guild_id}: {e}")
            finally:
                self.ffmpeg_processes.pop(guild_id, None)

    async def animate_embed(self, guild_id, channel, message):
        colors = [
            discord.Color.red(),
            discord.Color.orange(),
            discord.Color.yellow(),
            discord.Color.green(),
            discord.Color.blue(),
            discord.Color.purple(),
        ]
        i = 0
        while guild_id in self.currents and self.currents[guild_id]:
            try:
                embed = message.embeds[0].copy()
                embed.color = colors[i % len(colors)]
                await message.edit(embed=embed)
                i += 1
                await asyncio.sleep(2)  # Increased interval to reduce CPU usage
            except Exception as e:
                logger.error(f"Animation error in guild {guild_id}: {e}")
                break
        if guild_id in self.animation_tasks:
            del self.animation_tasks[guild_id]

    async def play_next(self, guild_id, text_channel):
        try:
            # Clean up previous FFmpeg process
            self.cleanup_ffmpeg(guild_id)

            loop_mode = self.loop_modes.get(guild_id, 0)
            current = self.currents.get(guild_id)

            if loop_mode == 1 and current:
                self.queues[guild_id].insert(0, current)
            elif loop_mode == 2 and current:
                self.queues[guild_id].append(current)

            if self.queues.get(guild_id):
                self.currents[guild_id] = self.queues[guild_id].pop(0)
                voice_client = self.voice_clients.get(guild_id)
                if voice_client:
                    volume = self.volumes.get(guild_id, 1.0)
                    self.currents[guild_id]['source'].volume = volume
                    self.ffmpeg_processes[guild_id] = self.currents[guild_id].get('process')
                    logger.info(f"Playing: {self.currents[guild_id]['title']} with volume {volume}")

                    embed = discord.Embed(
                        title="Now Playing",
                        description=f"🎵 {self.currents[guild_id]['title']}\n**Queue Position:** 1",
                        color=discord.Color.from_rgb(
                            random.randint(0, 255),
                            random.randint(0, 255),
                            random.randint(0, 255)
                        )
                    )
                    if 'thumbnail' in self.currents[guild_id] and self.currents[guild_id]['thumbnail']:
                        embed.set_thumbnail(url=self.currents[guild_id]['thumbnail'])
                    if 'duration' in self.currents[guild_id] and self.currents[guild_id]['duration']:
                        dur = self.currents[guild_id]['duration']
                        mins, secs = divmod(int(dur), 60)
                        embed.add_field(name="Duration", value=f"{mins}:{secs:02d}", inline=True)
                    embed.set_footer(text="Use the buttons below to control playback")
                    
                    view = AnimatedMusicControls(self, guild_id)
                    if guild_id in self.play_messages:
                        try:
                            await self.play_messages[guild_id].delete()
                        except:
                            pass
                    self.play_messages[guild_id] = await text_channel.send(embed=embed, view=view)

                    if guild_id in self.animation_tasks and not self.animation_tasks[guild_id].done():
                        self.animation_tasks[guild_id].cancel()
                    self.animation_tasks[guild_id] = asyncio.create_task(self.animate_embed(guild_id, text_channel, self.play_messages[guild_id]))

                    def after_play(error):
                        if error:
                            logger.error(f"Playback error in guild {guild_id}: {str(error)}")
                            self.bot.loop.call_soon_threadsafe(asyncio.create_task, text_channel.send(f"Playback error: {str(error)}"))
                        self.bot.loop.call_soon_threadsafe(asyncio.create_task, self.play_next(guild_id, text_channel))
                    voice_client.play(self.currents[guild_id]['source'], after=after_play)
                else:
                    logger.error(f"No voice client found for guild {guild_id}")
                    await text_channel.send("Error: No voice client available.")
                    self.currents.pop(guild_id, None)
                    self.cleanup_ffmpeg(guild_id)
            else:
                self.currents.pop(guild_id, None)
                self.cleanup_ffmpeg(guild_id)
                embed = discord.Embed(
                    title="Queue Ended",
                    description="No more tracks in queue",
                    color=discord.Color.red()
                )
                if guild_id in self.play_messages:
                    try:
                        await self.play_messages[guild_id].delete()
                    except:
                        pass
                await text_channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Error in play_next for guild {guild_id}: {str(e)}")
            self.currents.pop(guild_id, None)
            self.cleanup_ffmpeg(guild_id)
            await text_channel.send(f"Error playing next song: {str(e)}")
            if self.queues.get(guild_id):
                logger.info(f"Attempting to play next song in queue for guild {guild_id}")
                await self.play_next(guild_id, text_channel)

    @commands.command()
    async def join(self, ctx):
        guild_id = ctx.guild.id
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("Kamu harus berada di voice channel dulu.")
            return

        channel = ctx.author.voice.channel
        max_attempts = 5  # Increased attempts for reliability
        for attempt in range(max_attempts):
            try:
                if guild_id in self.voice_clients and self.voice_clients[guild_id].is_connected():
                    if self.voice_clients[guild_id].channel != channel:
                        await self.voice_clients[guild_id].move_to(channel)
                else:
                    self.voice_clients[guild_id] = await channel.connect()
                self.queues.setdefault(guild_id, [])
                self.loop_modes.setdefault(guild_id, 0)
                self.volumes.setdefault(guild_id, 1.0)
                await ctx.send(f"Berhasil join ke voice channel: {channel.name}")
                logger.info(f"Joined voice channel: {channel.name} in guild {guild_id}")
                return
            except discord.errors.ClientException as e:
                logger.error(f"ClientException joining voice channel (attempt {attempt + 1}/{max_attempts}): {str(e)}")
                if attempt < max_attempts - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                continue
            except Exception as e:
                logger.error(f"Error joining voice channel: {str(e)}")
                await ctx.send(f"Terjadi kesalahan: {str(e)}")
                return
        await ctx.send("Gagal join ke voice channel setelah beberapa percobaan.")

    @commands.command()
    async def leave(self, ctx):
        guild_id = ctx.guild.id
        if guild_id in self.play_messages:
            try:
                await self.play_messages[guild_id].delete()
            except:
                pass
            self.play_messages.pop(guild_id, None)
        
        if guild_id in self.animation_tasks:
            self.animation_tasks[guild_id].cancel()
            self.animation_tasks.pop(guild_id, None)
        
        if guild_id in self.voice_clients and self.voice_clients[guild_id].is_connected():
            self.cleanup_ffmpeg(guild_id)
            await self.voice_clients[guild_id].disconnect()
            self.voice_clients.pop(guild_id, None)
            self.queues.pop(guild_id, None)
            self.currents.pop(guild_id, None)
            self.loop_modes.pop(guild_id, None)
            self.volumes.pop(guild_id, None)
            await ctx.send("Keluar dari voice channel.")
            logger.info(f"Left voice channel in guild {guild_id}")
        else:
            await ctx.send("Bot tidak berada di voice channel.")

    @commands.command()
    async def play(self, ctx, *, query):
        guild_id = ctx.guild.id

        if guild_id not in self.voice_clients or not self.voice_clients[guild_id].is_connected():
            if not ctx.author.voice or not ctx.author.voice.channel:
                await ctx.send("Kamu harus berada di voice channel untuk memutar musik.")
                return
            await self.join(ctx)
            if guild_id not in self.voice_clients or not self.voice_clients[guild_id].is_connected():
                await ctx.send("Gagal join ke voice channel.")
                return

        try:
            song = await self.get_audio_source(query)
            self.queues.setdefault(guild_id, []).append(song)
            queue_position = len(self.queues[guild_id])
            embed = discord.Embed(
                title="Added to Queue",
                description=f"🎵 {song['title']}\n**Queue Position:** {queue_position}",
                color=discord.Color.blue()
            )
            if 'thumbnail' in song and song['thumbnail']:
                embed.set_thumbnail(url=song['thumbnail'])
            await ctx.send(embed=embed)
            logger.info(f"Added to queue: {song['title']} at position {queue_position} in guild {guild_id}")
            if not self.voice_clients[guild_id].is_playing() and not self.voice_clients[guild_id].is_paused():
                await self.play_next(guild_id, ctx.channel)
        except Exception as e:
            await ctx.send(f"Error: {str(e)}")
            logger.error(f"Error in play command for query '{query}': {str(e)}")

    @commands.command()
    async def pause(self, ctx):
        guild_id = ctx.guild.id
        if guild_id in self.voice_clients and self.voice_clients[guild_id].is_playing():
            self.voice_clients[guild_id].pause()
            await ctx.send("Dipause.")
            logger.info(f"Paused playback in guild {guild_id}")
        else:
            await ctx.send("Tidak ada yang sedang diputar.")

    @commands.command()
    async def resume(self, ctx):
        guild_id = ctx.guild.id
        if guild_id in self.voice_clients and self.voice_clients[guild_id].is_paused():
            self.voice_clients[guild_id].resume()
            await ctx.send("Dilanjutkan.")
            logger.info(f"Resumed playback in guild {guild_id}")
        else:
            await ctx.send("Tidak ada yang sedang dipause.")

    @commands.command()
    async def stop(self, ctx):
        guild_id = ctx.guild.id
        if guild_id in self.play_messages:
            try:
                await self.play_messages[guild_id].delete()
            except:
                pass
            self.play_messages.pop(guild_id, None)
        await self.stop_music(guild_id)
        await ctx.send("Dihentikan.")
        logger.info(f"Stopped playback in guild {guild_id}")

    async def stop_music(self, guild_id):
        if guild_id in self.play_messages:
            try:
                await self.play_messages[guild_id].delete()
            except:
                pass
            self.play_messages.pop(guild_id, None)
            
        if guild_id in self.animation_tasks:
            self.animation_tasks[guild_id].cancel()
            self.animation_tasks.pop(guild_id, None)
            
        if guild_id in self.voice_clients and self.voice_clients[guild_id].is_connected():
            self.cleanup_ffmpeg(guild_id)
            self.voice_clients[guild_id].stop()
            self.queues[guild_id] = []
            self.currents.pop(guild_id, None)
            logger.info(f"Cleared queue and stopped music in guild {guild_id}")

    @commands.command()
    async def skip(self, ctx):
        guild_id = ctx.guild.id
        if guild_id in self.voice_clients and self.voice_clients[guild_id].is_connected():
            self.cleanup_ffmpeg(guild_id)
            self.voice_clients[guild_id].stop()
            await ctx.send("Dilewati.")
            logger.info(f"Skipped song in guild {guild_id}")
        else:
            await ctx.send("Tidak ada yang sedang diputar.")

    @commands.command()
    async def volume(self, ctx, vol: int):
        guild_id = ctx.guild.id
        if guild_id in self.voice_clients and self.voice_clients[guild_id].is_connected():
            self.volumes[guild_id] = max(0.0, min(2.0, vol / 100))
            if self.voice_clients[guild_id].source:
                self.voice_clients[guild_id].source.volume = self.volumes[guild_id]
            await ctx.send(f"Volume diatur ke {vol}%")
            logger.info(f"Set volume to {vol}% in guild {guild_id}")
        else:
            await ctx.send("Bot tidak berada di voice channel.")

    @commands.command()
    async def loop(self, ctx, mode: str):
        guild_id = ctx.guild.id
        if mode.lower() == 'off':
            self.loop_modes[guild_id] = 0
            await ctx.send("Mode loop: Mati")
        elif mode.lower() == 'single':
            self.loop_modes[guild_id] = 1
            await ctx.send("Mode loop: Single")
        elif mode.lower() == 'queue':
            self.loop_modes[guild_id] = 2
            await ctx.send("Mode loop: Antrian")
        else:
            await ctx.send("Mode tidak valid. Gunakan off, single, atau queue.")
        logger.info(f"Set loop mode to {mode} in guild {guild_id}")

    @commands.command(name='queue')
    async def show_queue(self, ctx):
        guild_id = ctx.guild.id
        if guild_id in self.queues and self.queues[guild_id]:
            queue_list = "\n".join([f"{i+1}. {song['title']}" for i, song in enumerate(self.queues[guild_id])])
            embed = discord.Embed(
                title="Current Queue",
                description=queue_list,
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send("Antrian kosong.")

    @commands.command()
    async def controls(self, ctx):
        guild_id = ctx.guild.id
        if guild_id not in self.voice_clients or not self.voice_clients[guild_id].is_connected():
            await ctx.send("Bot tidak berada di voice channel.")
            return
        embed = discord.Embed(
            title="Music Controls",
            description="Control the music playback using these buttons",
            color=discord.Color.from_rgb(
                random.randint(0, 255),
                random.randint(0, 255),
                random.randint(0, 255)
            )
        )
        view = AnimatedMusicControls(self, guild_id)
        await ctx.send(embed=embed, view=view)
        logger.info(f"Displayed music controls in guild {guild_id}")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if not member.bot:
            for guild_id, vc in list(self.voice_clients.items()):
                if vc.is_connected() and vc.channel:
                    humans = [m for m in vc.channel.members if not m.bot]
                    if len(humans) == 0:
                        if guild_id in self.play_messages:
                            try:
                                await self.play_messages[guild_id].delete()
                            except:
                                pass
                            self.play_messages.pop(guild_id, None)
                        if guild_id in self.animation_tasks:
                            self.animation_tasks[guild_id].cancel()
                            self.animation_tasks.pop(guild_id, None)
                        self.cleanup_ffmpeg(guild_id)
                        await vc.disconnect()
                        self.voice_clients.pop(guild_id, None)
                        self.queues.pop(guild_id, None)
                        self.currents.pop(guild_id, None)
                        self.loop_modes.pop(guild_id, None)
                        self.volumes.pop(guild_id, None)
                        logger.info(f"Disconnected from voice channel in guild {guild_id} due to no human members")

async def setup_music_commands(bot):
    await bot.add_cog(MusicCog(bot))