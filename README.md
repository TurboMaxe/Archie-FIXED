# 🎮 Archie

A Discord bot for ArchMC Minecraft server statistics, leaderboards, and economy tracking.

## Features

- **Lifesteal Stats** - View player lifesteal statistics and rankings
- **Duel Stats** - Track duel wins, losses, and K/D ratios
- **Economy/Balance** - Check player balances and economy data
- **Leaderboards** - Server-wide rankings across all stats
- **Clan Stats** - View clan information and member stats
- **Playtime** - Track player playtime on the server

## Prerequisites

- Python 3.10+
- Discord bot token
- ArchMC API key

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/archie.git
   cd archie
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   # or
   venv\Scripts\activate  # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your tokens and settings
   ```

5. Run the bot:
   ```bash
   python bot.py
   ```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `TOKEN` | Discord bot token | Yes |
| `ARCH_API_KEY` | ArchMC API key | Yes |
| `GUILD_JOIN_CHANNEL` | Channel ID for join notifications | No |
| `GUILD_LEAVE_CHANNEL` | Channel ID for leave notifications | No |

## Commands

| Command | Description |
|---------|-------------|
| `/stats <player>` | View player statistics |
| `/lifesteal <player>` | View lifesteal stats |
| `/duel <player>` | View duel statistics |
| `/balance <player>` | Check player balance |
| `/leaderboard <type>` | View server leaderboards |
| `/clan <name>` | View clan information |
| `/playtime <player>` | Check player playtime |

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
