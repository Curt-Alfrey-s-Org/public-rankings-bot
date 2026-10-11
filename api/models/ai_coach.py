"""
AI Coach Database Models
SQLAlchemy ORM models for pool coaching analytics
"""

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, 
    ForeignKey, JSON, Text, Date, Index, UniqueConstraint,
    create_engine, func
)
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime, timedelta, timezone
import uuid

Base = declarative_base()  # sqlalchemy.orm.declarative_base (SQLAlchemy 2.0)


class AICoachAnalysis(Base):
    """
    Stores analysis results from Grok for each coaching session
    """
    __tablename__ = "ai_coach_analyses"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # User & ownership
    user_id = Column(String(36), nullable=False, index=True)  # Username as ID
    bot_type = Column(String(20), nullable=False)  # 'rankings', 'trading', 'contracts', 'credit'
    
    # Video source & metadata
    video_source = Column(String(20), nullable=False)  # 'youtube', 'upload'
    video_url = Column(String(500), nullable=True)
    video_title = Column(String(255), nullable=True)
    
    # Status tracking
    status = Column(String(20), nullable=False, index=True)  # pending, processing, completed, failed
    error_message = Column(Text, nullable=True)
    
    # Frame storage
    frame_count = Column(Integer, nullable=False)
    frame_size_mb = Column(Float, nullable=False)
    frame_storage_path = Column(String(255), nullable=False)  # Oracle filesystem path
    
    # Grok API usage tracking
    grok_tokens_input = Column(Integer, nullable=False, default=0)
    grok_tokens_output = Column(Integer, nullable=False, default=0)
    grok_cost_usd = Column(Float, nullable=False, default=0)  # Actual cost from API
    
    # Analysis results
    analysis_json = Column(JSON, nullable=True)  # Full structured response from Grok
    summary_text = Column(Text, nullable=True)  # Human-readable summary
    
    # Scoring
    stroke_mechanics_score = Column(Float, nullable=True)
    strategy_score = Column(Float, nullable=True)
    mental_game_score = Column(Float, nullable=True)
    overall_score = Column(Float, nullable=True)  # Average of above 3
    
    # Timing
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    started_processing_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)  # Auto-delete frames after this date
    
    # Additional metadata
    player_name = Column(String(255), nullable=True)
    opponent_name = Column(String(255), nullable=True)
    game_format = Column(String(50), nullable=True)  # '8-ball', '9-ball', '10-ball', etc

    # Progression review: compare this analysis with a previous one
    progression_from_id = Column(String(36), nullable=True, index=True)  # Previous analysis_id
    
    # Indices for fast queries
    __table_args__ = (
        Index('idx_user_created', 'user_id', 'created_at'),
        Index('idx_status_created', 'status', 'created_at'),
        Index('idx_bot_type', 'bot_type'),
        Index('idx_ai_coach_analyses_expires_at', 'expires_at'),  # For cleanup queries
    )
    
    def __repr__(self):
        return f"<AICoachAnalysis {self.id[:8]}... user={self.user_id[:8]}... status={self.status}>"


class PromoCode(Base):
    """
    Promo/coupon codes for influencer marketing program
    Used for giving free trials, discounts, and tracking referrals
    """
    __tablename__ = "promo_codes"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Code details
    code = Column(String(50), unique=True, nullable=False, index=True)  # 'TEICHERT26', 'REYES99'
    description = Column(String(255), nullable=True)
    
    # Influencer ownership
    influencer_id = Column(String(36), nullable=False, index=True)  # Username as ID
    influencer_tier = Column(String(20), nullable=False)  # 'HOF' (Hall of Fame) or 'TOP_33'
    
    # What the code provides
    trial_tier = Column(String(20), nullable=False)  # Tier given for free ('POOL_SHARK', 'PRO', etc)
    trial_duration_days = Column(Integer, nullable=False, default=14)  # How long the trial lasts
    discount_percent = Column(Integer, nullable=True, default=0)  # Immediate discount 0-100%
    bonus_analyses = Column(Integer, nullable=False, default=0)  # Extra analyses added on redeem
    
    # After trial ends
    upgrade_tier = Column(String(20), nullable=True)  # Optional: auto-downgrade to this tier
    upgrade_discount_percent = Column(Integer, nullable=True, default=0)  # 0-50% discount if upgrade
    upgrade_duration_months = Column(Integer, nullable=True)  # How long discount lasts
    
    # Usage tracking
    max_uses = Column(Integer, nullable=True)  # None = unlimited
    current_uses = Column(Integer, nullable=False, default=0)  # used_count
    
    # Lifecycle
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=True)  # Code expires on this date
    
    # Metadata
    notes = Column(Text, nullable=True)  # Internal notes
    
    __table_args__ = (
        Index('idx_code_active', 'code', 'is_active'),
        Index('idx_influencer_active', 'influencer_id', 'is_active'),
    )
    
    def is_valid(self) -> bool:
        """Check if code is still valid for use"""
        if not self.is_active:
            return False
        if self.max_uses and self.current_uses >= self.max_uses:
            return False
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return False
        return True
    
    def __repr__(self):
        return f"<PromoCode {self.code} by {self.influencer_id[:8]}... uses={self.current_uses}>"


