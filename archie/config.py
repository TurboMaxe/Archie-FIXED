"""Configuration module for Archie bot."""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    """Bot configuration loaded from environment variables."""

    TOKEN: str
    ARCH_API_KEY: str
    GUILD_JOIN_CHANNEL: int
    GUILD_LEAVE_CHANNEL: int
    BOT_ERRORS_CHANNEL: int

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        return cls(
            TOKEN=os.getenv("TOKEN", ""),
            ARCH_API_KEY=os.getenv("ARCH_API_KEY", ""),
            GUILD_JOIN_CHANNEL=int(os.getenv("GUILD_JOIN_CHANNEL", 0)),
            GUILD_LEAVE_CHANNEL=int(os.getenv("GUILD_LEAVE_CHANNEL", 0)),
            BOT_ERRORS_CHANNEL=1454137711710703785,
        )


config = Config.from_env()
