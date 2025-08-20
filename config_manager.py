import json
import logging
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class ConfigManager:
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            logger.info("Configuration loaded successfully")
            return config
        except FileNotFoundError:
            logger.error(f"Configuration file {self.config_file} not found")
            return self.get_default_config()
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing configuration file: {e}")
            return self.get_default_config()
    
    def save_config(self) -> bool:
        """Save current configuration to JSON file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info("Configuration saved successfully")
            return True
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            return False
    
    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            "guild_id": int(os.getenv("GUILD_ID", "0")),
            "bot_token": os.getenv("DISCORD_TOKEN", ""),
            "announcements_channel_id": int(os.getenv("ANNOUNCEMENTS_CHANNEL_ID", "0")),
            "mod_log_channel_id": int(os.getenv("MOD_LOG_CHANNEL_ID", "0")),
            
            "xp_settings": {
                "message_xp_min": 25,
                "message_xp_max": 25,
                "message_cooldown_seconds": 15,
                "voice_xp_min": 25,
                "voice_xp_max": 25,
                "voice_tick_interval_seconds": 60
            },
            
            "channels": {
                "message_whitelist": [
                     1406672609340297367,
                     1405343788892684419,
                     1405340673032585337
                ],
                "voice_whitelist": [
                    1405342950422216786,
                    1405340524369412206
                ]
            },
            
            "role_rewards": {
                "5": 1407002119151685673,
                "10": 1407002164903284797,
                "20": 1407002220280676523,
                "30": 1407002301595652108,
                "50": 1407028439315386438
            },
            
            "exempt_roles": [
                1405636265260486656,
                1405636554759602236
            ],
            
            "level_formula": {
                "type": "xp_anchors",
                "anchors": [
                    { "level": 5,  "xp": 7500 },
                    { "level": 10, "xp": 60000 },
                    { "level": 20, "xp": 120000 },
                    { "level": 30, "xp": 225000 },
                    { "level": 50, "xp": 375000 }
                ],
                "base_xp": 100,
                "multiplier": 1.5
            }
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any) -> bool:
        """Set configuration value"""
        keys = key.split('.')
        config = self.config
        
        # Navigate to the parent of the target key
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # Set the value
        config[keys[-1]] = value
        
        # Save to file
        return self.save_config()
    
    def get_guild_id(self) -> int:
        """Get guild ID"""
        return self.get("guild_id", 0)
    
    def get_bot_token(self) -> str:
        """Get bot token"""
        return self.get("bot_token", "")
    
    def get_announcements_channel_id(self) -> int:
        """Get announcements channel ID"""
        return self.get("announcements_channel_id", 0)
    
    def get_mod_log_channel_id(self) -> int:
        """Get mod log channel ID"""
        return self.get("mod_log_channel_id", 0)
    
    def get_message_xp_min(self) -> int:
        """Get minimum message XP"""
        return self.get("xp_settings.message_xp_min", 25)
    
    def get_message_xp_max(self) -> int:
        """Get maximum message XP"""
        return self.get("xp_settings.message_xp_max", 25)
    
    def get_message_cooldown(self) -> int:
        """Get message cooldown in seconds"""
        return self.get("xp_settings.message_cooldown_seconds", 15)
    
    def get_voice_xp_min(self) -> int:
        """Get minimum voice XP"""
        return self.get("xp_settings.voice_xp_min", 25)
    
    def get_voice_xp_max(self) -> int:
        """Get maximum voice XP"""
        return self.get("xp_settings.voice_xp_max", 25)
    
    def get_voice_tick_interval(self) -> int:
        """Get voice tick interval in seconds"""
        return self.get("xp_settings.voice_tick_interval_seconds", 60)
    
    def get_message_whitelist(self) -> List[int]:
        """Get message channel whitelist"""
        return self.get("channels.message_whitelist", [])
    
    def get_voice_whitelist(self) -> List[int]:
        """Get voice channel whitelist"""
        return self.get("channels.voice_whitelist", [])
    
    def get_role_rewards(self) -> Dict[str, int]:
        """Get role rewards mapping"""
        return self.get("role_rewards", {})
    
    def get_exempt_roles(self) -> List[int]:
        """Get exempt role IDs"""
        return self.get("exempt_roles", [])
    
    def get_level_formula(self) -> Dict[str, float]:
        """Get level formula parameters"""
        return self.get("level_formula", {"base_xp": 100, "multiplier": 1.5})
    
    def set_message_cooldown(self, seconds: int) -> bool:
        """Set message cooldown"""
        return self.set("xp_settings.message_cooldown_seconds", seconds)
    
    def set_message_xp_range(self, min_xp: int, max_xp: int) -> bool:
        """Set message XP range"""
        success1 = self.set("xp_settings.message_xp_min", min_xp)
        success2 = self.set("xp_settings.message_xp_max", max_xp)
        return success1 and success2
    
    def set_voice_xp_range(self, min_xp: int, max_xp: int) -> bool:
        """Set voice XP range"""
        success1 = self.set("xp_settings.voice_xp_min", min_xp)
        success2 = self.set("xp_settings.voice_xp_max", max_xp)
        return success1 and success2
    
    def set_voice_tick_interval(self, seconds: int) -> bool:
        """Set voice tick interval"""
        return self.set("xp_settings.voice_tick_interval_seconds", seconds)
    
    def add_message_channel(self, channel_id: int) -> bool:
        """Add channel to message whitelist"""
        whitelist = self.get_message_whitelist()
        if channel_id not in whitelist:
            whitelist.append(channel_id)
            return self.set("channels.message_whitelist", whitelist)
        return True
    
    def remove_message_channel(self, channel_id: int) -> bool:
        """Remove channel from message whitelist"""
        whitelist = self.get_message_whitelist()
        if channel_id in whitelist:
            whitelist.remove(channel_id)
            return self.set("channels.message_whitelist", whitelist)
        return True
    
    def add_voice_channel(self, channel_id: int) -> bool:
        """Add channel to voice whitelist"""
        whitelist = self.get_voice_whitelist()
        if channel_id not in whitelist:
            whitelist.append(channel_id)
            return self.set("channels.voice_whitelist", whitelist)
        return True
    
    def remove_voice_channel(self, channel_id: int) -> bool:
        """Remove channel from voice whitelist"""
        whitelist = self.get_voice_whitelist()
        if channel_id in whitelist:
            whitelist.remove(channel_id)
            return self.set("channels.voice_whitelist", whitelist)
        return True
    
    def add_role_reward(self, level: int, role_id: int) -> bool:
        """Add role reward"""
        rewards = self.get_role_rewards()
        rewards[str(level)] = role_id
        return self.set("role_rewards", rewards)
    
    def remove_role_reward(self, level: int) -> bool:
        """Remove role reward"""
        rewards = self.get_role_rewards()
        if str(level) in rewards:
            del rewards[str(level)]
            return self.set("role_rewards", rewards)
        return True
    
    def add_exempt_role(self, role_id: int) -> bool:
        """Add exempt role"""
        exempt_roles = self.get_exempt_roles()
        if role_id not in exempt_roles:
            exempt_roles.append(role_id)
            return self.set("exempt_roles", exempt_roles)
        return True
    
    def remove_exempt_role(self, role_id: int) -> bool:
        """Remove exempt role"""
        exempt_roles = self.get_exempt_roles()
        if role_id in exempt_roles:
            exempt_roles.remove(role_id)
            return self.set("exempt_roles", exempt_roles)
        return True
    
    def set_announcements_channel(self, channel_id: int) -> bool:
        """Set announcements channel"""
        return self.set("announcements_channel_id", channel_id)
    
    def set_mod_log_channel(self, channel_id: int) -> bool:
        """Set mod log channel"""
        return self.set("mod_log_channel_id", channel_id)
    
    def get_config_summary(self) -> str:
        """Get configuration summary for display"""
        summary = "**Current Configuration:**\n\n"
        
        # XP Settings
        summary += "**XP Settings:**\n"
        summary += f"• Message XP: {self.get_message_xp_min()}-{self.get_message_xp_max()} XP\n"
        summary += f"• Message Cooldown: {self.get_message_cooldown()} seconds\n"
        summary += f"• Voice XP: {self.get_voice_xp_min()}-{self.get_voice_xp_max()} XP\n"
        summary += f"• Voice Tick Interval: {self.get_voice_tick_interval()} seconds\n\n"
        
        # Channels
        summary += "**Channels:**\n"
        summary += f"• Message Whitelist: {len(self.get_message_whitelist())} channels\n"
        summary += f"• Voice Whitelist: {len(self.get_voice_whitelist())} channels\n"
        summary += f"• Announcements: <#{self.get_announcements_channel_id()}>\n"
        summary += f"• Mod Log: <#{self.get_mod_log_channel_id()}>\n\n"
        
        # Role Rewards
        summary += "**Role Rewards:**\n"
        rewards = self.get_role_rewards()
        for level, role_id in rewards.items():
            summary += f"• Level {level}: <@&{role_id}>\n"
        
        summary += f"\n**Exempt Roles:** {len(self.get_exempt_roles())} roles\n"
        
        return summary
    
    def validate_config(self) -> List[str]:
        """Validate configuration and return list of issues"""
        issues = []
        
        if not self.get_bot_token() or self.get_bot_token() == "YOUR_BOT_TOKEN_HERE":
            issues.append("Bot token not configured")
        
        if self.get_guild_id() == 1234567890123456789:
            issues.append("Guild ID not configured")
        
        if self.get_announcements_channel_id() == 1234567890123456789:
            issues.append("Announcements channel not configured")
        
        if self.get_mod_log_channel_id() == 1234567890123456789:
            issues.append("Mod log channel not configured")
        
        # Check role rewards
        rewards = self.get_role_rewards()
        for level, role_id in rewards.items():
            if role_id == 1234567890123456789:
                issues.append(f"Role reward for level {level} not configured")
        
        # Check exempt roles
        exempt_roles = self.get_exempt_roles()
        for role_id in exempt_roles:
            if role_id == 1234567890123456789:
                issues.append("Exempt role not configured")
        
        return issues
