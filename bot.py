import discord
from discord.ext import commands
import logging
import asyncio
import os
from datetime import datetime
from database import Database
from config_manager import ConfigManager
from xp_manager import XPManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class XPBot(commands.Bot):
    def __init__(self):
        # Initialize configuration
        self.config = ConfigManager()
        
        # Initialize database
        self.db = Database()
        
        # Initialize XP manager
        self.xp_manager = XPManager(self, self.db, self.config)
        
        # Set up bot intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        intents.voice_states = True
        
        # Initialize bot with intents
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None
        )
    
    async def setup_hook(self):
        """Set up bot when it starts"""
        logger.info("Setting up bot...")
        
        # Load cogs
        await self.load_extension('cogs.xp_commands')
        await self.load_extension('cogs.message_tracker')
        await self.load_extension('cogs.voice_tracker')
        await self.load_extension('cogs.assistant')
        
        logger.info("All cogs loaded successfully")
    
    async def on_ready(self):
        """Called when bot is ready"""
        logger.info(f"Bot is ready! Logged in as {self.user}")
        logger.info(f"Bot ID: {self.user.id}")
        logger.info(f"Guild ID: {self.config.get_guild_id()}")
        
        # Validate configuration
        issues = self.config.validate_config()
        if issues:
            logger.warning("Configuration issues found:")
            for issue in issues:
                logger.warning(f"  - {issue}")
        else:
            logger.info("Configuration validated successfully")
        
        # Set bot status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="XP gains | !rank"
            )
        )
        
        logger.info("Bot setup complete!")
    
    async def on_command_error(self, ctx, error):
        """Handle command errors"""
        if isinstance(error, commands.CommandNotFound):
            return  # Ignore command not found errors
        
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command!")
            return
        
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing required argument: {error.param}")
            return
        
        if isinstance(error, commands.BadArgument):
            await ctx.send("❌ Invalid argument provided!")
            return
        
        # Log other errors
        logger.error(f"Command error in {ctx.command}: {error}")
        await ctx.send("❌ An error occurred while executing the command.")

async def main():
    """Main function to run the bot"""
    # Create bot instance
    bot = XPBot()
    
    try:
        # Get bot token from config
        token = bot.config.get_bot_token()
        
        if not token or token == "YOUR_BOT_TOKEN_HERE":
            logger.error("Bot token not configured! Please update config.json")
            return
        
        # Start the bot
        logger.info("Starting bot...")
        await bot.start(token)
    
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Error running bot: {e}")
    finally:
        # Clean up
        if not bot.is_closed():
            await bot.close()

if __name__ == "__main__":
    # Run the bot
    asyncio.run(main())
