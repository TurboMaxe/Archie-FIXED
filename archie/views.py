"""Discord UI views for Archie bot."""

from typing import Any, Dict, List, Tuple

import discord
from discord.ui import Button, View

from .embeds import build_duelstats_embed


class DuelStatsView(View):
    """Paginated view for duel stats."""

    def __init__(
        self,
        data: Dict[str, Any],
        username: str,
        mode_stats: Dict[str, Dict[str, List[Tuple[str, Any]]]],
        mode_keys: List[str],
        page: int,
    ) -> None:
        super().__init__(timeout=60)
        self.data = data
        self.username = username
        self.mode_stats = mode_stats
        self.mode_keys = mode_keys
        self.page = page
        self.modes_per_page = 4
        self.max_page = (len(mode_keys) - 1) // self.modes_per_page

        if self.page > 0:
            self.add_item(self.PrevButton(self))
        if self.page < self.max_page:
            self.add_item(self.NextButton(self))

    class PrevButton(Button):
        def __init__(self, parent: "DuelStatsView") -> None:
            super().__init__(label="Prev", style=discord.ButtonStyle.primary)
            self.parent = parent

        async def callback(self, interaction: discord.Interaction) -> None:
            if self.parent.page > 0:
                self.parent.page -= 1
                embed = build_duelstats_embed(
                    self.parent.data,
                    self.parent.username,
                    self.parent.mode_stats,
                    self.parent.mode_keys,
                    self.parent.page,
                    self.parent.modes_per_page,
                )
                new_view = DuelStatsView(
                    self.parent.data,
                    self.parent.username,
                    self.parent.mode_stats,
                    self.parent.mode_keys,
                    self.parent.page,
                )
                await interaction.response.edit_message(embed=embed, view=new_view)

    class NextButton(Button):
        def __init__(self, parent: "DuelStatsView") -> None:
            super().__init__(label="Next", style=discord.ButtonStyle.primary)
            self.parent = parent

        async def callback(self, interaction: discord.Interaction) -> None:
            if self.parent.page < self.parent.max_page:
                self.parent.page += 1
                embed = build_duelstats_embed(
                    self.parent.data,
                    self.parent.username,
                    self.parent.mode_stats,
                    self.parent.mode_keys,
                    self.parent.page,
                    self.parent.modes_per_page,
                )
                new_view = DuelStatsView(
                    self.parent.data,
                    self.parent.username,
                    self.parent.mode_stats,
                    self.parent.mode_keys,
                    self.parent.page,
                )
                await interaction.response.edit_message(embed=embed, view=new_view)
