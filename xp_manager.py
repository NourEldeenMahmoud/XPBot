import random
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import discord
from database import Database
from config_manager import ConfigManager

logger = logging.getLogger(__name__)

class XPManager:
    def __init__(self, bot, database: Database, config: ConfigManager):
        self.bot = bot
        self.db = database
        self.config = config
    
    def calculate_level(self, xp: int) -> int:
        """Calculate level from XP using configurable formula.
        Supports legacy exponential formula and XP-anchors formula.
        """
        formula = self.config.get_level_formula()
        formula_type = formula.get("type", "exponential")

        if formula_type == "xp_anchors":
            thresholds = self._get_xp_anchor_thresholds()
            current_level = 1
            for level in sorted(thresholds.keys()):
                if xp >= thresholds[level]:
                    current_level = level
                else:
                    break
            return current_level

        # Legacy exponential behavior
        base_xp = formula.get("base_xp", 100)
        multiplier = formula.get("multiplier", 1.5)
        
        if xp < base_xp:
            return 1
        
        # Level = 1 + log_base_multiplier(xp / base_xp)
        import math
        level = 1 + math.log(xp / base_xp, multiplier)
        return int(level)
    
    def calculate_xp_for_level(self, level: int) -> int:
        """Calculate XP required for a specific level.
        Supports legacy exponential formula and XP-anchors formula.
        """
        formula = self.config.get_level_formula()
        formula_type = formula.get("type", "exponential")

        if formula_type == "xp_anchors":
            thresholds = self._get_xp_anchor_thresholds()
            if level <= 1:
                return 0
            # If level beyond our map, extend linearly using last segment slope
            if level in thresholds:
                return thresholds[level]
            highest = max(thresholds.keys())
            if level > highest:
                # Linear extrapolation beyond the highest anchor
                if highest - 1 in thresholds:
                    last_delta = thresholds[highest] - thresholds[highest - 1]
                else:
                    last_delta = 0
                return thresholds[highest] + last_delta * (level - highest)
            # Fallback
            return thresholds.get(level, 0)

        # Legacy exponential behavior
        base_xp = formula.get("base_xp", 100)
        multiplier = formula.get("multiplier", 1.5)
        
        if level <= 1:
            return 0
        
        return int(base_xp * (multiplier ** (level - 1)))

    def _get_xp_anchor_thresholds(self) -> Dict[int, int]:
        """Build a per-level XP threshold map from XP anchors.

        Behavior:
        - Piecewise linear interpolation between provided anchors.
        - Level 1 => 0 XP.
        - Below first anchor: linear from level 1.
        - Above last anchor: linear extrapolation using last segment slope.
        """
        formula = self.config.get_level_formula()
        anchors_data = formula.get("anchors", [])
        # Expect items like {"level": 5, "xp": 7500}
        anchors: List[Tuple[int, int]] = []
        for a in anchors_data:
            lvl = int(a.get("level", 0))
            xp_val = int(a.get("xp", 0))
            if lvl > 1 and xp_val >= 0:
                anchors.append((lvl, xp_val))

        if not anchors:
            # Fallback to a minimal curve if no anchors are provided
            return {1: 0, 2: 100, 3: 300, 4: 700, 5: 1500}

        anchors.sort(key=lambda t: t[0])

        thresholds: Dict[int, int] = {1: 0}

        # Build thresholds up to highest anchor via linear interpolation between points
        prev_level = 1
        prev_xp = 0
        for lvl, xp_target in anchors:
            span = max(lvl - prev_level, 1)
            for l in range(prev_level + 1, lvl + 1):
                t = (l - prev_level) / float(span)
                xp_at_l = int(prev_xp + t * (xp_target - prev_xp))
                thresholds[l] = xp_at_l
            prev_level = lvl
            prev_xp = xp_target

        # Extrapolate beyond the last anchor level with the last segment slope
        last_anchor_level = anchors[-1][0]
        if len(anchors) >= 2:
            prev_anchor_level, prev_anchor_xp = anchors[-2]
            last_span_levels = max(last_anchor_level - prev_anchor_level, 1)
            last_span_xp = anchors[-1][1] - prev_anchor_xp
            last_per_level_delta = int(last_span_xp / last_span_levels)
        else:
            # If single anchor, use its average per-level delta from level 1
            last_per_level_delta = int((anchors[-1][1] - 0) / max(anchors[-1][0] - 1, 1))

        for l in range(last_anchor_level + 1, 101):
            thresholds[l] = thresholds[last_anchor_level] + last_per_level_delta * (l - last_anchor_level)

        return thresholds
    
    def is_user_exempt(self, member: discord.Member) -> bool:
        """Check if user has any exempt roles"""
        if member.bot:
            return True
        
        exempt_roles = self.config.get_exempt_roles()
        user_role_ids = [role.id for role in member.roles]
        
        for exempt_role_id in exempt_roles:
            if exempt_role_id in user_role_ids:
                return True
        
        return False
    
    def get_user_reward_roles(self, member: discord.Member) -> List[discord.Role]:
        """Get all reward roles that the user currently has"""
        reward_roles = []
        role_rewards = self.config.get_role_rewards()
        
        for role in member.roles:
            if role.id in role_rewards.values():
                reward_roles.append(role)
        
        return reward_roles
    
    def get_appropriate_reward_role(self, level: int) -> Optional[int]:
        """Get the appropriate reward role ID for the given level"""
        role_rewards = self.config.get_role_rewards()
        
        # Find the highest level threshold that the user has reached
        appropriate_level = 0
        appropriate_role_id = None
        
        for level_str, role_id in role_rewards.items():
            level_threshold = int(level_str)
            if level >= level_threshold and level_threshold > appropriate_level:
                appropriate_level = level_threshold
                appropriate_role_id = role_id
        
        return appropriate_role_id
    
    async def award_message_xp(self, guild: discord.Guild, member: discord.Member, channel: discord.TextChannel) -> Optional[Dict]:
        """Award XP for message activity"""
        # Check if user is exempt
        if self.is_user_exempt(member):
            return None
        
        # Check if channel is whitelisted
        if channel.id not in self.config.get_message_whitelist():
            return None
        
        # Get user data
        user_data = self.db.get_or_create_user(guild.id, member.id)
        
        # Check cooldown
        cooldown_seconds = self.config.get_message_cooldown()
        current_time = datetime.now().timestamp()
        
        if current_time - user_data['last_message_xp_timestamp'] < cooldown_seconds:
            return None
        
        # Award XP
        min_xp = self.config.get_message_xp_min()
        max_xp = self.config.get_message_xp_max()
        xp_amount = random.randint(min_xp, max_xp)
        
        success = self.db.award_message_xp(guild.id, member.id, xp_amount)
        if not success:
            return None
        
        # Get updated user data
        updated_user = self.db.get_user(guild.id, member.id)
        old_level = user_data['level']
        new_level = self.calculate_level(updated_user['permanent_xp'])
        
        result = {
            'xp_awarded': xp_amount,
            'old_level': old_level,
            'new_level': new_level,
            'total_xp': updated_user['permanent_xp'],
            'weekly_xp': updated_user['weekly_xp'],
            'leveled_up': new_level > old_level
        }
        
        # Handle level up and role rewards
        if result['leveled_up']:
            await self.handle_level_up(guild, member, old_level, new_level)
        
        return result
    
    async def award_voice_xp(self, guild: discord.Guild, member: discord.Member, channel: discord.VoiceChannel) -> Optional[Dict]:
        """Award XP for voice activity"""
        # Check if user is exempt
        if self.is_user_exempt(member):
            return None
        
        # Check if channel is whitelisted
        if channel.id not in self.config.get_voice_whitelist():
            return None
        
        # Get user data
        user_data = self.db.get_or_create_user(guild.id, member.id)
        
        # Check if enough time has passed since last voice XP
        voice_tick_interval = self.config.get_voice_tick_interval()
        current_time = datetime.now().timestamp()
        
        if current_time - user_data['last_voice_xp_timestamp'] < voice_tick_interval:
            return None
        
        # Award XP
        min_xp = self.config.get_voice_xp_min()
        max_xp = self.config.get_voice_xp_max()
        xp_amount = random.randint(min_xp, max_xp)
        
        success = self.db.award_voice_xp(guild.id, member.id, xp_amount)
        if not success:
            return None
        
        # Update voice tick timestamp
        self.db.update_voice_tick(guild.id, member.id)
        
        # Get updated user data
        updated_user = self.db.get_user(guild.id, member.id)
        old_level = user_data['level']
        new_level = self.calculate_level(updated_user['permanent_xp'])
        
        result = {
            'xp_awarded': xp_amount,
            'old_level': old_level,
            'new_level': new_level,
            'total_xp': updated_user['permanent_xp'],
            'weekly_xp': updated_user['weekly_xp'],
            'leveled_up': new_level > old_level
        }
        
        # Handle level up and role rewards
        if result['leveled_up']:
            await self.handle_level_up(guild, member, old_level, new_level)
        
        return result
    
    async def handle_level_up(self, guild: discord.Guild, member: discord.Member, old_level: int, new_level: int):
        """Handle level up events and role rewards"""
        try:
            # Get appropriate reward role for new level
            new_reward_role_id = self.get_appropriate_reward_role(new_level)
            
            if new_reward_role_id:
                new_reward_role = guild.get_role(new_reward_role_id)
                if not new_reward_role:
                    logger.error(f"Reward role {new_reward_role_id} not found in guild")
                    return
                
                # Remove previous reward roles from the same reward set
                current_reward_roles = self.get_user_reward_roles(member)
                role_rewards = self.config.get_role_rewards()
                
                for role in current_reward_roles:
                    if role.id in role_rewards.values():
                        try:
                            await member.remove_roles(role, reason=f"Level up: {old_level} → {new_level}")
                            await self.log_role_removal(guild, member, role, f"Level up to {new_level}")
                        except discord.Forbidden:
                            logger.error(f"Cannot remove role {role.name} from {member.name} - insufficient permissions")
                        except Exception as e:
                            logger.error(f"Error removing role {role.name} from {member.name}: {e}")
                
                # Add new reward role
                try:
                    await member.add_roles(new_reward_role, reason=f"Level up: {old_level} → {new_level}")
                    await self.log_role_grant(guild, member, new_reward_role, f"Level up to {new_level}")
                    
                    # Announce role grant
                    await self.announce_role_grant(guild, member, new_reward_role, new_level)
                except discord.Forbidden:
                    logger.error(f"Cannot add role {new_reward_role.name} to {member.name} - insufficient permissions")
                except Exception as e:
                    logger.error(f"Error adding role {new_reward_role.name} to {member.name}: {e}")
            
            # Log level up
            await self.log_level_up(guild, member, old_level, new_level)
            
        except Exception as e:
            logger.error(f"Error handling level up for {member.name}: {e}")
    
    async def announce_role_grant(self, guild: discord.Guild, member: discord.Member, role: discord.Role, level: int):
        """Announce role grant in announcements channel"""
        try:
            announcements_channel_id = self.config.get_announcements_channel_id()
            if announcements_channel_id:
                channel = guild.get_channel(announcements_channel_id)
                if channel:
                    embed = discord.Embed(
                        title="🎉 New Role Unlocked!",
                        description=f"Congratulations {member.mention}! You've reached **Level {level}** and earned the **{role.name}** role!",
                        color=role.color if role.color != discord.Color.default() else discord.Color.green(),
                        timestamp=datetime.now()
                    )
                    embed.set_thumbnail(url=member.display_avatar.url)
                    embed.add_field(name="Role", value=role.mention, inline=True)
                    embed.add_field(name="Level", value=str(level), inline=True)
                    
                    await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Error announcing role grant: {e}")
    
    async def log_level_up(self, guild: discord.Guild, member: discord.Member, old_level: int, new_level: int):
        """Log level up event"""
        try:
            mod_log_channel_id = self.config.get_mod_log_channel_id()
            if mod_log_channel_id:
                channel = guild.get_channel(mod_log_channel_id)
                if channel:
                    embed = discord.Embed(
                        title="📈 Level Up",
                        description=f"{member.mention} leveled up from **{old_level}** to **{new_level}**",
                        color=discord.Color.blue(),
                        timestamp=datetime.now()
                    )
                    embed.set_thumbnail(url=member.display_avatar.url)
                    embed.add_field(name="User", value=f"{member.name}#{member.discriminator}", inline=True)
                    embed.add_field(name="Level Change", value=f"{old_level} → {new_level}", inline=True)
                    
                    await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Error logging level up: {e}")
    
    async def log_role_grant(self, guild: discord.Guild, member: discord.Member, role: discord.Role, reason: str):
        """Log role grant event"""
        try:
            mod_log_channel_id = self.config.get_mod_log_channel_id()
            if mod_log_channel_id:
                channel = guild.get_channel(mod_log_channel_id)
                if channel:
                    embed = discord.Embed(
                        title="🎖️ Role Granted",
                        description=f"{member.mention} was granted the **{role.name}** role",
                        color=discord.Color.green(),
                        timestamp=datetime.now()
                    )
                    embed.set_thumbnail(url=member.display_avatar.url)
                    embed.add_field(name="User", value=f"{member.name}#{member.discriminator}", inline=True)
                    embed.add_field(name="Role", value=role.mention, inline=True)
                    embed.add_field(name="Reason", value=reason, inline=False)
                    
                    await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Error logging role grant: {e}")
    
    async def log_role_removal(self, guild: discord.Guild, member: discord.Member, role: discord.Role, reason: str):
        """Log role removal event"""
        try:
            mod_log_channel_id = self.config.get_mod_log_channel_id()
            if mod_log_channel_id:
                channel = guild.get_channel(mod_log_channel_id)
                if channel:
                    embed = discord.Embed(
                        title="🗑️ Role Removed",
                        description=f"{member.mention} had the **{role.name}** role removed",
                        color=discord.Color.orange(),
                        timestamp=datetime.now()
                    )
                    embed.set_thumbnail(url=member.display_avatar.url)
                    embed.add_field(name="User", value=f"{member.name}#{member.discriminator}", inline=True)
                    embed.add_field(name="Role", value=role.mention, inline=True)
                    embed.add_field(name="Reason", value=reason, inline=False)
                    
                    await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Error logging role removal: {e}")
    
    async def sync_user_roles(self, guild: discord.Guild, member: discord.Member):
        """Sync user's roles based on their current level"""
        try:
            user_data = self.db.get_user(guild.id, member.id)
            if not user_data:
                return
            
            current_level = user_data['level']
            appropriate_role_id = self.get_appropriate_reward_role(current_level)
            
            if appropriate_role_id:
                appropriate_role = guild.get_role(appropriate_role_id)
                if appropriate_role:
                    # Remove all current reward roles
                    current_reward_roles = self.get_user_reward_roles(member)
                    role_rewards = self.config.get_role_rewards()
                    
                    for role in current_reward_roles:
                        if role.id in role_rewards.values():
                            try:
                                await member.remove_roles(role, reason="Role sync")
                            except discord.Forbidden:
                                logger.error(f"Cannot remove role {role.name} from {member.name} - insufficient permissions")
                            except Exception as e:
                                logger.error(f"Error removing role {role.name} from {member.name}: {e}")
                    
                    # Add appropriate reward role
                    try:
                        await member.add_roles(appropriate_role, reason="Role sync")
                        await self.log_role_grant(guild, member, appropriate_role, f"Role sync for level {current_level}")
                    except discord.Forbidden:
                        logger.error(f"Cannot add role {appropriate_role.name} to {member.name} - insufficient permissions")
                    except Exception as e:
                        logger.error(f"Error adding role {appropriate_role.name} to {member.name}: {e}")
        
        except Exception as e:
            logger.error(f"Error syncing roles for {member.name}: {e}")
    
    def get_user_stats(self, guild_id: int, user_id: int) -> Optional[Dict]:
        """Get comprehensive user statistics"""
        user_data = self.db.get_user(guild_id, user_id)
        if not user_data:
            return None
        
        total_xp = user_data['permanent_xp']
        weekly_xp = user_data['weekly_xp']
        level = user_data['level']
        
        # Calculate XP progress to next level
        current_level_xp = self.calculate_xp_for_level(level)
        next_level_xp = self.calculate_xp_for_level(level + 1)
        xp_progress = total_xp - current_level_xp
        xp_needed = next_level_xp - current_level_xp
        
        # Get ranks
        permanent_rank = self.db.get_user_rank(guild_id, user_id)
        weekly_rank = self.db.get_user_weekly_rank(guild_id, user_id)
        
        return {
            'total_xp': total_xp,
            'weekly_xp': weekly_xp,
            'level': level,
            'xp_progress': xp_progress,
            'xp_needed': xp_needed,
            'permanent_rank': permanent_rank,
            'weekly_rank': weekly_rank,
            'progress_percentage': (xp_progress / xp_needed * 100) if xp_needed > 0 else 100
        }
