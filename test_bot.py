#!/usr/bin/env python3
"""
Test script for XPBot functionality
This script simulates XP awarding and tests various bot features
"""

import asyncio
import random
import time
from datetime import datetime, timedelta
from database import Database
from config_manager import ConfigManager
from xp_manager import XPManager

class MockBot:
    """Mock bot class for testing"""
    def __init__(self):
        self.user = type('User', (), {'id': 123456789})()
        self.guild = type('Guild', (), {'id': 1234567890123456789})()

class MockMember:
    """Mock member class for testing"""
    def __init__(self, user_id, name, roles=None):
        self.id = user_id
        self.name = name
        self.bot = False
        self.roles = roles or []
        self.color = type('Color', (), {'default': lambda: True})()
        self.display_avatar = type('Avatar', (), {'url': 'https://example.com/avatar.png'})()

class MockChannel:
    """Mock channel class for testing"""
    def __init__(self, channel_id, name, channel_type="text"):
        self.id = channel_id
        self.name = name
        self.type = channel_type

class MockGuild:
    """Mock guild class for testing"""
    def __init__(self, guild_id):
        self.id = guild_id
        self.members = {}
        self.channels = {}
        self.roles = {}
    
    def get_member(self, user_id):
        return self.members.get(user_id)
    
    def get_channel(self, channel_id):
        return self.channels.get(channel_id)
    
    def get_role(self, role_id):
        return self.roles.get(role_id)

def test_xp_calculation():
    """Test XP and level calculations"""
    print("🧪 Testing XP and Level Calculations...")
    
    config = ConfigManager()
    db = Database()
    xp_manager = XPManager(MockBot(), db, config)
    
    # Test level calculations
    test_cases = [
        (0, 1),
        (50, 1),
        (100, 1),
        (150, 2),
        (225, 2),
        (337, 3),
        (1000, 4),
        (5000, 6)
    ]
    
    for xp, expected_level in test_cases:
        calculated_level = xp_manager.calculate_level(xp)
        status = "✅" if calculated_level == expected_level else "❌"
        print(f"  {status} {xp} XP → Level {calculated_level} (expected: {expected_level})")
    
    print()

def test_message_xp_simulation():
    """Simulate message XP awarding"""
    print("💬 Testing Message XP Simulation...")
    
    config = ConfigManager()
    db = Database()
    xp_manager = XPManager(MockBot(), db, config)
    
    guild = MockGuild(1234567890123456789)
    channel = MockChannel(1234567890123456789, "test-channel")
    member = MockMember(123456789, "TestUser")
    
    guild.members[member.id] = member
    guild.channels[channel.id] = channel
    
    # Simulate multiple messages
    total_xp = 0
    for i in range(5):
        # Simulate cooldown
        if i > 0:
            time.sleep(0.1)
        
        # Award XP
        result = asyncio.run(xp_manager.award_message_xp(guild, member, channel))
        
        if result:
            total_xp += result['xp_awarded']
            print(f"  ✅ Message {i+1}: +{result['xp_awarded']} XP (Total: {total_xp})")
            if result['leveled_up']:
                print(f"    🎉 Leveled up from {result['old_level']} to {result['new_level']}!")
        else:
            print(f"  ⏰ Message {i+1}: Cooldown active")
    
    print()

def test_voice_xp_simulation():
    """Simulate voice XP awarding"""
    print("🎤 Testing Voice XP Simulation...")
    
    config = ConfigManager()
    db = Database()
    xp_manager = XPManager(MockBot(), db, config)
    
    guild = MockGuild(1234567890123456789)
    channel = MockChannel(1234567890123456789, "test-voice", "voice")
    member = MockMember(123456789, "TestUser")
    
    guild.members[member.id] = member
    guild.channels[channel.id] = channel
    
    # Start voice session
    db.start_voice_session(guild.id, member.id, channel.id)
    print("  ✅ Voice session started")
    
    # Simulate voice ticks
    for i in range(3):
        time.sleep(0.1)  # Simulate time passing
        
        result = asyncio.run(xp_manager.award_voice_xp(guild, member, channel))
        
        if result:
            print(f"  ✅ Voice tick {i+1}: +{result['xp_awarded']} XP")
            if result['leveled_up']:
                print(f"    🎉 Leveled up from {result['old_level']} to {result['new_level']}!")
        else:
            print(f"  ⏰ Voice tick {i+1}: Cooldown active")
    
    # End voice session
    db.end_voice_session(guild.id, member.id)
    print("  ✅ Voice session ended")
    print()

