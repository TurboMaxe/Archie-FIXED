"""API client for ArchMC PIGDI API."""

from typing import Any, Dict, Optional

import requests


class PIGDIClient:
    """Client for interacting with the ArchMC API."""

    BASE_URL = "https://api.arch.mc"

    def __init__(self, api_key: str) -> None:
        """
        Initialize the PIGDI client.

        Args:
            api_key: The API key for authentication.
        """
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({"X-API-KEY": self.api_key})

    def _request(self, method: str, path: str, **kwargs: Any) -> Optional[Any]:
        """
        Make an HTTP request to the API.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: API endpoint path.
            **kwargs: Additional arguments passed to requests.

        Returns:
            JSON response data or text, or None on error.
        """
        url = f"{self.BASE_URL}{path}"
        resp = self.session.request(method, url, **kwargs)
        try:
            resp.raise_for_status()
        except requests.HTTPError:
            return None
        if resp.headers.get("Content-Type", "").startswith("application/json"):
            return resp.json()
        return resp.text

    def get_ugc_player_stats_by_username(
        self, gamemode: str, username: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get all statistics for a player by username.

        Args:
            gamemode: The gamemode identifier (e.g., 'trojan', 'spartan').
            username: The player's Minecraft username.

        Returns:
            Dictionary containing player statistics, or None on error.
        """
        path = f"/v1/ugc/{gamemode}/players/username/{username}/statistics"
        return self._request("GET", path)

    def get_ugc_leaderboard(
        self, gamemode: str, stat_type: str, page: int = 0, size: int = 10
    ) -> Optional[Dict[str, Any]]:
        """
        Get leaderboard for a statistic.

        Args:
            gamemode: The gamemode identifier.
            stat_type: The statistic type to get leaderboard for.
            page: Page number (0-indexed).
            size: Number of entries per page.

        Returns:
            Dictionary containing leaderboard data, or None on error.
        """
        path = f"/v1/ugc/{gamemode}/leaderboard/{stat_type}?page={page}&size={size}"
        return self._request("GET", path)

    def list_statistics(self) -> Optional[Dict[str, Any]]:
        """
        Get all available statistic IDs.

        Returns:
            Dictionary containing available statistics, or None on error.
        """
        path = "/v1/statistics"
        return self._request("GET", path)
