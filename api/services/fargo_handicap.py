"""
Fargo-based handicap calculator for tournament matches.
Per EXTERNALPOOL_ANALYSIS: every 40 pts diff = -1 rack; caps; high-rated bonus.
"""

from typing import Optional, Tuple


def calculate_handicap(
    operator_fargo: Optional[int],
    player2_fargo: Optional[int],
    race_to: int = 7,
    bracket_type: str = "winners",
) -> Tuple[int, int]:
    """
    Calculate handicapped race-to for each player.

    Rules (from ExternalPool/Fargo):
    - Every 40 points Fargo difference = -1 rack from lower player's race
    - Max reduction: -3 racks on winners side, -2 on losers side
    - 680-740 Fargo: +1 rack for higher-rated player
    - 741+ Fargo: +2 racks for higher-rated player

    Returns:
        (operator_race, player2_race) - race-to for each player
    """
    if operator_fargo is None and player2_fargo is None:
        return race_to, race_to
    if operator_fargo is None:
        operator_fargo = 0
    if player2_fargo is None:
        player2_fargo = 0

    p1 = int(operator_fargo)
    p2 = int(player2_fargo)
    diff = abs(p1 - p2)
    rack_adjustment = diff // 40
    max_reduction = 3 if bracket_type.lower() == "winners" else 2
    rack_adjustment = min(rack_adjustment, max_reduction)

    # Base races
    if p1 < p2:
        p1_race = max(race_to - rack_adjustment, 3)
        p2_race = race_to
    elif p1 > p2:
        p1_race = race_to
        p2_race = max(race_to - rack_adjustment, 3)
    else:
        p1_race = race_to
        p2_race = race_to

    # High-rated bonus
    def add_bonus(rating: int) -> int:
        if rating >= 741:
            return 2
        if rating >= 680:
            return 1
        return 0

    p1_race += add_bonus(p1)
    p2_race += add_bonus(p2)

    return p1_race, p2_race