class Referral(Base):
    """
    Tracks referrals from promo codes
    Used for influencer bonus program
    """
    __tablename__ = "referrals"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Code and referred user
    promo_code_id = Column(String(36), ForeignKey('promo_codes.id'), nullable=False, index=True)
    referred_user_id = Column(String(36), nullable=False, index=True)  # Username as ID
    referrer_id = Column(String(36), nullable=True, index=True)  # Influencer who owns the code
    
    # Tracking
    referral_date = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)  # created_at
    conversion_date = Column(DateTime, nullable=True)  # When they started paying subscription
    is_active = Column(Boolean, nullable=False, default=True)  # Still a paying customer
    reward_status = Column(String(20), nullable=False, default='pending')  # pending, awarded, expired
    
    # Attribution
    referral_value_usd = Column(Float, nullable=True)  # Paid subscription value
    
    # Bonus tracking
    bonus_awarded = Column(Float, nullable=False, default=0)  # Amount awarded to influencer
    bonus_awarded_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index('idx_promo_code_conversion', 'promo_code_id', 'conversion_date'),
        Index('idx_referred_user', 'referred_user_id'),
    )
    
    def __repr__(self):
        return f"<Referral {self.id[:8]}... code={self.promo_code_id[:8]}... user={self.referred_user_id[:8]}...>"


class AICoachUsage(Base):
    """
    Tracks usage against tier limits
    Updated whenever user runs an analysis
    """
    __tablename__ = "ai_coach_usage"
    
    user_id = Column(String(36), primary_key=True, index=True)  # Username as ID (no foreign key; accounts may not exist in users table)
    
    # Current tier and limits
    tier = Column(String(20), nullable=False)  # 'FREEBIE', 'ROOKIE', 'WEEKEND_WARRIOR', 'POOL_SHARK', 'PRO'
    
    # Monthly usage
    analyses_this_month = Column(Integer, nullable=False, default=0)
    analyses_limit = Column(Integer, nullable=False)  # Tier-dependent limit
    month_reset_date = Column(Date, nullable=False, default=lambda: datetime.now(timezone.utc).date())  # When month resets
    
    # Lifetime usage (FREEBIE tier only)
    lifetime_analyses = Column(Integer, nullable=False, default=0)
    lifetime_limit = Column(Integer, nullable=True, default=3)  # For FREEBIE tier
    
    # Max video duration allowed (seconds)
    max_video_duration_seconds = Column(Integer, nullable=False, default=30)
    
    # Last usage
    last_analysis_at = Column(DateTime, nullable=True)
    
    # Trial info (if applicable)
    trial_tier = Column(String(20), nullable=True)  # What tier they got free
    trial_expires_at = Column(DateTime, nullable=True)  # When free trial ends
    
    # Discount info (if applicable)
    discount_percent = Column(Integer, nullable=False, default=0)  # 0-50
    discount_expires_at = Column(DateTime, nullable=True)  # When discount ends

    # Notification preferences
    notify_rank_changes = Column(Boolean, nullable=True, default=True)  # Email when subscribed player's rank changes

    # Tracking
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index('idx_tier', 'tier'),
        Index('idx_trial_expires', 'trial_expires_at'),
        Index('idx_discount_expires', 'discount_expires_at'),
    )
    
    def is_within_limits(self) -> bool:
        """Check if user can run another analysis"""
        if self.tier == 'FREEBIE':
            return self.lifetime_analyses < (self.lifetime_limit or 3)
        else:
            return self.analyses_this_month < self.analyses_limit
    
    def uses_remaining(self) -> int:
        """Get number of analyses remaining this period"""
        if self.tier == 'FREEBIE':
            return max(0, (self.lifetime_limit or 3) - self.lifetime_analyses)
        else:
            return max(0, self.analyses_limit - self.analyses_this_month)
    
    def reset_if_new_month(self) -> bool:
        """Reset monthly counter if we're in a new month"""
        today = datetime.now(timezone.utc).date()
        if today.replace(day=1) > self.month_reset_date.replace(day=1):
            self.analyses_this_month = 0
            self.month_reset_date = today
            return True
        return False
    
    def __repr__(self):
        return f"<AICoachUsage user={self.user_id[:8]}... tier={self.tier} uses={self.analyses_this_month}/{self.analyses_limit}>"


