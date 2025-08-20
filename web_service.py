from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
import logging
from typing import Dict, List, Optional
import os
from database import Database
from config_manager import ConfigManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="XPBot Web Service",
    description="Web service for Discord XP Bot",
    version="1.0.0"
)

# Global variables for database and config
db: Optional[Database] = None
config: Optional[ConfigManager] = None

@app.on_event("startup")
async def startup_event():
    """Initialize database and config on startup"""
    global db, config
    
    try:
        # Initialize configuration
        config = ConfigManager()
        
        # Initialize database
        db = Database()
        
        logger.info("Web service started successfully")
    except Exception as e:
        logger.error(f"Error starting web service: {e}")
        raise

@app.get("/")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "bot": "running",
        "service": "XPBot Web Service",
        "version": "1.0.0"
    }

@app.get("/leaderboard")
async def get_leaderboard(limit: int = 10):
    """Get permanent leaderboard data"""
    if not db or not config:
        raise HTTPException(status_code=500, detail="Service not initialized")
    
    try:
        if limit > 50:
            limit = 50
        elif limit < 1:
            limit = 10
        
        guild_id = config.get_guild_id()
        leaderboard = db.get_leaderboard(guild_id, limit)
        
        # Format the response
        formatted_leaderboard = []
        for entry in leaderboard:
            formatted_leaderboard.append({
                "rank": entry['rank'],
                "user_id": entry['user_id'],
                "permanent_xp": entry['permanent_xp'],
                "level": entry['level']
            })
        
        return {
            "leaderboard": formatted_leaderboard,
            "total_entries": len(formatted_leaderboard),
            "guild_id": guild_id
        }
    
    except Exception as e:
        logger.error(f"Error getting leaderboard: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/weeklyboard")
async def get_weekly_leaderboard(limit: int = 10):
    """Get weekly leaderboard data"""
    if not db or not config:
        raise HTTPException(status_code=500, detail="Service not initialized")
    
    try:
        if limit > 50:
            limit = 50
        elif limit < 1:
            limit = 10
        
        guild_id = config.get_guild_id()
        leaderboard = db.get_weekly_leaderboard(guild_id, limit)
        
        # Format the response
        formatted_leaderboard = []
        for entry in leaderboard:
            formatted_leaderboard.append({
                "rank": entry['rank'],
                "user_id": entry['user_id'],
                "weekly_xp": entry['weekly_xp']
            })
        
        return {
            "leaderboard": formatted_leaderboard,
            "total_entries": len(formatted_leaderboard),
            "guild_id": guild_id
        }
    
    except Exception as e:
        logger.error(f"Error getting weekly leaderboard: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/user/{user_id}")
async def get_user_stats(user_id: int):
    """Get user statistics"""
    if not db or not config:
        raise HTTPException(status_code=500, detail="Service not initialized")
    
    try:
        guild_id = config.get_guild_id()
        user_data = db.get_user(guild_id, user_id)
        
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Calculate level
        from xp_manager import XPManager
        xp_manager = XPManager(None, db, config)
        level = xp_manager.calculate_level(user_data['permanent_xp'])
        
        # Get ranks
        permanent_rank = db.get_user_rank(guild_id, user_id)
        weekly_rank = db.get_user_weekly_rank(guild_id, user_id)
        
        return {
            "user_id": user_id,
            "permanent_xp": user_data['permanent_xp'],
            "weekly_xp": user_data['weekly_xp'],
            "level": level,
            "permanent_rank": permanent_rank,
            "weekly_rank": weekly_rank
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/stats")
async def get_bot_stats():
    """Get overall bot statistics"""
    if not db or not config:
        raise HTTPException(status_code=500, detail="Service not initialized")
    
    try:
        guild_id = config.get_guild_id()
        
        # Get total users
        conn = db.db_path
        import sqlite3
        with sqlite3.connect(conn) as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM users WHERE guild_id = ?", (guild_id,))
            total_users = cursor.fetchone()[0]
            
            cursor.execute("SELECT SUM(permanent_xp) FROM users WHERE guild_id = ?", (guild_id,))
            total_xp = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT SUM(weekly_xp) FROM users WHERE guild_id = ?", (guild_id,))
            total_weekly_xp = cursor.fetchone()[0] or 0
        
        return {
            "total_users": total_users,
            "total_xp": total_xp,
            "total_weekly_xp": total_weekly_xp,
            "guild_id": guild_id
        }
    
    except Exception as e:
        logger.error(f"Error getting bot stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/config")
async def get_config():
    """Get current bot configuration (read-only)"""
    if not config:
        raise HTTPException(status_code=500, detail="Service not initialized")
    
    try:
        return {
            "xp_settings": {
                "message_xp_min": config.get_message_xp_min(),
                "message_xp_max": config.get_message_xp_max(),
                "message_cooldown_seconds": config.get_message_cooldown(),
                "voice_xp_min": config.get_voice_xp_min(),
                "voice_xp_max": config.get_voice_xp_max(),
                "voice_tick_interval_seconds": config.get_voice_tick_interval()
            },
            "channels": {
                "message_whitelist_count": len(config.get_message_whitelist()),
                "voice_whitelist_count": len(config.get_voice_whitelist())
            },
            "role_rewards_count": len(config.get_role_rewards()),
            "exempt_roles_count": len(config.get_exempt_roles())
        }
    
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    # Get port from environment variable (for Render)
    port = int(os.environ.get("PORT", 8000))
    
    # Run the web service
    uvicorn.run(
        "web_service:app",
        host="0.0.0.0",
        port=port,
        reload=False
    )
