"""
Database migration: Add video analysis rating adjustments table

This table tracks how AI video coaching analysis results influence ALFA ratings,
allowing the system to refine player ratings based on direct performance observation.
"""

-- Create video_analysis_rating_adjustments table
CREATE TABLE video_analysis_rating_adjustments (
    analysis_id VARCHAR(36) PRIMARY KEY,  -- Foreign key to ai_coach_analyses.id

    -- Player and association
    player_name VARCHAR(100) NOT NULL,
    association VARCHAR(20) NOT NULL,  -- 'WPBA', 'WPA_Women', 'WPA_Men'

    -- Rating changes
    old_rating FLOAT NOT NULL,
    new_rating FLOAT NOT NULL,
    adjustment FLOAT NOT NULL,  -- How much rating changed (+/-)

    -- Confidence and quality metrics
    confidence FLOAT NOT NULL,  -- 0.0-1.0, based on video quality/analysis depth
    video_score FLOAT NULL,  -- Overall video analysis score
    frame_count INTEGER NULL,  -- Frames analyzed

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT NULL,

    -- Indexes for performance
    INDEX idx_video_rating_player_assoc (player_name, association),
    INDEX idx_video_rating_created (created_at),
    INDEX idx_video_rating_analysis (analysis_id)
);

-- Add comment to table
COMMENT ON TABLE video_analysis_rating_adjustments IS 'Tracks how AI video coaching analysis results influence ALFA player ratings';