class VideoAnalysisRatingAdjustment(Base):
    """
    Tracks how video analysis results influence ALFA ratings.

    This table records rating adjustments made based on AI video coaching
    analysis, allowing the system to learn from direct performance observation.
    """
    __tablename__ = "video_analysis_rating_adjustments"

    analysis_id = Column(String(36), primary_key=True)  # Foreign key to ai_coach_analyses.id

    # Player and association
    player_name = Column(String(100), nullable=False, index=True)
    association = Column(String(20), nullable=False, index=True)  # 'WPBA', 'WPA_Women', 'WPA_Men'

    # Rating changes
    old_rating = Column(Float, nullable=False)
    new_rating = Column(Float, nullable=False)
    adjustment = Column(Float, nullable=False)  # How much rating changed (+/-)

    # Confidence and quality metrics
    confidence = Column(Float, nullable=False)  # 0.0-1.0, based on video quality/analysis depth
    video_score = Column(Float, nullable=True)  # Overall video analysis score
    frame_count = Column(Integer, nullable=True)  # Frames analyzed

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)

    # Indexes for performance
    __table_args__ = (
        Index('idx_video_rating_player_assoc', 'player_name', 'association'),
        Index('idx_video_rating_created', 'created_at'),
    )

    def __repr__(self):
        return f"<VideoAnalysisRatingAdjustment(analysis_id='{self.analysis_id}', player='{self.player_name}', adjustment={self.adjustment:.1f})>"


# Tier configuration (for reference - used by application logic)
TIER_CONFIG = {
    "FREEBIE": {
        "name": "Freebie",
        "monthly_limit": None,  # Uses lifetime_limit instead
        "lifetime_limit": 3,
        "max_video_duration": 30,  # seconds
        "price_monthly": 0,
        "features": ["Basic analysis", "Limited videos"]
    },
    "ROOKIE": {
        "name": "Rookie",
        "monthly_limit": 25,
        "lifetime_limit": None,
        "max_video_duration": 120,  # 2 minutes
        "price_monthly": 5,
        "features": ["25 analyses/month", "2-min videos", "Email support"]
    },
    "WEEKEND_WARRIOR": {
        "name": "Weekend Warrior",
        "monthly_limit": 100,
        "lifetime_limit": None,
        "max_video_duration": 1800,  # 30 minutes (free AI coach video eval)
        "price_monthly": 8,
        "features": ["100 analyses/month", "30-min free video eval", "Priority support"]
    },
    "POOL_SHARK": {
        "name": "Pool Shark",
        "monthly_limit": 300,
        "lifetime_limit": None,
        "max_video_duration": 3600,  # 1 hour (free AI coach video eval)
        "price_monthly": 10,
        "features": ["300 analyses/month", "1-hr free video eval", "Referral bonuses"]
    },
    "PRO": {
        "name": "Pro",
        "monthly_limit": None,  # Unlimited
        "lifetime_limit": None,
        "max_video_duration": 3600,  # 1 hour
        "price_monthly": 20,
        "features": ["Unlimited analyses", "1-hour videos", "VIP support", "Custom drills"]
    }
}


if __name__ == "__main__":
    print("AI Coach Database Models")
    print("------------------------")
    print("AICoachAnalysis - stores coaching analyses")
    print("PromoCode - influencer coupon codes")
    print("Referral - referral tracking")
    print("AICoachUsage - tier usage tracking")
