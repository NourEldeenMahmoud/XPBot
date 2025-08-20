import discord
from discord.ext import commands
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class MessageTracker(commands.Cog):
    def __init__(self, bot, xp_manager, database, config):
        self.bot = bot
        self.xp_manager = xp_manager
        self.db = database
        self.config = config
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Handle message events for XP awarding"""
        # Ignore bot messages
        if message.author.bot:
            return
        
        # Check if message is in a guild
        if not message.guild:
            return
        
        # Check if this is the correct guild
        if message.guild.id != self.config.get_guild_id():
            return
        
        # Check if channel is whitelisted
        if message.channel.id not in self.config.get_message_whitelist():
            return
        
        # Award XP for message
        try:
            result = await self.xp_manager.award_message_xp(
                message.guild, 
                message.author, 
                message.channel
            )
            
            if result:
                logger.info(f"Awarded {result['xp_awarded']} message XP to {message.author.name}")
                
                # Update message count
                self.db.update_user_message_count(message.guild.id, message.author.id, 1)
                
                # Log level up if it occurred
                if result['leveled_up']:
                    logger.info(f"{message.author.name} leveled up from {result['old_level']} to {result['new_level']}")
        
        except Exception as e:
            logger.error(f"Error awarding message XP to {message.author.name}: {e}")

async def setup(bot):
    await bot.add_cog(MessageTracker(bot, bot.xp_manager, bot.db, bot.config))
