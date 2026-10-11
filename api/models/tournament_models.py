"""
Tournament Management API Models
Pydantic models for request/response validation
"""

from pydantic import BaseModel, ConfigDict, Field, validator
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from enum import Enum


class MembershipStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    LIFETIME = "lifetime"


class TournamentStatus(str, Enum):
    SETUP = "setup"
    REGISTRATION = "registration"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class EliminationType(str, Enum):
    SINGLE = "single"
    DOUBLE = "double"
    ROUND_ROBIN = "round_robin"
    GROUP_STAGE = "group_stage"


class MatchStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BYE = "bye"


class BracketType(str, Enum):
    WINNERS = "winners"
    LOSERS = "losers"
    GRAND_FINAL = "grand_final"


# ==========================================
# PLAYER MODELS
# ==========================================

class PlayerBase(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    nickname: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = None
    phone: Optional[str] = None
    license_number: Optional[str] = None
    license_expiry_date: Optional[str] = Field(None, description="YYYY-MM-DD; manual entry")
    avatar_url: Optional[str] = None
    fargo_score: Optional[float] = Field(None, ge=0, le=1000)
    fargo_robustness: Optional[int] = Field(None, description="Fargo robustness/games count")
    fargo_last_sync: Optional[str] = Field(None, description="ISO datetime of last Fargo sync")
    fargo_source: Optional[str] = Field(None, description="fairmatch, rankings, manual")
    nationality: Optional[str] = Field(
        None,
        max_length=255,
        description="Country or region (alpha-3 code or full name; DB VARCHAR(255))",
    )
    hometown: Optional[str] = None
    state: Optional[str] = Field(None, max_length=2)
    membership_status: MembershipStatus = MembershipStatus.ACTIVE
    hall_of_fame: bool = False


class PlayerCreate(PlayerBase):
    pass


class PlayerUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    nickname: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = None
    phone: Optional[str] = None
    license_number: Optional[str] = None
    license_expiry_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    avatar_url: Optional[str] = None
    fargo_score: Optional[int] = Field(None, ge=0, le=1000)
    fargo_robustness: Optional[int] = None
    fargo_last_sync: Optional[str] = None
    fargo_source: Optional[str] = None
    nationality: Optional[str] = Field(None, max_length=255)
    hometown: Optional[str] = None
    state: Optional[str] = Field(None, max_length=2)
    membership_status: Optional[MembershipStatus] = None
    hall_of_fame: Optional[bool] = None


class PlayerResponse(PlayerBase):
    player_id: str
    license_overdue: Optional[bool] = Field(None, description="True if license_expiry_date < today")
    total_tournaments_played: int = 0
    total_points: float = 0.0
    current_rank: Optional[int] = None
    hot_streak_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlayerStatsResponse(BaseModel):
    player_id: str
    total_tournaments: int = 0
    total_matches_played: int = 0
    total_matches_won: int = 0
    total_games_played: int = 0
    total_games_won: int = 0
    win_percentage_matches: float = 0.0
    win_percentage_games: float = 0.0
    first_place_finishes: int = 0
    second_place_finishes: int = 0
    third_place_finishes: int = 0
    average_placement: Optional[float] = None
    best_placement: Optional[int] = None
    current_streak: int = 0
    longest_streak: int = 0


# ==========================================
# TOURNAMENT MODELS
# ==========================================

class TournamentBase(BaseModel):
    tournament_name: str = Field(..., min_length=3, max_length=200)
    tournament_date: date
    location: Optional[str] = None
    elimination_type: EliminationType
    max_players: int = Field(32, ge=2, le=256)
    stage2_cutoff: Optional[int] = Field(None, ge=2, le=256)
    stage2_elimination_type: Optional[EliminationType] = None
    stage2_seed_strategy: Optional[str] = None
    stage2_started_at: Optional[datetime] = None
    # Group Stage specific fields
    num_groups: Optional[int] = Field(None, ge=2, le=16, description="Number of groups for group stage tournaments")
    players_per_group: Optional[int] = Field(None, ge=2, le=32, description="Players per group (used with num_groups)")
    group_advance_count: Optional[int] = Field(None, ge=1, le=8, description="Number of players advancing from each group")
    group_format: Optional[str] = Field(None, description="Format within groups: 'round_robin' or 'single_elimination'")
    points_structure: Dict[str, float] = Field(
        ...,
        description="Points for each placement: {'1': 2880, '2': 3600, ...}"
    )
    notes: Optional[str] = None
    game_type: Optional[str] = Field(None, max_length=64, description="e.g. 9_ball, 10_ball")
    association: Optional[str] = Field(
        None,
        max_length=64,
        description="Ranking association tag (e.g. WPA_Women, WPBA_Women); required for directors",
    )
    tournament_end_date: Optional[date] = None
    bracket_template_id: Optional[int] = Field(
        None, description="Saved bracket layout preset (bracket_templates.id)"
    )


class TournamentCreate(TournamentBase):
    template_id: Optional[int] = None
    created_by: Optional[str] = None


class TournamentUpdate(BaseModel):
    tournament_name: Optional[str] = Field(None, min_length=3, max_length=200)
    tournament_date: Optional[date] = None
    location: Optional[str] = None
    status: Optional[TournamentStatus] = None
    points_structure: Optional[Dict[str, float]] = None
    notes: Optional[str] = None
    stage2_cutoff: Optional[int] = Field(None, ge=2, le=256)
    stage2_elimination_type: Optional[EliminationType] = None
    stage2_seed_strategy: Optional[str] = None
    stage2_started_at: Optional[datetime] = None


class TournamentResponse(TournamentBase):
    tournament_id: str
    actual_players: int = 0
    status: TournamentStatus
    template_id: Optional[int] = None
    created_by: Optional[str] = None
    winner_player_id: Optional[str] = None
    runner_up_player_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TournamentDetailResponse(TournamentResponse):
    players: List[Dict] = []
    matches_count: int = 0
    completed_matches: int = 0


# ==========================================
# TOURNAMENT TEMPLATE MODELS
# ==========================================

class TournamentTemplateBase(BaseModel):
    template_name: str = Field(..., min_length=3, max_length=200)
    elimination_type: EliminationType
    max_players: int = Field(32, ge=2, le=256)
    points_structure: Dict[str, float]
    description: Optional[str] = None


class TournamentTemplateCreate(TournamentTemplateBase):
    created_by: Optional[str] = None


class TournamentTemplateResponse(TournamentTemplateBase):
    id: int
    times_used: int = 0
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# BRACKET TEMPLATE MODELS (draw structure presets)
# ==========================================


class BracketTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    player_count: int = Field(..., ge=2, le=512)
    bracket_draw_size: int = Field(..., ge=2, le=512)
    format: str = Field(..., max_length=32, description="single_elimination | double_elimination | round_robin")
    bye_strategy: str = Field("top_seed", max_length=32)
    rounds: List[Dict[str, Any]] = Field(..., description="Round structure, e.g. [{round: 1, matches: 8}, ...]")
    association: Optional[str] = Field(None, max_length=64)


class BracketTemplateResponse(BaseModel):
    id: int
    name: str
    player_count: int
    bracket_draw_size: int
    format: str
    bye_strategy: str
    rounds: List[Dict[str, Any]]
    association: Optional[str] = None
    is_system: bool = False
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# TOURNAMENT PLAYER MODELS
# ==========================================

class TournamentPlayerRegister(BaseModel):
    player_id: str
    seed_position: Optional[int] = None


class TournamentPlayerResponse(BaseModel):
    player_id: str
    first_name: str
    last_name: str
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    seed_position: Optional[int] = None
    final_placement: Optional[int] = None
    points_earned: float = 0.0
    matches_played: int = 0
    matches_won: int = 0
    matches_lost: int = 0
    total_games_won: int = 0
    total_games_lost: int = 0
    check_in_at: Optional[str] = Field(None, description="ISO datetime when player checked in")


# ==========================================
# MATCH MODELS
# ==========================================

class MatchCreate(BaseModel):
    tournament_id: str
    round_number: int = Field(..., ge=1)
    match_number: int = Field(..., ge=1)
    bracket_type: BracketType = BracketType.WINNERS
    operator_id: Optional[str] = None
    player2_id: Optional[str] = None
    race_to: Optional[int] = Field(None, ge=1)
    scheduled_time: Optional[datetime] = None
    table_number: Optional[int] = None


class MatchUpdate(BaseModel):
    operator_id: Optional[str] = None
    player2_id: Optional[str] = None
    operator_score: Optional[int] = Field(None, ge=0)
    player2_score: Optional[int] = Field(None, ge=0)
    status: Optional[MatchStatus] = None
    scheduled_time: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    table_number: Optional[int] = None
    notes: Optional[str] = None


class MatchScoreUpdate(BaseModel):
    operator_score: int = Field(..., ge=0)
    player2_score: int = Field(..., ge=0)
    status: MatchStatus = MatchStatus.COMPLETED


class MatchOutcomeUpdate(BaseModel):
    """Director records forfeit or DQ with reason."""
    outcome: str = Field(..., description="forfeit or dq")
    reason: str = Field(..., min_length=1, description="Reason for forfeit/DQ")
    winner_id: Optional[str] = Field(None, description="Player who advances (opponent of forfeiting/DQ'd player)")


class MatchResponse(BaseModel):
    match_id: str
    tournament_id: str
    round_number: int
    match_number: int
    bracket_type: BracketType
    operator_id: Optional[str] = None
    player2_id: Optional[str] = None
    operator_name: Optional[str] = None
    player2_name: Optional[str] = None
    operator_score: int = 0
    player2_score: int = 0
    winner_id: Optional[str] = None
    loser_id: Optional[str] = None
    status: MatchStatus
    race_to: Optional[int] = None
    scheduled_time: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    table_number: Optional[int] = None
    notes: Optional[str] = None
    outcome: Optional[str] = Field(None, description="normal, forfeit, dq")
    outcome_reason: Optional[str] = None
    operator_handicapped_race: Optional[int] = Field(None, description="Race-to for operator when handicap applied")
    player2_handicapped_race: Optional[int] = Field(None, description="Race-to for player2 when handicap applied")
    handicap_applied: bool = Field(False, description="True if Fargo handicap was applied")
    projected_start_time: Optional[str] = Field(None, description="Estimated match start (ISO datetime)")
    projected_end_time: Optional[str] = Field(None, description="Estimated match end (ISO datetime)")

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# GAME/RACK MODELS
# ==========================================

class GameCreate(BaseModel):
    """Create a new game/rack result within a match"""
    match_id: str = Field(..., description="Match this game belongs to")
    game_number: int = Field(..., ge=1, description="Game/rack number (1, 2, 3...)")
    winner_id: str = Field(..., description="Player who won this game")
    breaking_player_id: Optional[str] = Field(None, description="Player who broke")
    innings: Optional[int] = Field(None, ge=0, description="Number of innings played")
    run_out: bool = Field(False, description="True if winner ran out")
    break_and_run: bool = Field(False, description="True if winner broke and ran")
    notes: Optional[str] = Field(None, description="Optional notes about the game")


class GameUpdate(BaseModel):
    """Update an existing game/rack result"""
    winner_id: Optional[str] = Field(None, description="Player who won this game")
    breaking_player_id: Optional[str] = Field(None, description="Player who broke")
    innings: Optional[int] = Field(None, ge=0, description="Number of innings played")
    run_out: Optional[bool] = Field(None, description="True if winner ran out")
    break_and_run: Optional[bool] = Field(None, description="True if winner broke and ran")
    notes: Optional[str] = Field(None, description="Optional notes about the game")


class GameResponse(BaseModel):
    """Game/rack response model"""
    id: int
    match_id: str
    game_number: int
    winner_id: Optional[str] = None
    winner_name: Optional[str] = None
    breaking_player_id: Optional[str] = None
    breaking_player_name: Optional[str] = None
    innings: Optional[int] = None
    run_out: bool = False
    break_and_run: bool = False
    notes: Optional[str] = None
    completed_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# BRACKET MODELS
# ==========================================

class BracketNode(BaseModel):
    """Represents a node in the tournament bracket tree"""
    match_id: Optional[str] = None
    round_number: int
    match_number: int
    bracket_type: BracketType
    operator: Optional[Dict] = None  # {player_id, name, seed}
    player2: Optional[Dict] = None
    winner: Optional[Dict] = None
    score: Optional[str] = None  # e.g., "7-3"
    status: MatchStatus
    next_match_id: Optional[str] = None  # Winner advances to this match
    loser_match_id: Optional[str] = None  # For double elimination


class BracketResponse(BaseModel):
    tournament_id: str
    tournament_name: str
    elimination_type: EliminationType
    winners_bracket: List[List[BracketNode]] = []  # List of rounds, each round has list of matches
    losers_bracket: Optional[List[List[BracketNode]]] = None  # Only for double elim
    finals: Optional[BracketNode] = None


# ==========================================
# RANKING MODELS
# ==========================================

class CurrentRankingResponse(BaseModel):
    player_id: str
    first_name: str
    last_name: str
    nickname: Optional[str] = None
    license_number: Optional[str] = None
    avatar_url: Optional[str] = None
    total_points: float
    current_rank: Optional[int] = None
    total_tournaments_played: int
    hall_of_fame: bool = False
    hot_streak_count: int = 0
    fargo_score: Optional[int] = None
    nationality: Optional[str] = None
    membership_status: Optional[str] = "active"  # For Leaderboard display (lifetime, active, etc.)
    win_percentage_matches: Optional[float] = None
    win_percentage_games: Optional[float] = None
    first_place_finishes: Optional[int] = 0
    second_place_finishes: Optional[int] = 0
    third_place_finishes: Optional[int] = 0


class HotStreakPlayerResponse(CurrentRankingResponse):
    """Hot streak player with upward-trend placement data."""
    last_placements: List[int] = Field(default_factory=list, description="Recent tournament placements (most recent first)")
    resilience_1yr: Optional[float] = Field(None, description="Resilience 0-100 from last 365 days of real events (≥2 events)")
    resilience_career: Optional[float] = Field(None, description="Resilience 0-100 from full career in association (≥2 events)")
    fargo_history: List[Dict[str, Any]] = Field(default_factory=list, description="Recent Fargo ratings by tournament (oldest to newest)")
    fargo_trend_score: float = 0.0
    trend_score: float = 0.0
    recent_tournaments_count: int = 0


class TournamentPerformancePlayerResponse(BaseModel):
    player_name: str
    placement: Optional[int] = None
    finish_percentile: Optional[float] = None
    matches_played: int = 0
    matches_won: int = 0
    matches_lost: int = 0
    win_rate: Optional[float] = None
    points_for: int = 0
    points_against: int = 0
    score_diff: int = 0


class TournamentPerformanceResponse(BaseModel):
    tournament_id: str
    tournament_name: str
    association: Optional[str] = None
    tournament_date: Optional[date] = None
    field_size: int = 0
    players: List[TournamentPerformancePlayerResponse] = Field(default_factory=list)


class TournamentTabCoverageResponse(BaseModel):
    tournament_id: str
    tournament_name: Optional[str] = None
    latest_archive_file: Optional[str] = None
    captured_at: Optional[str] = None
    archive_dir: Optional[str] = None
    has_overview: bool = False
    has_bracket: bool = False
    has_live_scores: bool = False
    has_matches: bool = False
    has_schedule: bool = False
    has_players: bool = False
    has_stats: bool = False
    has_performance: bool = False
    players_count: int = 0
    bracket_matches_count: int = 0
    matches_count: int = 0
    # Populated when include_payload=true (archived JSON from tournament software harvest)
    tab_overview: Optional[Dict[str, Any]] = None
    tab_players: Optional[List[Dict[str, Any]]] = None
    tab_brackets: Optional[List[Dict[str, Any]]] = None
    tab_matches: Optional[List[Dict[str, Any]]] = None
    # Explicit per-tab slices (External Pool GraphQL-derived; see externalpool_tournament_harvester)
    tab_schedule: Optional[Any] = None
    tab_live_scores: Optional[Any] = None
    tab_stats: Optional[List[Dict[str, Any]]] = None
    tab_performance: Optional[Any] = None


class TournamentTabCoverageListItemResponse(TournamentTabCoverageResponse):
    association: Optional[str] = None
    tournament_date: Optional[date] = None


class TournamentTabCoverageListResponse(BaseModel):
    total: int = 0
    items: List[TournamentTabCoverageListItemResponse] = Field(default_factory=list)


class RankingHistoryResponse(BaseModel):
    player_id: str
    rank_position: int
    total_points: float
    tournaments_counted: int
    snapshot_date: date
    ranking_system: str = "LOCAL"


# ==========================================
# BULK OPERATIONS
# ==========================================

class BulkPlayerRegister(BaseModel):
    player_ids: List[str] = Field(..., min_length=1)


class GenerateBracketRequest(BaseModel):
    shuffle_seeds: bool = False  # Randomize placement if no seeds set
    race_to: int = Field(7, ge=1, description="Race to X games (default: 7)")
    bye_player_ids: Optional[List[str]] = Field(
        None,
        description="Optional list of player_ids to receive BYEs in round 1",
    )
    bye_seed_positions: Optional[List[int]] = Field(
        None,
        description="Optional list of seed positions to receive BYEs in round 1",
    )


class Stage2StartRequest(BaseModel):
    cutoff: int = Field(..., ge=2, le=256, description="Number of players advancing to stage 2")
    advancing_player_ids: Optional[List[str]] = Field(
        None,
        description="Optional ordered list of player_ids to advance",
    )
    seed_strategy: str = Field(
        "placement",
        description="Seeding strategy: placement | seed | manual",
    )
    race_to: int = Field(7, ge=1, description="Race to X games (default: 7)")
    bye_player_ids: Optional[List[str]] = Field(
        None,
        description="Optional list of player_ids to receive BYEs in stage 2 round 1",
    )
    bye_seed_positions: Optional[List[int]] = Field(
        None,
        description="Optional list of seed positions to receive BYEs in stage 2 round 1",
    )


# ==========================================
# IMPORT MODELS (WPBA/WPA)
# ==========================================

class ImportPlayerRequest(BaseModel):
    source: str = Field(..., description="'WPBA' or 'WPA'")
    player_name: str
    license_number: Optional[str] = None
    nationality: Optional[str] = None
    fargo_score: Optional[int] = None


class ImportTournamentRequest(BaseModel):
    source: str = Field(..., description="'WPBA' or 'WPA'")
    tournament_name: str
    tournament_date: date
    results: List[Dict] = Field(..., description="List of {player_name, placement, points}")
