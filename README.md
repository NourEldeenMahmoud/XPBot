<div align="center">

# 🎮 Discord XP Bot

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Discord.py](https://img.shields.io/badge/discord.py-2.3+-blue.svg)](https://github.com/Rapptz/discord.py)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688.svg)](https://fastapi.tiangolo.com/)

A comprehensive Discord bot for managing XP, levels, and leaderboards with image generation capabilities.

[Features](#-features) • [Installation](#-installation) • [Configuration](#-configuration) • [Commands](#-commands) • [API](#-web-service-api) • [Contributing](#-contributing)

</div>

---

## ✨ Features

- **🎯 XP System**: Track user XP from messages and voice activity
- **📊 Level System**: Automatic level calculation with custom formulas (exponential or XP-anchors)
- **🎖️ Role Rewards**: Automatic role assignment based on levels
- **🏆 Leaderboards**: Beautiful image-based leaderboards (permanent & weekly)
- **⚙️ Admin Commands**: Full control over XP, levels, and settings
- **🌐 Web Service**: REST API for external integrations
- **🎤 Voice Tracking**: Real-time voice activity monitoring
- **💬 Message Tracking**: Smart message XP with cooldowns
- **🔒 Security**: Environment-based configuration with sensitive data protection

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- Discord Bot Token ([Get one here](https://discord.com/developers/applications))
- Discord Server (Guild) with appropriate permissions

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/NourEldeenMahmoud/XPBot.git
   cd XPBot
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp config/env.example .env
   # Edit .env with your actual values
   ```

4. **Set up configuration file**
   ```bash
   cp config/config.example.json config.json
   # Edit config.json with your server settings
   ```

5. **Configure your bot**
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Create a new application
   - Go to "Bot" section and copy the token
   - Enable required intents (Message Content, Server Members, Voice States)
   - Add the bot to your server with appropriate permissions

6. **Run the bot**
   ```bash
   python main.py
   ```
   Or:
   ```bash
   python -m src.bot
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

### Configuration File

The `config.json` file contains all bot settings:

- **XP Settings**: Message and voice XP ranges, cooldowns
- **Channel Whitelists**: Which channels track XP
- **Role Rewards**: Automatic role assignment at specific levels
- **Level Formula**: Customizable level calculation (exponential or XP-anchors)
- **Exempt Roles**: Roles that don't earn XP

See `config.example.json` for a template.

### Bot Permissions

The bot needs the following permissions:

- ✅ Send Messages
- ✅ Embed Links
- ✅ Attach Files
- ✅ Manage Messages (for delete command)
- ✅ Manage Roles (for role rewards)
- ✅ View Channels
- ✅ Connect (for voice tracking)
- ✅ Speak (for voice tracking)

**Required Intents:**
- Message Content Intent
- Server Members Intent
- Voice States Intent

## 📋 Commands

### User Commands

| Command | Description |
|---------|-------------|
| `!rank` | Show your current rank, XP, and level |
| `!leaderboard` | Show permanent leaderboard (top 10) |
| `!weeklyleaderboard` | Show weekly activity leaderboard (top 10) |

### Admin Commands

| Command | Description | Permission |
|---------|-------------|------------|
| `!setxp @user <amount>` | Set user's permanent XP | Administrator |
| `!setweekly @user <amount>` | Set user's weekly XP | Administrator |
| `!setlevel @user <level>` | Set user's level | Administrator |
| `!resetxp @user` | Reset all user data | Administrator |
| `!resetweekly` | Reset weekly leaderboard | Administrator |
| `!delete <amount>` | Delete last N messages | Manage Messages |
| `!config` | Show current configuration | Administrator |

## 🌐 Web Service API

The bot includes a FastAPI web service for external integrations:

### Base URL
```
http://localhost:8000
```

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Health check |
| `GET` | `/leaderboard?limit=10` | Get permanent leaderboard |
| `GET` | `/weeklyboard?limit=10` | Get weekly leaderboard |
| `GET` | `/user/{user_id}` | Get user statistics |
| `GET` | `/stats` | Get overall bot statistics |
| `GET` | `/config` | Get current bot configuration (read-only) |

### Example Response

```json
{
  "leaderboard": [
    {
      "rank": 1,
      "user_id": 123456789,
      "permanent_xp": 50000,
      "level": 25
    }
  ],
  "total_entries": 10,
  "guild_id": 987654321
}
```

## 📁 Project Structure

```
XPBot/
├── main.py                # Main entry point
├── src/                   # Source code
│   ├── bot.py             # Main bot entry point
│   ├── config_manager.py  # Configuration management
│   ├── database.py        # Database operations
│   ├── xp_manager.py      # XP and level calculations
│   ├── web_service.py     # FastAPI web service
│   └── cogs/              # Bot command modules
│       ├── xp_commands.py     # XP-related commands
│       ├── message_tracker.py # Message XP tracking
│       ├── voice_tracker.py   # Voice XP tracking
│       └── assistant.py       # Assistant features
├── config/                # Configuration files
│   ├── config.example.json    # Configuration template
│   └── env.example            # Environment variables template
├── tests/                 # Test files
│   └── test_bot.py        # Bot tests
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## 🔒 Security

### Important Security Notes

1. **Never commit sensitive files**
   - `.env` - Contains your bot token
   - `config.json` - Contains server-specific IDs
   - `*.db` - Database files

2. **Keep your bot token secret**
   - Anyone with the token can control your bot
   - Rotate tokens periodically
   - Use environment variables for all sensitive data

3. **Production Deployment**
   - Use environment variables for all configuration
   - Set up proper logging and monitoring
   - Use a production database (PostgreSQL recommended)
   - Enable rate limiting on web service
   - Set up health checks

## 🚀 Deployment

### Render (Recommended)

1. Connect your GitHub repository to Render
2. Create a new Web Service
3. Set environment variables in Render dashboard
4. Set build command: `pip install -r requirements.txt`
5. Set start command: `python bot.py`
6. Deploy!

### Heroku

1. Create a Heroku app
2. Set environment variables using `heroku config:set`
3. Deploy using Git: `git push heroku main`

### VPS/Dedicated Server

1. Clone the repository
2. Set up environment variables
3. Use systemd or PM2 for process management
4. Set up reverse proxy (nginx) for web service

### Docker (Coming Soon)

Docker support is planned for future releases.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct.

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [discord.py](https://github.com/Rapptz/discord.py) - Discord API wrapper
- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- Discord community for feedback and suggestions

## 📞 Support

- 🐛 [Report a Bug](https://github.com/NourEldeenMahmoud/XPBot/issues/new?template=bug_report.md)
- 💡 [Request a Feature](https://github.com/NourEldeenMahmoud/XPBot/issues/new?template=feature_request.md)
- ❓ [Ask a Question](https://github.com/NourEldeenMahmoud/XPBot/issues/new?template=question.md)

---

<div align="center">

**Made with ❤️ for the Discord community**

⭐ Star this repo if you find it helpful!

</div>