def test_leaderboard():
    """Test leaderboard functionality"""
    print("🏆 Testing Leaderboard Functionality...")
    
    config = ConfigManager()
    db = Database()
    
    guild_id = 1234567890123456789
    
    # Create some test users
    test_users = [
        (111111111, "User1"),
        (222222222, "User2"),
        (333333333, "User3"),
        (444444444, "User4"),
        (555555555, "User5")
    ]
    
    for user_id, name in test_users:
        # Create user with random XP
        permanent_xp = random.randint(100, 5000)
        weekly_xp = random.randint(10, 500)
        
        db.set_user_xp(guild_id, user_id, permanent_xp, weekly_xp)
        print(f"  ✅ Created user {name}: {permanent_xp} total XP, {weekly_xp} weekly XP")
    
    # Test permanent leaderboard
    leaderboard = db.get_leaderboard(guild_id, 5)
    print(f"  📊 Permanent Leaderboard (Top 5):")
    for entry in leaderboard:
        print(f"    #{entry['rank']}: {entry['permanent_xp']} XP (Level {entry['level']})")
    
    # Test weekly leaderboard
    weekly_board = db.get_weekly_leaderboard(guild_id, 5)
    print(f"  📅 Weekly Leaderboard (Top 5):")
    for entry in weekly_board:
        print(f"    #{entry['rank']}: {entry['weekly_xp']} XP")
    
    print()

def test_role_rewards():
    """Test role reward system"""
    print("🎖️ Testing Role Reward System...")
    
    config = ConfigManager()
    db = Database()
    xp_manager = XPManager(MockBot(), db, config)
    
    guild = MockGuild(1234567890123456789)
    member = MockMember(123456789, "TestUser")
    
    # Test different levels
    test_levels = [5, 10, 20, 30, 50]
    
    for level in test_levels:
        # Calculate XP needed for this level
        xp_needed = xp_manager.calculate_xp_for_level(level)
        
        # Set user to this level
        db.set_user_xp(guild.id, member.id, xp_needed)
        db.set_user_level(guild.id, member.id, level)
        
        # Get appropriate reward role
        reward_role_id = xp_manager.get_appropriate_reward_role(level)
        
        if reward_role_id:
            print(f"  ✅ Level {level}: Reward role ID {reward_role_id}")
        else:
            print(f"  ❌ Level {level}: No reward role configured")
    
    print()

def test_config_validation():
    """Test configuration validation"""
    print("⚙️ Testing Configuration Validation...")
    
    config = ConfigManager()
    issues = config.validate_config()
    
    if issues:
        print("  ❌ Configuration issues found:")
        for issue in issues:
            print(f"    - {issue}")
    else:
        print("  ✅ Configuration is valid")
    
    print()

def test_database_backup():
    """Test database backup functionality"""
    print("💾 Testing Database Backup...")
    
    db = Database()
    
    try:
        filename = db.export_database()
        print(f"  ✅ Database backup created: {filename}")
    except Exception as e:
        print(f"  ❌ Backup failed: {e}")
    
    print()

def main():
    """Run all tests"""
    print("🤖 XPBot Test Suite")
    print("=" * 50)
    
    try:
        test_xp_calculation()
        test_message_xp_simulation()
        test_voice_xp_simulation()
        test_leaderboard()
        test_role_rewards()
        test_config_validation()
        test_database_backup()
        
        print("✅ All tests completed!")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
