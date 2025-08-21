# 🎮 Discord XP Bot

A comprehensive Discord bot for managing XP, levels, and leaderboards with image generation capabilities.

## ✨ Features

- **XP System**: Track user XP from messages and voice activity
- **Level System**: Automatic level calculation with custom formulas
- **Role Rewards**: Automatic role assignment based on levels
- **Leaderboards**: Beautiful image-based leaderboards (permanent & weekly)
- **Admin Commands**: Full control over XP, levels, and settings
- **Web Service**: REST API for external integrations
- **Voice Tracking**: Real-time voice activity monitoring
- **Message Tracking**: Smart message XP with cooldowns

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Discord Bot Token
- Discord Server (Guild)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/discord-xp-bot.git
   cd discord-xp-bot
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp env.example .env
   # Edit .env with your actual values
   ```

4. **Configure your bot**
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Create a new application
   - Go to "Bot" section and copy the token
   - Add the bot to your server with appropriate permissions

5. **Run the bot**
   ```bash
   python bot.py
   ```

## 🔧 Configuration

### Environment Variables

Create a `.env` file with the following variables:

```env
# Required
DISCORD_TOKEN=your_discord_bot_token_here
GUILD_ID=your_guild_id_here

# Optional
ANNOUNCEMENTS_CHANNEL_ID=your_announcements_channel_id_here
MOD_LOG_CHANNEL_ID=your_mod_log_channel_id_here
WEBHOOK_URL=your_webhook_url_here
DATABASE_PATH=xp_bot.db
LOG_LEVEL=INFO
```

### Bot Permissions

The bot needs the following permissions:
- Send Messages
- Embed Links
- Attach Files
- Manage Messages (for delete command)
- Manage Roles (for role rewards)
- View Channels
- Connect (for voice tracking)
- Speak (for voice tracking)

## 📋 Commands

### User Commands
- `!rank` - Show your current rank and XP
- `!leaderboard` - Show permanent leaderboard
- `!weeklyleaderboard` - Show weekly activity leaderboard

### Admin Commands
- `!setxp @user <amount>` - Set user's permanent XP
- `!setweekly @user <amount>` - Set user's weekly XP
- `!setlevel @user <level>` - Set user's level
- `!resetxp @user` - Reset all user data
- `!resetweekly` - Reset weekly leaderboard
- `!delete <amount>` - Delete last N messages
- `!config` - Show current configuration

## 🌐 Web Service

The bot includes a FastAPI web service for external integrations:

### Endpoints
- `GET /` - Health check
- `GET /leaderboard?limit=10` - Get permanent leaderboard
- `GET /weeklyboard?limit=10` - Get weekly leaderboard



## 🔒 Security

### Important Security Notes

1. **Never commit your `.env` file** - It contains sensitive data
2. **Keep your bot token secret** - Anyone with the token can control your bot
3. **Use environment variables** - Don't hardcode sensitive data
4. **Regular token rotation** - Change your bot token periodically

### Safe Deployment

For production deployment:
1. Use environment variables for all sensitive data
2. Set up proper logging
3. Use a production database (PostgreSQL recommended)
4. Set up monitoring and health checks

## 🚀 Deployment

### Render (Recommended)
1. Connect your GitHub repository to Render
2. Create a new Web Service
3. Set environment variables in Render dashboard
4. Deploy!

### Heroku
1. Create a Heroku app
2. Set environment variables
3. Deploy using Git

### VPS/Dedicated Server
1. Clone the repository
2. Set up environment variables
3. Use systemd or PM2 for process management

## ⚠️ Disclaimer

This bot is for educational and personal use. Make sure to comply with Discord's Terms of Service and your server's rules.



**Made with ❤️ for the Discord community**
