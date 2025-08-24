import sqlite3
import json
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "xp_bot.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Users table for XP tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                permanent_xp INTEGER DEFAULT 0,
                weekly_xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                last_message_xp_timestamp REAL DEFAULT 0,
                last_voice_xp_timestamp REAL DEFAULT 0,
                voice_time INTEGER DEFAULT 0,
                message_count INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
        ''')
        
        # Add new columns if they don't exist (for existing databases)
        try:
            cursor.execute('ALTER TABLE users ADD COLUMN voice_time INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            cursor.execute('ALTER TABLE users ADD COLUMN message_count INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Voice sessions table for tracking voice activity
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS voice_sessions (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                join_time REAL NOT NULL,
                last_xp_tick REAL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
        ''')
        
        # Weekly leaderboard archive
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS weekly_archives (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                week_start_date TEXT NOT NULL,
                week_end_date TEXT NOT NULL,
                archive_data TEXT NOT NULL,
                created_at REAL DEFAULT (strftime('%s', 'now'))
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
    
    def get_user(self, guild_id: int, user_id: int) -> Optional[Dict]:
        """Get user data from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT permanent_xp, weekly_xp, level, last_message_xp_timestamp, last_voice_xp_timestamp, voice_time, message_count
            FROM users WHERE guild_id = ? AND user_id = ?
        ''', (guild_id, user_id))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'permanent_xp': result[0],
                'weekly_xp': result[1],
                'level': result[2],
                'last_message_xp_timestamp': result[3],
                'last_voice_xp_timestamp': result[4],
                'voice_time': result[5] if len(result) > 5 else 0,
                'message_count': result[6] if len(result) > 6 else 0
            }
        return None
    
    def create_user(self, guild_id: int, user_id: int) -> Dict:
        """Create a new user in the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR IGNORE INTO users (guild_id, user_id, permanent_xp, weekly_xp, level)
            VALUES (?, ?, 0, 0, 1)
        ''', (guild_id, user_id))
        
        conn.commit()
        conn.close()
        
        return {
            'permanent_xp': 0,
            'weekly_xp': 0,
            'level': 1,
            'last_message_xp_timestamp': 0,
            'last_voice_xp_timestamp': 0
        }
    
    def get_or_create_user(self, guild_id: int, user_id: int) -> Dict:
        """Get user data or create if doesn't exist"""
        user = self.get_user(guild_id, user_id)
        if user is None:
            user = self.create_user(guild_id, user_id)
        return user
    
    def award_message_xp(self, guild_id: int, user_id: int, xp_amount: int) -> bool:
        """Award XP for message activity"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE users 
                SET permanent_xp = permanent_xp + ?, 
                    weekly_xp = weekly_xp + ?,
                    last_message_xp_timestamp = ?
                WHERE guild_id = ? AND user_id = ?
            ''', (xp_amount, xp_amount, datetime.now().timestamp(), guild_id, user_id))
            
            conn.commit()
            success = cursor.rowcount > 0
            conn.close()
            return success
        except Exception as e:
            logger.error(f"Error awarding message XP: {e}")
            conn.rollback()
            conn.close()
            return False
    
    def award_voice_xp(self, guild_id: int, user_id: int, xp_amount: int) -> bool:
        """Award XP for voice activity"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE users 
                SET permanent_xp = permanent_xp + ?, 
                    weekly_xp = weekly_xp + ?,
                    last_voice_xp_timestamp = ?
                WHERE guild_id = ? AND user_id = ?
            ''', (xp_amount, xp_amount, datetime.now().timestamp(), guild_id, user_id))
            
            conn.commit()
            success = cursor.rowcount > 0
            conn.close()
            return success
        except Exception as e:
            logger.error(f"Error awarding voice XP: {e}")
            conn.rollback()
            conn.close()
            return False
    
    def set_user_xp(self, guild_id: int, user_id: int, permanent_xp: int, weekly_xp: int = None) -> bool:
        """Set user XP (admin command)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            if weekly_xp is not None:
                cursor.execute('''
                    UPDATE users 
                    SET permanent_xp = ?, weekly_xp = ?
                    WHERE guild_id = ? AND user_id = ?
                ''', (permanent_xp, weekly_xp, guild_id, user_id))
            else:
                cursor.execute('''
                    UPDATE users 
                    SET permanent_xp = ?
                    WHERE guild_id = ? AND user_id = ?
                ''', (permanent_xp, guild_id, user_id))
            
            conn.commit()
            success = cursor.rowcount > 0
            conn.close()
            return success
        except Exception as e:
            logger.error(f"Error setting user XP: {e}")
            conn.rollback()
            conn.close()
            return False
    
    def set_user_level(self, guild_id: int, user_id: int, level: int) -> bool:
        """Set user level (admin command)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE users 
                SET level = ?
                WHERE guild_id = ? AND user_id = ?
            ''', (level, guild_id, user_id))
            
            conn.commit()
            success = cursor.rowcount > 0
            conn.close()
            return success
        except Exception as e:
            logger.error(f"Error setting user level: {e}")
            conn.rollback()
            conn.close()
            return False
    
    def update_user_voice_time(self, guild_id: int, user_id: int, minutes: int) -> bool:
        """Update user's voice time"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE users SET voice_time = voice_time + ? WHERE guild_id = ? AND user_id = ?
            ''', (minutes, guild_id, user_id))
            
            conn.commit()
            success = cursor.rowcount > 0
            conn.close()
            return success
        except Exception as e:
            logger.error(f"Error updating voice time: {e}")
            conn.rollback()
            conn.close()
            return False
    
    def update_user_message_count(self, guild_id: int, user_id: int, count: int = 1) -> bool:
        """Update user's message count"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE users SET message_count = message_count + ? WHERE guild_id = ? AND user_id = ?
            ''', (count, guild_id, user_id))
            
            conn.commit()
            success = cursor.rowcount > 0
            conn.close()
            return success
        except Exception as e:
            logger.error(f"Error updating message count: {e}")
            conn.rollback()
            conn.close()
            return False
    
    def reset_user_all(self, guild_id: int, user_id: int) -> bool:
        """Reset all user data (XP, level, voice time, message count)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE users 
                SET permanent_xp = 0, 
                    weekly_xp = 0, 
                    level = 1, 
                    voice_time = 0, 
                    message_count = 0,
                    last_message_xp_timestamp = 0,
                    last_voice_xp_timestamp = 0
                WHERE guild_id = ? AND user_id = ?
            ''', (guild_id, user_id))
            
            conn.commit()
            success = cursor.rowcount > 0
            conn.close()
            return success
        except Exception as e:
            logger.error(f"Error resetting user data: {e}")
            conn.rollback()
            conn.close()
            return False
    
    def get_leaderboard(self, guild_id: int, limit: int = 10) -> List[Dict]:
        """Get permanent leaderboard with full stats"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, permanent_xp, level, voice_time, message_count
            FROM users 
            WHERE guild_id = ?
            ORDER BY permanent_xp DESC
            LIMIT ?
        ''', (guild_id, limit))
        
        results = cursor.fetchall()
        conn.close()
        
        return [
            {
                'user_id': row[0],
                'permanent_xp': row[1],
                'level': row[2],
                'voice_time': row[3] or 0,
                'message_count': row[4] or 0,
                'rank': i + 1
            }
            for i, row in enumerate(results)
        ]
    
    def get_weekly_leaderboard(self, guild_id: int, limit: int = 10) -> List[Dict]:
        """Get weekly leaderboard based on weekly XP with full stats"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, weekly_xp, voice_time, message_count
            FROM users 
            WHERE guild_id = ? AND weekly_xp > 0
            ORDER BY weekly_xp DESC
            LIMIT ?
        ''', (guild_id, limit))
        
        results = cursor.fetchall()
        conn.close()
        
        return [
            {
                'user_id': row[0],
                'weekly_xp': row[1],
                'voice_time': row[2] or 0,
                'message_count': row[3] or 0,
                'rank': i + 1
            }
            for i, row in enumerate(results)
        ]
    
    def get_user_rank(self, guild_id: int, user_id: int) -> Optional[int]:
        """Get user's rank in permanent leaderboard"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) + 1
            FROM users 
            WHERE guild_id = ? AND permanent_xp > (
                SELECT permanent_xp FROM users WHERE guild_id = ? AND user_id = ?
            )
        ''', (guild_id, guild_id, user_id))
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    
    def get_user_weekly_rank(self, guild_id: int, user_id: int) -> Optional[int]:
        """Get user's rank in weekly leaderboard"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) + 1
            FROM users 
            WHERE guild_id = ? AND weekly_xp > (
                SELECT weekly_xp FROM users WHERE guild_id = ? AND user_id = ?
            )
        ''', (guild_id, guild_id, user_id))
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    
    def reset_weekly_leaderboard(self, guild_id: int) -> bool:
        """Reset weekly leaderboard and archive current data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Get current weekly data
            cursor.execute('''
                SELECT user_id, weekly_xp
                FROM users 
                WHERE guild_id = ? AND weekly_xp > 0
            ''', (guild_id,))
            
            weekly_data = cursor.fetchall()
            
            # Archive current weekly data
            if weekly_data:
                week_start = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
                week_end = datetime.now().strftime('%Y-%m-%d')
                archive_data = json.dumps([{'user_id': row[0], 'weekly_xp': row[1]} for row in weekly_data])
                
                cursor.execute('''
                    INSERT INTO weekly_archives (guild_id, week_start_date, week_end_date, archive_data)
                    VALUES (?, ?, ?, ?)
                ''', (guild_id, week_start, week_end, archive_data))
            
            # Reset weekly XP, voice time, and message count
            cursor.execute('''
                UPDATE users 
                SET weekly_xp = 0, voice_time = 0, message_count = 0
                WHERE guild_id = ?
            ''', (guild_id,))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error resetting weekly leaderboard: {e}")
            conn.rollback()
            conn.close()
            return False
    
    def start_voice_session(self, guild_id: int, user_id: int, channel_id: int) -> bool:
        """Start tracking voice session"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO voice_sessions (guild_id, user_id, channel_id, join_time, last_xp_tick)
                VALUES (?, ?, ?, ?, ?)
            ''', (guild_id, user_id, channel_id, datetime.now().timestamp(), 0))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error starting voice session: {e}")
            conn.rollback()
            conn.close()
            return False
    
    def end_voice_session(self, guild_id: int, user_id: int) -> bool:
        """End voice session tracking"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                DELETE FROM voice_sessions 
                WHERE guild_id = ? AND user_id = ?
            ''', (guild_id, user_id))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error ending voice session: {e}")
            conn.rollback()
            conn.close()
            return False
    
    def get_active_voice_sessions(self, guild_id: int) -> List[Dict]:
        """Get all active voice sessions"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, channel_id, join_time, last_xp_tick
            FROM voice_sessions 
            WHERE guild_id = ?
        ''', (guild_id,))
        
        results = cursor.fetchall()
        conn.close()
        
        return [
            {
                'user_id': row[0],
                'channel_id': row[1],
                'join_time': row[2],
                'last_xp_tick': row[3]
            }
            for row in results
        ]
    
    def update_voice_tick(self, guild_id: int, user_id: int) -> bool:
        """Update last voice XP tick timestamp"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE voice_sessions 
                SET last_xp_tick = ?
                WHERE guild_id = ? AND user_id = ?
            ''', (datetime.now().timestamp(), guild_id, user_id))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error updating voice tick: {e}")
            conn.rollback()
            conn.close()
            return False
    
    def export_database(self, filename: str = None) -> str:
        """Export database to JSON file"""
        if filename is None:
            filename = f"xp_bot_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all users
        cursor.execute('SELECT * FROM users')
        users = cursor.fetchall()
        
        # Get all voice sessions
        cursor.execute('SELECT * FROM voice_sessions')
        voice_sessions = cursor.fetchall()
        
        # Get all weekly archives
        cursor.execute('SELECT * FROM weekly_archives')
        weekly_archives = cursor.fetchall()
        
        conn.close()
        
        # Create backup data
        backup_data = {
            'timestamp': datetime.now().isoformat(),
            'users': [
                {
                    'guild_id': row[0],
                    'user_id': row[1],
                    'permanent_xp': row[2],
                    'weekly_xp': row[3],
                    'level': row[4],
                    'last_message_xp_timestamp': row[5],
                    'last_voice_xp_timestamp': row[6]
                }
                for row in users
            ],
            'voice_sessions': [
                {
                    'guild_id': row[0],
                    'user_id': row[1],
                    'channel_id': row[2],
                    'join_time': row[3],
                    'last_xp_tick': row[4]
                }
                for row in voice_sessions
            ],
            'weekly_archives': [
                {
                    'id': row[0],
                    'guild_id': row[1],
                    'week_start_date': row[2],
                    'week_end_date': row[3],
                    'archive_data': row[4],
                    'created_at': row[5]
                }
                for row in weekly_archives
            ]
        }
        
        # Save to file
        with open(filename, 'w') as f:
            json.dump(backup_data, f, indent=2)
        
        return filename
