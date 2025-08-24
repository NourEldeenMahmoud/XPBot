import discord
from discord.ext import commands
from discord import app_commands
import logging
from typing import Optional
from datetime import datetime
from io import BytesIO
import os
import base64
import math
import pkgutil
import asyncio

# Pillow for image generation
try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
except Exception:  # pragma: no cover - Pillow may not be available at import time in some envs
    Image = None
    ImageDraw = None
    ImageFont = None
    ImageFilter = None
    ImageOps = None

logger = logging.getLogger(__name__)

class XPCommands(commands.Cog):
    def __init__(self, bot, xp_manager, database, config):
        self.bot = bot
        self.xp_manager = xp_manager
        self.db = database
        self.config = config
    
    @commands.command(name="rank")
    async def rank_command(self, ctx, user: Optional[discord.Member] = None):
        """Show user's rank, XP, and level information"""
        if user is None:
            user = ctx.author
        
        # Check if user is in the correct guild
        if user.guild.id != self.config.get_guild_id():
            return
        
        stats = self.xp_manager.get_user_stats(user.guild.id, user.id)
        if not stats:
            await ctx.send(f"{user.mention} has no XP data yet!")
            return
        
        # Create rank embed
        embed = discord.Embed(
            title=f"📊 {user.display_name}'s Stats",
            color=user.color if user.color != discord.Color.default() else discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        
        # XP and Level info
        embed.add_field(
            name="🏆 Total XP & Level",
            value=f"**{stats['total_xp']:,} XP** • Level **{stats['level']}**",
            inline=False
        )
        
        # Weekly XP
        embed.add_field(
            name="📅 Weekly XP",
            value=f"**{stats['weekly_xp']:,} XP**",
            inline=True
        )
        
        # Ranks
        permanent_rank = stats['permanent_rank'] or "N/A"
        weekly_rank = stats['weekly_rank'] or "N/A"
        
        embed.add_field(
            name="🏅 Ranks",
            value=f"**#{permanent_rank}** (Total) • **#{weekly_rank}** (Weekly)",
            inline=True
        )
        
        # Progress to next level
        if stats['level'] > 1:
            progress_bar = self.create_progress_bar(stats['progress_percentage'])
            embed.add_field(
                name=f"📈 Progress to Level {stats['level'] + 1}",
                value=f"{progress_bar} **{stats['xp_progress']:,}** / **{stats['xp_needed']:,} XP** ({stats['progress_percentage']:.1f}%)",
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="leaderboard")
    async def leaderboard_command(self, ctx, limit: Optional[int] = 10):
        """Show the permanent leaderboard as a generated image"""
        if limit > 25:
            limit = 25
        elif limit < 1:
            limit = 10

        leaderboard = self.db.get_leaderboard(ctx.guild.id, limit)
        if not leaderboard:
            await ctx.send("No users found in the leaderboard!")
            return

        # Fallback to embed if Pillow is unavailable
        if Image is None:
            embed = discord.Embed(
                title="🏆 Permanent Leaderboard",
                description="Top users by total XP",
                color=discord.Color.gold(),
                timestamp=datetime.now()
            )
            for entry in leaderboard:
                user = ctx.guild.get_member(entry['user_id'])
                if user:
                    embed.add_field(
                        name=f"#{entry['rank']} • {user.display_name}",
                        value=f"**{entry['permanent_xp']:,} XP** • Level **{entry['level']}**",
                        inline=False
                    )
            await ctx.send(embed=embed)
            return

        image_bytes = await self._render_leaderboard_image(ctx.guild, leaderboard)
        await ctx.send(file=discord.File(fp=image_bytes, filename="leaderboard.png"))
    
    @commands.command(name="weeklyleaderboard")
    async def weekly_leaderboard_command(self, ctx, limit: Optional[int] = 10):
        """Show the weekly leaderboard as a generated image"""
        if limit > 25:
            limit = 25
        elif limit < 1:
            limit = 10

        leaderboard = self.db.get_weekly_leaderboard(ctx.guild.id, limit)
        if not leaderboard:
            await ctx.send("No users found in the weekly leaderboard!")
            return

        # Try to generate image, fallback to embed if Pillow is not available
        if Image is not None:
            try:
                image_buffer = await self._render_weekly_leaderboard_image(ctx.guild, leaderboard)
                file = discord.File(image_buffer, filename="weekly_leaderboard.png")
                await ctx.send(file=file)
                return
            except Exception as e:
                logger.error(f"Error generating weekly leaderboard image: {e}")
                # Fall back to embed
        
        # Fallback embed
        embed = discord.Embed(
            title="📅 Weekly Leaderboard",
            description="Top users by weekly XP",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        for entry in leaderboard:
            user = ctx.guild.get_member(entry['user_id'])
            if user:
                embed.add_field(
                    name=f"#{entry['rank']} • {user.display_name}",
                    value=f"**{entry['weekly_xp']:,} XP**",
                    inline=False
                )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="setxp")
    @commands.has_permissions(administrator=True)
    async def set_xp_command(self, ctx, user: discord.Member, amount: int):
        """Set a user's permanent XP (Admin only)"""
        if amount < 0:
            await ctx.send("XP amount cannot be negative!")
            return
        
        success = self.db.set_user_xp(ctx.guild.id, user.id, amount)
        if success:
            # Update level in database
            new_level = self.xp_manager.calculate_level(amount)
            self.db.set_user_level(ctx.guild.id, user.id, new_level)
            
            # Sync roles
            await self.xp_manager.sync_user_roles(ctx.guild, user)
            
            embed = discord.Embed(
                title="✅ XP Updated",
                description=f"{user.mention}'s permanent XP has been set to **{amount:,}**",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="New Level", value=str(new_level), inline=True)
            embed.add_field(name="Updated by", value=ctx.author.mention, inline=True)
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Failed to update XP!")
    
    @commands.command(name="setweekly")
    @commands.has_permissions(administrator=True)
    async def set_weekly_command(self, ctx, user: discord.Member, amount: int):
        """Set a user's weekly XP (Admin only)"""
        if amount < 0:
            await ctx.send("XP amount cannot be negative!")
            return
        
        success = self.db.set_user_xp(ctx.guild.id, user.id, None, amount)
        if success:
            embed = discord.Embed(
                title="✅ Weekly XP Updated",
                description=f"{user.mention}'s weekly XP has been set to **{amount:,}**",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Updated by", value=ctx.author.mention, inline=True)
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Failed to update weekly XP!")
    
    @commands.command(name="setlevel")
    @commands.has_permissions(administrator=True)
    async def set_level_command(self, ctx, user: discord.Member, level: int):
        """Set a user's level (Admin only)"""
        if level < 1:
            await ctx.send("Level cannot be less than 1!")
            return
        
        # Calculate XP for the level
        xp_needed = self.xp_manager.calculate_xp_for_level(level)
        
        success = self.db.set_user_xp(ctx.guild.id, user.id, xp_needed)
        if success:
            self.db.set_user_level(ctx.guild.id, user.id, level)
            
            # Sync roles
            await self.xp_manager.sync_user_roles(ctx.guild, user)
            
            embed = discord.Embed(
                title="✅ Level Updated",
                description=f"{user.mention}'s level has been set to **{level}**",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="XP Required", value=f"{xp_needed:,} XP", inline=True)
            embed.add_field(name="Updated by", value=ctx.author.mention, inline=True)
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Failed to update level!")
    
    @commands.command(name="resetweekly")
    @commands.has_permissions(administrator=True)
    async def reset_weekly_command(self, ctx):
        """Reset the weekly leaderboard (Admin only)"""
        success = self.db.reset_weekly_leaderboard(ctx.guild.id)
        if success:
            embed = discord.Embed(
                title="✅ Weekly Leaderboard Reset",
                description="The weekly leaderboard has been reset and archived.",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Reset by", value=ctx.author.mention, inline=True)
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Failed to reset weekly leaderboard!")
    
    @commands.command(name="exempt")
    @commands.has_permissions(administrator=True)
    async def exempt_command(self, ctx, action: str, role: discord.Role):
        """Manage exempt roles (Admin only)"""
        action = action.lower()
        
        if action == "add":
            success = self.config.add_exempt_role(role.id)
            if success:
                embed = discord.Embed(
                    title="✅ Exempt Role Added",
                    description=f"{role.mention} has been added to the exempt roles list.",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                await ctx.send(embed=embed)
            else:
                await ctx.send("❌ Failed to add exempt role!")
        
        elif action == "remove":
            success = self.config.remove_exempt_role(role.id)
            if success:
                embed = discord.Embed(
                    title="✅ Exempt Role Removed",
                    description=f"{role.mention} has been removed from the exempt roles list.",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                await ctx.send(embed=embed)
            else:
                await ctx.send("❌ Failed to remove exempt role!")
        
        else:
            await ctx.send("❌ Invalid action! Use 'add' or 'remove'.")
    
    @commands.command(name="config")
    @commands.has_permissions(administrator=True)
    async def config_command(self, ctx, action: str = "show"):
        """Show or modify configuration (Admin only)"""
        if action == "show":
            summary = self.config.get_config_summary()
            embed = discord.Embed(
                title="⚙️ Bot Configuration",
                description=summary,
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            await ctx.send(embed=embed)
        
        else:
            await ctx.send("❌ Invalid action! Use 'show' to display configuration.")
    
    @commands.command(name="setcooldown")
    @commands.has_permissions(administrator=True)
    async def set_cooldown_command(self, ctx, seconds: int):
        """Set message cooldown in seconds (Admin only)"""
        if seconds < 1:
            await ctx.send("Cooldown must be at least 1 second!")
            return
        
        success = self.config.set_message_cooldown(seconds)
        if success:
            embed = discord.Embed(
                title="✅ Cooldown Updated",
                description=f"Message cooldown has been set to **{seconds} seconds**",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Updated by", value=ctx.author.mention, inline=True)
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Failed to update cooldown!")
    
    @commands.command(name="setmessagexp")
    @commands.has_permissions(administrator=True)
    async def set_message_xp_command(self, ctx, min_xp: int, max_xp: int):
        """Set message XP range (Admin only)"""
        if min_xp < 0 or max_xp < 0:
            await ctx.send("XP values cannot be negative!")
            return
        
        if min_xp > max_xp:
            await ctx.send("Minimum XP cannot be greater than maximum XP!")
            return
        
        success = self.config.set_message_xp_range(min_xp, max_xp)
        if success:
            embed = discord.Embed(
                title="✅ Message XP Updated",
                description=f"Message XP range has been set to **{min_xp}-{max_xp} XP**",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Updated by", value=ctx.author.mention, inline=True)
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Failed to update message XP range!")
    
    @commands.command(name="setvoicexp")
    @commands.has_permissions(administrator=True)
    async def set_voice_xp_command(self, ctx, min_xp: int, max_xp: int):
        """Set voice XP range (Admin only)"""
        if min_xp < 0 or max_xp < 0:
            await ctx.send("XP values cannot be negative!")
            return
        
        if min_xp > max_xp:
            await ctx.send("Minimum XP cannot be greater than maximum XP!")
            return
        
        success = self.config.set_voice_xp_range(min_xp, max_xp)
        if success:
            embed = discord.Embed(
                title="✅ Voice XP Updated",
                description=f"Voice XP range has been set to **{min_xp}-{max_xp} XP**",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Updated by", value=ctx.author.mention, inline=True)
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Failed to update voice XP range!")
    
    @commands.command(name="setvoiceinterval")
    @commands.has_permissions(administrator=True)
    async def set_voice_interval_command(self, ctx, seconds: int):
        """Set voice XP tick interval in seconds (Admin only)"""
        if seconds < 10:
            await ctx.send("Voice tick interval must be at least 10 seconds!")
            return
        
        success = self.config.set_voice_tick_interval(seconds)
        if success:
            embed = discord.Embed(
                title="✅ Voice Interval Updated",
                description=f"Voice XP tick interval has been set to **{seconds} seconds**",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Updated by", value=ctx.author.mention, inline=True)
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Failed to update voice interval!")
    
    @commands.command(name="addmessagechannel")
    @commands.has_permissions(administrator=True)
    async def add_message_channel_command(self, ctx, channel: discord.TextChannel):
        """Add channel to message XP whitelist (Admin only)"""
        success = self.config.add_message_channel(channel.id)
        if success:
            embed = discord.Embed(
                title="✅ Message Channel Added",
                description=f"{channel.mention} has been added to the message XP whitelist.",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Updated by", value=ctx.author.mention, inline=True)
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Failed to add message channel!")
    
    @commands.command(name="addvoicechannel")
    @commands.has_permissions(administrator=True)
    async def add_voice_channel_command(self, ctx, channel: discord.VoiceChannel):
        """Add channel to voice XP whitelist (Admin only)"""
        success = self.config.add_voice_channel(channel.id)
        if success:
            embed = discord.Embed(
                title="✅ Voice Channel Added",
                description=f"{channel.mention} has been added to the voice XP whitelist.",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Updated by", value=ctx.author.mention, inline=True)
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Failed to add voice channel!")
    
    @commands.command(name="removemessagechannel")
    @commands.has_permissions(administrator=True)
    async def remove_message_channel_command(self, ctx, channel: discord.TextChannel):
        """Remove channel from message XP whitelist (Admin only)"""
        success = self.config.remove_message_channel(channel.id)
        if success:
            embed = discord.Embed(
                title="✅ Message Channel Removed",
                description=f"{channel.mention} has been removed from the message XP whitelist.",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Updated by", value=ctx.author.mention, inline=True)
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Failed to remove message channel!")
    
    @commands.command(name="removevoicechannel")
    @commands.has_permissions(administrator=True)
    async def remove_voice_channel_command(self, ctx, channel: discord.VoiceChannel):
        """Remove channel from voice XP whitelist (Admin only)"""
        success = self.config.remove_voice_channel(channel.id)
        if success:
            embed = discord.Embed(
                title="✅ Voice Channel Removed",
                description=f"{channel.mention} has been removed from the voice XP whitelist.",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Updated by", value=ctx.author.mention, inline=True)
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Failed to remove voice channel!")
    
    @commands.command(name="setrole")
    @commands.has_permissions(administrator=True)
    async def set_role_command(self, ctx, level: int, role: discord.Role):
        """Set role reward for a level (Admin only)"""
        if level < 1:
            await ctx.send("Level must be at least 1!")
            return
        
        success = self.config.add_role_reward(level, role.id)
        if success:
            embed = discord.Embed(
                title="✅ Role Reward Set",
                description=f"{role.mention} has been set as the reward for Level {level}.",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Updated by", value=ctx.author.mention, inline=True)
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Failed to set role reward!")
    
    @commands.command(name="removerole")
    @commands.has_permissions(administrator=True)
    async def remove_role_command(self, ctx, level: int):
        """Remove role reward for a level (Admin only)"""
        if level < 1:
            await ctx.send("Level must be at least 1!")
            return
        
        success = self.config.remove_role_reward(level)
        if success:
            embed = discord.Embed(
                title="✅ Role Reward Removed",
                description=f"Role reward for Level {level} has been removed.",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Updated by", value=ctx.author.mention, inline=True)
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Failed to remove role reward!")
    
    @commands.command(name="backup")
    @commands.has_permissions(administrator=True)
    async def backup_command(self, ctx):
        """Create a database backup (Admin only)"""
        try:
            filename = self.db.export_database()
            embed = discord.Embed(
                title="✅ Database Backup Created",
                description=f"Database backup saved as `{filename}`",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Backup by", value=ctx.author.mention, inline=True)
            
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ Failed to create backup: {e}")
    
    def create_progress_bar(self, percentage: float, length: int = 10) -> str:
        """Create a visual progress bar"""
        filled_length = int(length * percentage / 100)
        bar = "█" * filled_length + "░" * (length - filled_length)
        return bar

    # -----------------------------
    # Image rendering helpers (Pillow)
    # -----------------------------
    async def _render_leaderboard_image(self, guild: discord.Guild, leaderboard: list) -> BytesIO:
        """Render a PNG leaderboard image and return BytesIO ready for Discord upload."""
        # Layout configuration
        width = 1200  # wider card
        margin_x = 32
        margin_y = 24
        card_height = 160  # bigger to accommodate 140px avatar
        card_gap = 16      # consistent spacing
        header_height = 84
        footer_gap = 20

        visible_count = min(len(leaderboard), 10)
        total_height = margin_y * 2 + header_height + footer_gap + (card_height + card_gap) * visible_count

        # Base image
        bg_color = (24, 22, 30)  # dark background
        img = Image.new("RGBA", (width, total_height), bg_color)
        draw = ImageDraw.Draw(img)

        # Title text (slightly smaller as requested)
        title_font = self._get_font(44, bold=True)
        subtitle_font = self._get_font(28, bold=True)
        small_font = self._get_font(30, bold=True)  # bigger font for percentage
        value_font = self._get_font(38, bold=True)  # increase XP font size by 2-4 levels

        title_text = "Server Leaderboard"
        draw.text((margin_x, margin_y), title_text, fill=(249, 249, 255), font=title_font)
        # Subtitle without date/time
        
        # Cards
        start_y = margin_y + header_height
        for idx, entry in enumerate(leaderboard[:10]):
            top_card = idx == 0
            card_y = start_y + idx * (card_height + card_gap)
            card_x = margin_x
            card_w = width - margin_x * 2

            # Background with rounded corners, thin border and subtle shadow
            # Alternating background for separation
            if top_card:
                card_bg = (50, 46, 66)
            else:
                card_bg = (47, 44, 58) if idx % 2 else (43, 40, 52)
            self._draw_card_with_shadow(img, (card_x, card_y, card_x + card_w, card_y + card_height), radius=18, fill=card_bg, glow=top_card)
            # Thin border
            border = Image.new("RGBA", (card_w, card_height), (0, 0, 0, 0))
            border_draw = ImageDraw.Draw(border)
            border_draw.rounded_rectangle((0, 0, card_w - 1, card_height - 1), radius=18, outline=(90, 90, 110, 220), width=2)
            img.alpha_composite(border, (card_x, card_y))

            # Fetch user
            member = guild.get_member(entry['user_id'])
            display_name = member.display_name if member else f"User {entry['user_id']}"
            avatar_img = await self._fetch_avatar_image(member)

            # Rank icon/emoji on the far left, aligned with avatar center
            rank_emoji = "🏆" if idx == 0 else ("🥈" if idx == 1 else ("🥉" if idx == 2 else "⭐"))
            emoji_x = card_x + 20
            # Try using an emoji font first
            emoji_font = self._get_emoji_font(75)  # same size as avatar
            if emoji_font is not None:
                emoji_bbox = draw.textbbox((0, 0), rank_emoji, font=emoji_font)
                emoji_w = emoji_bbox[2] - emoji_bbox[0]
                emoji_h = emoji_bbox[3] - emoji_bbox[1]
                # Align emoji with avatar center (avatar is centered vertically in card)
                avatar_center_y = card_y + (card_height - 140) // 2 + 70  # 140 is avatar size, 70 is half
                emoji_y = int(avatar_center_y - emoji_h / 2) + 15  # move emoji down a bit
                # Ensure emoji is properly aligned with avatar center
                draw.text((emoji_x, emoji_y), rank_emoji, font=emoji_font, fill=(255, 255, 255))
            else:
                # Fallback: draw embedded PNG icon
                icon_img = self._get_rank_icon_image(idx, target_height=75)  # same size as avatar
                emoji_w, emoji_h = icon_img.size
                # Align icon with avatar center
                avatar_center_y = card_y + (card_height - 140) // 2 + 70
                emoji_y = int(avatar_center_y - emoji_h / 2) + 15  # move icon down a bit
                # Ensure icon is properly aligned with avatar center
                img.paste(icon_img, (emoji_x, emoji_y), icon_img)

            # Avatar circle to the right of emoji
            avatar_size = 140
            avatar_x = emoji_x + emoji_w + 24
            avatar_y = card_y + (card_height - avatar_size) // 2
            if avatar_img:
                avatar_img = avatar_img.resize((avatar_size, avatar_size), Image.LANCZOS)
                avatar_mask = Image.new("L", (avatar_size, avatar_size), 0)
                ImageDraw.Draw(avatar_mask).ellipse((0, 0, avatar_size, avatar_size), fill=255)
                img.paste(avatar_img, (avatar_x, avatar_y), avatar_mask)

            # Text column and name (no rank suffix next to name)
            text_col_x = avatar_x + avatar_size + 24
            text_top_y = card_y + 30  # move name slightly up
            name_font = self._get_font(44, bold=True)  # increase font size by 2 levels
            # Padding from card edge already ensured via text_col_x
            draw.text((text_col_x, text_top_y), display_name, fill=(255, 255, 255), font=name_font)
            
            # Add voice time and message count below name
            stats_text = f"🎤 {voice_time}m • 💬 {message_count:,} msgs"
            stats_y = text_top_y + 50
            stats_font = self._get_font(24, bold=False)
            draw.text((text_col_x, stats_y), stats_text, fill=(180, 200, 255), font=stats_font)

            # Progress label under name
            level = entry.get('level', 1)
            total_xp = entry.get('permanent_xp', 0)
            voice_time = entry.get('voice_time', 0) or 0
            message_count = entry.get('message_count', 0) or 0
            current_level_xp = self.xp_manager.calculate_xp_for_level(level)
            next_level_xp = self.xp_manager.calculate_xp_for_level(level + 1)
            xp_progress = max(0, total_xp - current_level_xp)
            xp_needed = max(1, next_level_xp - current_level_xp)
            pct = max(0.0, min(1.0, xp_progress / xp_needed))

            # Progress bar (keep size), align neatly under name
            bar_x = text_col_x
            bar_y = card_y + card_height - 50  # move progress bar up from bottom edge
            bar_w = int(card_w * 0.60)
            bar_h = 32  # much bigger progress bar
            self._draw_progress_bar(img, (bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), pct)

            # Progress percentage on the right side of progress bar
            progress_text = f"Level {level}"
            progress_w = draw.textlength(progress_text, font=small_font)
            progress_x = bar_x + bar_w + 15  # 15px padding from progress bar
            progress_y = bar_y + (bar_h - 36) // 2 - 4  # nudge up slightly
            draw.text((progress_x, progress_y), progress_text, fill=(190, 190, 200), font=small_font)

            # XP value on right, above progress percentage
            current_level_xp = self.xp_manager.calculate_xp_for_level(level)
            user_xp_in_level = total_xp - current_level_xp
            next_level_xp = self.xp_manager.calculate_xp_for_level(level + 1)
            xp_needed_for_level = next_level_xp - current_level_xp
            value = f"{user_xp_in_level:,} / {xp_needed_for_level:,}"
            value_w = draw.textlength(value, font=value_font)
            value_x = bar_x + bar_w - value_w  # align right edge with progress bar end
            value_y = progress_y - 50  # slightly lower (down a bit)
            # Highlight XP values for visibility (gold/silver/bronze for top 3)
            value_color = (255, 215, 64) if idx == 0 else ((200, 200, 210) if idx == 1 else ((205, 127, 50) if idx == 2 else (235, 240, 255)))
            # Soft shadow behind text for extra contrast
            draw.text((value_x + 2, value_y + 2), value, fill=(0, 0, 0), font=value_font)
            draw.text((value_x, value_y), value, fill=value_color, font=value_font)

        # Export to bytes
        output = BytesIO()
        img.save(output, format="PNG")
        output.seek(0)
        return output

    async def _render_weekly_leaderboard_image(self, guild: discord.Guild, leaderboard: list) -> BytesIO:
        """Render weekly leaderboard as an image"""
        if not leaderboard:
            raise ValueError("No leaderboard data provided")

        # Layout configuration - different from permanent leaderboard
        width = 1600  # much wider for emojis and content
        margin_x = 50
        margin_y = 30
        card_height = 180  # taller cards for more info
        card_gap = 20      # more spacing
        header_height = 100
        footer_gap = 30
        visible_count = min(len(leaderboard), 10)
        total_height = margin_y * 2 + header_height + footer_gap + (card_height + card_gap) * visible_count

        # Create base image - different color scheme
        img = Image.new("RGBA", (width, total_height), (20, 25, 35))  # darker blue background
        draw = ImageDraw.Draw(img)

        # Fonts - even bigger sizes
        title_font = self._get_font(75, bold=True)
        subtitle_font = self._get_font(42, bold=True)
        name_font = self._get_font(56, bold=True)
        stats_font = self._get_font(40, bold=True)
        value_font = self._get_font(44, bold=True)

        title_text = "Weekly Leaderboard"
       

        # Title
        title_w = draw.textlength(title_text, font=title_font)
        title_x = (width - title_w) // 2
        title_y = margin_y
        draw.text((title_x, title_y), title_text, fill=(100, 200, 255), font=title_font)  # blue color


        # Draw cards for each user
        for idx, entry in enumerate(leaderboard[:10]):
            card_y = margin_y + header_height + (card_height + card_gap) * idx
            card_w = width - margin_x * 2
            card_x = margin_x

            # Get user info
            user_id = entry['user_id']
            member = guild.get_member(user_id)
            if not member:
                continue

            # Card background with shadow and optional glow for first place - different colors
            top_card = idx == 0
            card_color = (35, 45, 65) if idx % 2 == 0 else (30, 40, 60)  # blue-tinted cards
            self._draw_card_with_shadow(img, (card_x, card_y, card_x + card_w, card_y + card_height), radius=20, fill=card_color, glow=top_card)

            # Thin border around card - different color
            border = Image.new("RGBA", (card_w, card_height), (0, 0, 0, 0))
            border_draw = ImageDraw.Draw(border)
            border_draw.rounded_rectangle((0, 0, card_w - 1, card_height - 1), radius=20, outline=(80, 120, 180, 200), width=2)
            img.alpha_composite(border, (card_x, card_y))

            # Avatar - even bigger size
            avatar_size = 160
            avatar_x = card_x + 80
            avatar_y = card_y + (card_height - avatar_size) // 2
            avatar_img = await self._fetch_avatar_image(member)
            if avatar_img:
                # Resize and make circular
                avatar_img = avatar_img.resize((avatar_size, avatar_size), Image.LANCZOS)
                mask = Image.new("L", (avatar_size, avatar_size), 0)
                ImageDraw.Draw(mask).ellipse((0, 0, avatar_size, avatar_size), fill=255)
                avatar_with_mask = Image.new("RGBA", (avatar_size, avatar_size), (0, 0, 0, 0))
                avatar_with_mask.paste(avatar_img, (0, 0), mask)
                img.alpha_composite(avatar_with_mask, (avatar_x, avatar_y))

            # Rank emoji/icon inside card on left side of avatar - even bigger size
            rank_emoji = "🥇" if idx == 0 else ("🥈" if idx == 1 else ("🥉" if idx == 2 else "⭐"))
            emoji_font = self._get_emoji_font(100)
            emoji_x = avatar_x - 140  # inside card, to the left of avatar with more space
            avatar_center_y = avatar_y + avatar_size // 2

            if emoji_font:
                # Try to render emoji with font
                emoji_w = draw.textlength(rank_emoji, font=emoji_font)
                emoji_h = 100
                emoji_y = int(avatar_center_y - emoji_h / 2)
                draw.text((emoji_x, emoji_y), rank_emoji, fill=(255, 255, 255), font=emoji_font)
            else:
                # Fallback to PNG icon
                icon_img = self._get_rank_icon_image(idx, target_height=100)
                if icon_img:
                    emoji_y = int(avatar_center_y - icon_img.height / 2)
                    img.alpha_composite(icon_img, (emoji_x, emoji_y))

            # User name - even bigger and better positioned
            text_col_x = avatar_x + avatar_size + 50
            text_top_y = card_y + 35
            name = member.display_name
            draw.text((text_col_x, text_top_y), name, fill=(255, 255, 255), font=name_font)

            # Get voice time and message count from leaderboard data
            voice_minutes = entry.get('voice_time', 0) or 0
            messages_count = entry.get('message_count', 0) or 0
            
            # Voice time (convert minutes to hours)
            voice_hours = voice_minutes // 60
            voice_minutes_remainder = voice_minutes % 60
            
            # Voice time text
            if voice_hours > 0:
                voice_text = f"{voice_hours}h {voice_minutes_remainder}m studied"
            else:
                voice_text = f"{voice_minutes}m studied"
            
            # Stats text
            stats_text = f"🎤 {voice_text} • 💬 {messages_count:,} msgs"
            
            # Draw stats below name - even bigger and better positioned
            stats_y = text_top_y + 70
            draw.text((text_col_x, stats_y), stats_text, fill=(180, 200, 255), font=stats_font)
            
            # Weekly XP on right side (even bigger)
            weekly_xp = entry.get('weekly_xp', 0)
            score_text = f"{weekly_xp:,} XP"
            score_w = draw.textlength(score_text, font=value_font)
            score_x = card_x + card_w - score_w - 40
            score_y = card_y + (card_height - 50) // 2
            
            # Different colors for top 3
            score_color = (255, 215, 64) if idx == 0 else ((200, 200, 210) if idx == 1 else ((205, 127, 50) if idx == 2 else (180, 200, 255)))
            draw.text((score_x + 1, score_y + 1), score_text, fill=(0, 0, 0), font=value_font)
            draw.text((score_x, score_y), score_text, fill=score_color, font=value_font)

        # Export to bytes
        output = BytesIO()
        img.save(output, format="PNG")
        output.seek(0)
        return output



    async def _fetch_avatar_image(self, member: Optional[discord.Member]):
        if not member:
            return None
        try:
            avatar_bytes = await member.display_avatar.read()
            avatar_img = Image.open(BytesIO(avatar_bytes)).convert("RGBA")
            return avatar_img
        except Exception:
            return None

    def _draw_card_with_shadow(self, base_img: Image.Image, bbox: tuple, radius: int, fill: tuple, glow: bool = False):
        x0, y0, x1, y1 = bbox
        w = x1 - x0
        h = y1 - y0

        # Shadow layer
        shadow = Image.new("RGBA", (w + 10, h + 10), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
        shadow_draw.rounded_rectangle((5, 5, w + 5, h + 5), radius=radius, fill=(0, 0, 0, 160))
        shadow = shadow.filter(ImageFilter.GaussianBlur(6))
        base_img.alpha_composite(shadow, (x0 - 5, y0 - 4))

        # Optional glow for first place
        if glow:
            glow_layer = Image.new("RGBA", (w + 14, h + 14), (0, 0, 0, 0))
            glow_draw = ImageDraw.Draw(glow_layer)
            glow_color = (255, 215, 64, 180)  # soft gold
            glow_draw.rounded_rectangle((7, 7, w + 7, h + 7), radius=radius + 2, outline=glow_color, width=4)
            glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(8))
            base_img.alpha_composite(glow_layer, (x0 - 7, y0 - 7))

        # Card itself
        card = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        card_draw = ImageDraw.Draw(card)
        card_draw.rounded_rectangle((0, 0, w, h), radius=radius, fill=fill)
        base_img.alpha_composite(card, (x0, y0))

    def _draw_progress_bar(self, base_img: Image.Image, bbox: tuple, percentage: float):
        x0, y0, x1, y1 = bbox
        w = x1 - x0
        h = y1 - y0
        radius = h // 2

        # Background bar
        bar_bg = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        bg_draw = ImageDraw.Draw(bar_bg)
        bg_draw.rounded_rectangle((0, 0, w, h), radius=radius, fill=(70, 66, 82))

        # Foreground gradient
        fg_w = max(1, int(w * percentage))
        gradient = self._linear_gradient((255, 163, 26), (255, 64, 64), fg_w, h)
        mask = Image.new("L", (fg_w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, fg_w, h), radius=radius, fill=255)
        bar_bg.paste(gradient, (0, 0), mask)

        base_img.alpha_composite(bar_bg, (x0, y0))

    def _linear_gradient(self, start_rgb: tuple, end_rgb: tuple, width: int, height: int) -> Image.Image:
        gradient = Image.new("RGBA", (width, height), color=0)
        for x in range(width):
            t = x / max(1, width - 1)
            r = int(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * t)
            g = int(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * t)
            b = int(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * t)
            ImageDraw.Draw(gradient).line([(x, 0), (x, height)], fill=(r, g, b, 255))
        return gradient

    def _get_font(self, size: int, bold: bool = False):
        """Load a scalable TrueType font with a strong preference for Windows fonts.

        Preference order:
        1) Windows core fonts (Arial/Segoe UI) in the system Fonts directory
        2) Same fonts by family name (for fontconfig resolution on non-Windows)
        3) Other common sans fonts (Calibri/Verdana/Tahoma/Liberation/Noto)
        4) Finally fall back to PIL's default bitmap font
        """
        windir = os.environ.get("WINDIR", "C:/Windows")
        fonts_dir = os.path.join(windir, "Fonts")

        primary = [
            # Bold first if requested
            "arialbd.ttf" if bold else "arial.ttf",
            "segoeuib.ttf" if bold else "segoeui.ttf",
        ]

        secondary = [
            ("calibrib.ttf" if bold else "calibri.ttf"),
            ("verdanab.ttf" if bold else "verdana.ttf"),
            ("tahomabd.ttf" if bold else "tahoma.ttf"),
            # Cross-platform fallbacks
            ("LiberationSans-Bold.ttf" if bold else "LiberationSans-Regular.ttf"),
            ("NotoSans-Bold.ttf" if bold else "NotoSans-Regular.ttf"),
            ("HelveticaBold.ttf" if bold else "Helvetica.ttf"),
        ]

        candidates: list[str] = []
        # Full paths in Windows fonts dir
        for name in primary + secondary:
            candidates.append(os.path.join(fonts_dir, name))
        # Also try by name only (fontconfig may resolve on non-Windows)
        candidates.extend(primary + secondary)
        # Linux distro paths for Liberation/Noto
        candidates.extend([
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf" if not bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf" if not bold else "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        ])

        for path in candidates:
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue

        # Last resort: default bitmap font
        # Note: This does not scale perfectly but avoids crashes.
        return ImageFont.load_default()

    def _get_emoji_font(self, size: int):
        """Try to load an emoji-capable font if available.

        Attempts common system paths for emoji fonts on Windows, macOS, and Linux.
        Returns an ImageFont instance or None if not available.
        """
        if hasattr(self, "_cached_emoji_font_size") and getattr(self, "_cached_emoji_font_size") == size:
            return getattr(self, "_cached_emoji_font", None)

        emoji_font_paths = [
            # Linux
            "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
            "/usr/share/fonts/truetype/joypixels/JoyPixels.ttf",
            "/usr/share/fonts/NotoColorEmoji.ttf",
            # Windows
            os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts", "seguiemj.ttf"),  # Segoe UI Emoji
            os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts", "SegoeUIEmoji.ttf"),
            # macOS
            "/System/Library/Fonts/Apple Color Emoji.ttc",
        ]

        for path in emoji_font_paths:
            try:
                if os.path.exists(path):
                    # TTC collections are supported by PIL
                    font = ImageFont.truetype(path, size)
                    setattr(self, "_cached_emoji_font", font)
                    setattr(self, "_cached_emoji_font_size", size)
                    return font
            except Exception:
                continue

        setattr(self, "_cached_emoji_font", None)
        setattr(self, "_cached_emoji_font_size", size)
        return None

    def _generate_icon_png_b64(self, kind: str, size: int = 96) -> str:
        """Generate a simple fallback PNG icon as base64 (no external files).

        This is used when no emoji font is available.
        """
        icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(icon)

        if kind == "trophy":
            # Cup
            d.rounded_rectangle((18, 34, size - 18, size - 18), radius=16, fill=(255, 202, 40, 255))
            d.rectangle((size // 2 - 12, size - 18, size // 2 + 12, size - 10), fill=(180, 150, 20, 255))
            d.rectangle((size // 2 - 30, size - 10, size // 2 + 30, size - 4), fill=(210, 175, 30, 255))
            # Handles
            d.arc((6, 22, 36, 64), 270, 90, fill=(255, 202, 40, 255), width=10)
            d.arc((size - 36, 22, size - 6, 64), 90, 270, fill=(255, 202, 40, 255), width=10)
        elif kind == "silver":
            d.ellipse((12, 12, size - 12, size - 12), fill=(210, 215, 222, 255))
            d.ellipse((26, 26, size - 26, size - 26), fill=(245, 246, 248, 255))
            # Ribbon
            d.polygon([(size//2, size-12), (size//2-16, size-28), (size//2+16, size-28)], fill=(150, 170, 200, 255))
        elif kind == "bronze":
            d.ellipse((12, 12, size - 12, size - 12), fill=(205, 127, 50, 255))
            d.ellipse((26, 26, size - 26, size - 26), fill=(245, 210, 170, 255))
            d.polygon([(size//2, size-12), (size//2-16, size-28), (size//2+16, size-28)], fill=(160, 100, 40, 255))
        else:  # star
            cx = cy = size // 2
            r_outer = size * 0.44
            r_inner = size * 0.20
            points = []
            for i in range(10):
                angle = -math.pi / 2 + i * (math.pi / 5)
                r = r_outer if i % 2 == 0 else r_inner
                x = cx + r * math.cos(angle)
                y = cy + r * math.sin(angle)
                points.append((x, y))
            d.polygon(points, fill=(255, 222, 100, 255))

        buf = BytesIO()
        icon.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return b64

    def _get_rank_icon_image(self, rank_index: int, target_height: int) -> Image.Image:
        kind = "trophy" if rank_index == 0 else ("silver" if rank_index == 1 else ("bronze" if rank_index == 2 else "star"))
        if not hasattr(self, "_icon_b64_cache"):
            self._icon_b64_cache = {}
        if kind not in self._icon_b64_cache:
            self._icon_b64_cache[kind] = self._generate_icon_png_b64(kind)
        data = base64.b64decode(self._icon_b64_cache[kind])
        img = Image.open(BytesIO(data)).convert("RGBA")
        # Resize preserving aspect ratio to the target height
        w = int(img.width * (target_height / img.height))
        return img.resize((w, target_height), Image.LANCZOS)

    def _ordinal(self, n: int) -> str:
        if 10 <= n % 100 <= 20:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
        return f"{n}{suffix}"
    
    @commands.command(name="delete")
    async def delete_command(self, ctx, amount: int):
        """Delete the last N messages from the current channel"""
        # Check if user is owner or has manage messages permission
        if not (ctx.author.guild_permissions.manage_messages or ctx.author.id == ctx.guild.owner_id):
            await ctx.send("❌ You need 'Manage Messages' permission to use this command!")
            return
            
        if amount <= 0:
            await ctx.send("❌ Please specify a positive number of messages to delete!")
            return
        
        if amount > 100:
            await ctx.send("❌ You can only delete up to 100 messages at once!")
            return
        
        try:
            # Delete the command message first
            await ctx.message.delete()
            
            # Delete the specified number of messages
            deleted = await ctx.channel.purge(limit=amount)
            
            # Send confirmation message
            confirmation = await ctx.send(f"✅ Successfully deleted **{len(deleted)}** messages!")
            
            # Delete the confirmation message after 3 seconds
            await asyncio.sleep(3)
            await confirmation.delete()
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to delete messages in this channel!")
        except discord.HTTPException as e:
            await ctx.send(f"❌ Error deleting messages: {e}")
    
    @commands.command(name="clear")
    async def clear_command(self, ctx, amount: int):
        """Alias for delete command - delete the last N messages"""
        await self.delete_command(ctx, amount)
    
    @commands.command(name="resetxp")
    @commands.has_permissions(administrator=True)
    async def reset_xp_command(self, ctx, user: discord.Member):
        """Reset all XP data for a user (Admin only)"""
        try:
            # Reset all user data using the new database function
            success = self.db.reset_user_all(ctx.guild.id, user.id)
            
            if success:
                embed = discord.Embed(
                    title="✅ Complete XP Reset",
                    description=f"All XP data for {user.mention} has been completely reset!",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                embed.add_field(name="Reset by", value=ctx.author.mention, inline=True)
                embed.add_field(name="New Level", value="1", inline=True)
                embed.add_field(name="Permanent XP", value="0", inline=True)
                embed.add_field(name="Weekly XP", value="0", inline=True)
                embed.add_field(name="Voice Time", value="0 minutes", inline=True)
                embed.add_field(name="Messages", value="0", inline=True)
                
                await ctx.send(embed=embed)
            else:
                await ctx.send("❌ Failed to reset XP data!")
        except Exception as e:
            await ctx.send(f"❌ Error resetting XP: {e}")
    
    @set_xp_command.error
    @set_weekly_command.error
    @set_level_command.error
    @reset_weekly_command.error
    @exempt_command.error
    @config_command.error
    @set_cooldown_command.error
    @set_message_xp_command.error
    @set_voice_xp_command.error
    @set_voice_interval_command.error
    @add_message_channel_command.error
    @add_voice_channel_command.error
    @remove_message_channel_command.error
    @remove_voice_channel_command.error
    @set_role_command.error
    @remove_role_command.error
    @backup_command.error
    @reset_xp_command.error
    async def admin_command_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command!")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Missing required argument! Check the command usage.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Invalid argument provided! Check the command usage.")
        else:
            await ctx.send(f"❌ An error occurred: {error}")
    
    @delete_command.error
    @clear_command.error
    async def delete_command_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Please specify how many messages to delete! Example: `!delete 10`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Please provide a valid number! Example: `!delete 5`")
        else:
            await ctx.send(f"❌ An error occurred: {error}")
    
    @reset_xp_command.error
    async def reset_xp_command_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You need Administrator permission to use this command!")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Please specify a user! Example: `!resetxp @user`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Please provide a valid user! Example: `!resetxp @user`")
        else:
            await ctx.send(f"❌ An error occurred: {error}")

async def setup(bot):
    await bot.add_cog(XPCommands(bot, bot.xp_manager, bot.db, bot.config))
