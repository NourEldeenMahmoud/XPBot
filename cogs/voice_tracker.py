import discord
from discord.ext import commands, tasks
import logging
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

class VoiceTracker(commands.Cog):
    def __init__(self, bot, xp_manager, database, config):
        self.bot = bot
        self.xp_manager = xp_manager
        self.db = database
        self.config = config
        self.voice_tick_task.start()
    
    def cog_unload(self):
        """Clean up when cog is unloaded"""
        self.voice_tick_task.cancel()
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Handle voice state changes"""
        guild = member.guild
        
        # Check if this is the correct guild
        if guild.id != self.config.get_guild_id():
            return
        
        # User joined a voice channel
        if before.channel is None and after.channel is not None:
            await self.handle_voice_join(member, after.channel)
        
        # User left a voice channel
        elif before.channel is not None and after.channel is None:
            await self.handle_voice_leave(member, before.channel)
        
        # User moved between channels
        elif before.channel is not None and after.channel is not None and before.channel != after.channel:
            await self.handle_voice_move(member, before.channel, after.channel)
    
    async def handle_voice_join(self, member, channel):
        """Handle user joining a voice channel"""
        try:
            # Check if channel is whitelisted
            if channel.id not in self.config.get_voice_whitelist():
                return
            
            # Start tracking voice session
            success = self.db.start_voice_session(member.guild.id, member.id, channel.id)
            if success:
                logger.info(f"Started voice session for {member.name} in {channel.name}")
            else:
                logger.error(f"Failed to start voice session for {member.name}")
        
        except Exception as e:
            logger.error(f"Error handling voice join for {member.name}: {e}")
    
    async def handle_voice_leave(self, member, channel):
        """Handle user leaving a voice channel"""
        try:
            # End voice session tracking
            success = self.db.end_voice_session(member.guild.id, member.id)
            if success:
                logger.info(f"Ended voice session for {member.name} from {channel.name}")
            else:
                logger.error(f"Failed to end voice session for {member.name}")
        
        except Exception as e:
            logger.error(f"Error handling voice leave for {member.name}: {e}")
    
    async def handle_voice_move(self, member, old_channel, new_channel):
        """Handle user moving between voice channels"""
        try:
            # Check if new channel is whitelisted
            if new_channel.id not in self.config.get_voice_whitelist():
                # If new channel is not whitelisted, end the session
                await self.handle_voice_leave(member, old_channel)
                return
            
            # Update voice session with new channel
            success = self.db.start_voice_session(member.guild.id, member.id, new_channel.id)
            if success:
                logger.info(f"Updated voice session for {member.name} to {new_channel.name}")
            else:
                logger.error(f"Failed to update voice session for {member.name}")
        
        except Exception as e:
            logger.error(f"Error handling voice move for {member.name}: {e}")
    
    @tasks.loop(seconds=60)  # Check every minute
    async def voice_tick_task(self):
        """Periodic task to award voice XP"""
        try:
            guild_id = self.config.get_guild_id()
            guild = self.bot.get_guild(guild_id)
            
            if not guild:
                logger.warning(f"Guild {guild_id} not found")
                return
            
            # Get all active voice sessions
            active_sessions = self.db.get_active_voice_sessions(guild_id)
            
            for session in active_sessions:
                try:
                    member = guild.get_member(session['user_id'])
                    if not member:
                        # User left the guild, clean up session
                        self.db.end_voice_session(guild_id, session['user_id'])
                        continue
                    
                    channel = guild.get_channel(session['channel_id'])
                    if not channel:
                        # Channel was deleted, clean up session
                        self.db.end_voice_session(guild_id, session['user_id'])
                        continue
                    
                    # Check if user is still in the voice channel
                    if not member.voice or member.voice.channel.id != session['channel_id']:
                        # User left or moved, clean up session
                        self.db.end_voice_session(guild_id, session['user_id'])
                        continue
                    
                    # Check if enough time has passed since last XP tick
                    voice_tick_interval = self.config.get_voice_tick_interval()
                    current_time = datetime.now().timestamp()
                    
                    if current_time - session['last_xp_tick'] >= voice_tick_interval:
                        # Award voice XP
                        result = await self.xp_manager.award_voice_xp(guild, member, channel)
                        
                        if result:
                            logger.info(f"Awarded {result['xp_awarded']} voice XP to {member.name}")
                            
                            # Update voice tick timestamp
                            self.db.update_voice_tick(guild_id, session['user_id'])
                            
                            # Update voice time (calculate actual minutes passed)
                            minutes_passed = int((current_time - session['last_xp_tick']) / 60)
                            if minutes_passed < 1:
                                minutes_passed = 1  # Minimum 1 minute
                            self.db.update_user_voice_time(guild_id, session['user_id'], minutes_passed)
                        
                        # Add small delay to prevent overwhelming the database
                        await asyncio.sleep(0.1)
                
                except Exception as e:
                    logger.error(f"Error processing voice session for user {session['user_id']}: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error in voice tick task: {e}")
    
    @voice_tick_task.before_loop
    async def before_voice_tick_task(self):
        """Wait for bot to be ready before starting voice tick task"""
        await self.bot.wait_until_ready()
        logger.info("Voice tick task started")

async def setup(bot):
    await bot.add_cog(VoiceTracker(bot, bot.xp_manager, bot.db, bot.config))
