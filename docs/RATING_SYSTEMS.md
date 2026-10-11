# Rating Systems in Rankings Bot

This document explains the different rating systems used in the Rankings Bot and their purposes.

## Overview

The Rankings Bot uses multiple rating systems to track and predict player performance. Understanding the differences between these systems is crucial for interpreting rankings data correctly.

## Rating System Types

### 1. Fargo Rating
- **Source**: Official Fargo Rating Corporation
- **Purpose**: Established professional rating system for pool players
- **Update Frequency**: Monthly/quarterly through official Fargo updates
- **Display**: Shown as "Fargo Rating" in rankings tables
- **Data Source**: Official Fargo database/API

### 2. Est. Rating (Estimated Rating)
- **Source**: Calculated internally by Rankings Bot
- **Purpose**: Predictive estimate of what a player's Fargo rating *should* be based on current performance
- **Update Frequency**: Real-time, updated after every completed rack/game event
- **Display**: Shown as "Est. Rating" in rankings tables
- **Calculation**: Uses Elo-style algorithm based on tournament results and match outcomes
- **Use Case**: Helps identify players whose current Fargo rating may not reflect their true skill level
- **Validation**: Once Fargo releases official updates, Est. Rating accuracy can be measured
- **Access**: PRO subscription feature for players (admin/director/super-admin retain operational visibility)

### 3. Alfa Rating (AI Coach Rating)
- **Source**: Calculated internally by Rankings Bot using AI analysis
- **Purpose**: Advanced rating system using video shot performance analysis and AI coach insights
- **Update Frequency**: Real-time, updated after every game with detailed shot analysis
- **Display**: Shown as "Alfa Rating" in rankings tables (may be labeled "Est. Rating" in some interfaces)
- **Calculation**: Uses AI analysis of video footage, shot patterns, and performance metrics
- **Features**:
  - Analyzes individual shot quality and consistency
  - Considers shot selection and strategic decisions
  - Incorporates video-based performance metrics
  - Adapts to player style and improvement over time
- **Status**: In development - requires video capture infrastructure and AI analysis pipeline
- **Future Use**: Will provide the most accurate and detailed player assessments
- **Access**: PRO subscription feature for players (admin/director/super-admin retain operational visibility)

## Key Differences

| Aspect | Fargo Rating | Est. Rating | Alfa Rating |
|--------|-------------|-------------|-------------|
| **Data Source** | Official Fargo | Tournament Results | Video + AI Analysis |
| **Update Frequency** | Monthly | Per Tournament | Per Game |
| **Accuracy** | Official Standard | Predictive Estimate | Detailed Analysis |
| **Cost** | Paid Service | Free (calculated) | Requires AI/Video Infra |
| **Scope** | Professional Players | PRO Players + staff visibility | PRO Players + staff visibility |

## Technical Implementation

### Est. Rating Calculation
- Uses Elo-style rating system with configurable K-factor
- Considers tournament strength, opponent ratings, and match outcomes
- Includes confidence intervals and robustness metrics
- Stored in `players.est_rating` table columns

### Alfa Rating Calculation
- Requires video capture during matches
- Uses computer vision for shot analysis
- Incorporates AI models for performance evaluation
- Considers factors beyond win/loss (shot quality, consistency, strategy)
- Planned for future implementation

## Database Storage

### Players Table
```sql
ALTER TABLE players
ADD COLUMN IF NOT EXISTS est_rating DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS est_rating_confidence DOUBLE PRECISION DEFAULT 0.5,
ADD COLUMN IF NOT EXISTS est_rating_robustness INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS est_rating_last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
ADD COLUMN IF NOT EXISTS est_rating_formula_version VARCHAR(32) DEFAULT 'alfa_v2';
```

### Rankings Table
```sql
ALTER TABLE rankings
ADD COLUMN IF NOT EXISTS alfa_rating DOUBLE PRECISION;
```

### Est Rating Transitions (Audit)
```sql
CREATE TABLE IF NOT EXISTS est_rating_transitions (
    id SERIAL PRIMARY KEY,
    player_id VARCHAR(255) NOT NULL,
    player_name VARCHAR(255) NOT NULL,
    match_id VARCHAR(64) NOT NULL REFERENCES matches(match_id),
    game_id INTEGER NOT NULL REFERENCES games(id),
    -- Rating change tracking fields
);
```

## Future Development

### Alfa Rating Roadmap
1. **Phase 1**: Video capture infrastructure for tournaments
2. **Phase 2**: Basic computer vision shot detection
3. **Phase 3**: AI performance analysis models
4. **Phase 4**: Integration with live rating engine
5. **Phase 5**: Premium player opt-in program

### Integration Points
- Live rating engine will support both Est. Rating and Alfa Rating calculations
- Tournament director interface for enabling video capture
- Real-time rating updates during matches
- Historical rating trend analysis

## Display and User Interface

### Frontend Labels
- **Fargo Rating**: "Fargo Rating" (official)
- **Est. Rating**: "Est. Rating" (predictive)
- **Alfa Rating**: "Alfa Rating" or "AI Rating" (advanced)

### Column Ordering
In rankings tables, ratings appear in this order:
1. Fargo Rating (if available)
2. Fargo Robustness
3. **Est. Rating / Alfa Rating** (between robustness and points)
4. Points

## Validation and Accuracy

### Est. Rating Validation
- Compare predictions vs. actual Fargo rating updates
- Track prediction accuracy over time
- Adjust algorithm parameters based on performance
- Monthly validation reports

### Alfa Rating Validation
- Compare vs. human coach assessments
- Player improvement tracking
- Tournament outcome predictions
- Shot quality correlation studies

## API Endpoints

### Rating Data Retrieval
- `GET /api/tournaments/live-ratings/{player_id}` - Individual player ratings
- `GET /api/tournaments/live-ratings` - All current ratings
- `GET /api/tournaments/rating-transitions/{player_id}` - Rating history

### Rating Updates
- `POST /api/tournaments/games` - Triggers rating recalculation
- `PUT /api/games/{game_id}` - Updates game results and ratings

## Configuration

### Rating Engine Settings
Located in `api/services/live_rating_engine.py`:
- K-factor for rating changes
- Confidence calculation parameters
- Formula versions
- Update triggers

### Database Configuration
- Rating transition audit logging
- Archive conditions for old ratings
- Performance optimization settings

## Monitoring and Maintenance

### Health Checks
- Rating calculation performance
- Database query efficiency
- Real-time update latency
- Data consistency validation

### Backup and Recovery
- Rating history preservation
- Point-in-time rating restoration
- Audit trail integrity
- Disaster recovery procedures

---

**Last Updated**: March 5, 2026
**Document Version**: 1.0