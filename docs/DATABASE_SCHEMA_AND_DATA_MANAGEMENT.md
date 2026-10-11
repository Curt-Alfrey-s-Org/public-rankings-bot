# Database Schema and Data Management

This document provides a comprehensive overview of the Rankings Bot database schema, column definitions, and data change management policies.

## Database Overview

The Rankings Bot uses PostgreSQL with the following key design principles:

- **Flexible Schema**: Core fields in dedicated columns, extended data in JSONB `source_data`
- **Data Preservation**: Immutable historical records with archiving
- **Audit Trail**: Complete change tracking for critical operations
- **Performance**: Optimized queries with strategic indexing

## Core Tables and Columns

### 1. Players Table

**Purpose**: Stores player profile information and calculated ratings.

| Column | Type | Description | Constraints |
|--------|------|-------------|-------------|
| `id` | SERIAL | Primary key | PRIMARY KEY |
| `name` | VARCHAR(255) | Player full name | NOT NULL, UNIQUE |
| `nationality` | VARCHAR(255) | Player nationality | Optional |
| `fargo_rating` | INTEGER | Official Fargo rating | Optional |
| `est_rating` | DOUBLE PRECISION | Estimated rating (predictive) | Optional |
| `est_rating_confidence` | DOUBLE PRECISION | Confidence in est. rating (0.0-1.0) | Default 0.5 |
| `est_rating_robustness` | INTEGER | Sample size robustness | Default 0 |
| `est_rating_last_updated` | TIMESTAMP | Last rating calculation | Default CURRENT_TIMESTAMP |
| `est_rating_formula_version` | VARCHAR(32) | Rating formula version | Default 'alfa_v2' |
| `created_at` | TIMESTAMP | Record creation time | Default CURRENT_TIMESTAMP |
| `updated_at` | TIMESTAMP | Last record update | Default CURRENT_TIMESTAMP |

### 2. Rankings Table

**Purpose**: Daily snapshots of ranking lists from various sources.

| Column | Type | Description | Constraints |
|--------|------|-------------|-------------|
| `id` | SERIAL | Primary key | PRIMARY KEY |
| `player_name` | VARCHAR(255) | Player name in ranking | NOT NULL |
| `ranking_system` | VARCHAR(32) | Ranking type identifier | NOT NULL |
| `rank` | INTEGER | Position in ranking | NOT NULL |
| `points` | DOUBLE PRECISION | Ranking points | NOT NULL |
| `country` | VARCHAR(255) | Player country | Optional |
| `license_number` | VARCHAR(255) | Player license | Optional |
| `fargo_rating` | DOUBLE PRECISION | Fargo rating at scrape time | Optional |
| `fargo_last_updated` | TIMESTAMP | Fargo rating update time | Optional |
| `alfa_rating` | DOUBLE PRECISION | AI-calculated rating | Optional |
| `stops_played` | INTEGER | Number of stops played | Optional |
| `snapshot_date` | DATE | Date of ranking snapshot | NOT NULL |
| `position` | INTEGER | Unique position (1,2,3...) | NOT NULL |
| `source_data` | JSONB | Full source record data | Optional |
| `fargo_robustness` | DOUBLE PRECISION | Fargo rating stability | Optional |
| `created_at` | TIMESTAMP | Record creation time | Default CURRENT_TIMESTAMP |
| `updated_at` | TIMESTAMP | Last record update | Default CURRENT_TIMESTAMP |

**Unique Constraint**: `(player_name, ranking_system, snapshot_date)`
**Check Constraint**: `ranking_system IN ('WPBA_Women', 'WPA_Men', 'WPA_Women', 'WPBA', 'WPA', 'WPA_Heyball', 'WPA_Heyball_Men', 'WPA_Heyball_Women', 'WPA_Artistic')`

### 3. Rankings Archive Table

**Purpose**: Immutable historical backup of all ranking changes.

| Column | Type | Description | Constraints |
|--------|------|-------------|-------------|
| `id` | SERIAL | Primary key | PRIMARY KEY |
| `original_id` | INTEGER | Original rankings.id | NOT NULL |
| `player_name` | VARCHAR(255) | Player name | NOT NULL |
| `ranking_system` | VARCHAR(32) | Ranking system | NOT NULL |
| `rank` | INTEGER | Archived rank | NOT NULL |
| `points` | DOUBLE PRECISION | Archived points | NOT NULL |
| `country` | VARCHAR(255) | Archived country | Optional |
| `license_number` | VARCHAR(255) | Archived license | Optional |
| `fargo_rating` | DOUBLE PRECISION | Archived Fargo rating | Optional |
| `archived_at` | TIMESTAMP | Archive timestamp | Default CURRENT_TIMESTAMP |
| `archive_reason` | VARCHAR(64) | Reason for archiving | Default 'update' |
| `snapshot_date` | DATE | Original snapshot date | NOT NULL |

**Check Constraint**: `archive_reason IN ('update', 'delete', 'correction', 'pre_update')`

### 4. Tournament History Table

**Purpose**: Historical tournament metadata and results.

| Column | Type | Description | Constraints |
|--------|------|-------------|-------------|
| `id` | SERIAL | Primary key | PRIMARY KEY |
| `tournament_id` | VARCHAR(255) | Unique tournament identifier | NOT NULL, UNIQUE |
| `name` | VARCHAR(255) | Tournament name | NOT NULL |
| `date` | DATE | Tournament date | Optional |
| `location` | VARCHAR(255) | Tournament location | Optional |
| `year` | INTEGER | Tournament year | Optional |
| `association` | VARCHAR(32) | Governing association | Optional |
| `championship` | VARCHAR(255) | Championship title | Optional |
| `champion` | VARCHAR(255) | Winner name | Optional |
| `runner_up` | VARCHAR(255) | Second place | Optional |
| `final_score` | VARCHAR(64) | Final match score | Optional |
| `status` | VARCHAR(32) | Tournament status | Default 'completed' |
| `prize_pool` | VARCHAR(128) | Prize pool amount | Optional |
| `source_url` | TEXT | Source webpage URL | Optional |
| `bracket_url` | TEXT | Bracket/results URL | Optional |
| `created_at` | TIMESTAMP | Record creation time | Default CURRENT_TIMESTAMP |
| `updated_at` | TIMESTAMP | Last record update | Default CURRENT_TIMESTAMP |

### 5. Tournament Results Table

**Purpose**: Individual player placements and points from tournaments.

| Column | Type | Description | Constraints |
|--------|------|-------------|-------------|
| `id` | SERIAL | Primary key | PRIMARY KEY |
| `tournament_id` | VARCHAR(255) | Foreign key to tournament_history | NOT NULL, REFERENCES tournament_history(tournament_id) ON DELETE CASCADE |
| `player_name` | VARCHAR(255) | Player name | NOT NULL |
| `placement` | INTEGER | Finishing position | Optional |
| `points` | DOUBLE PRECISION | Points earned | Default 0.0 |
| `fargo_rating_at_scrape` | DOUBLE PRECISION | Fargo rating when scraped | Optional |
| `notes` | TEXT | Additional notes | Optional |
| `created_at` | TIMESTAMP | Record creation time | Default CURRENT_TIMESTAMP |

**Unique Constraint**: `(tournament_id, player_name)`

### 6. Matches Table

**Purpose**: Individual matches within tournaments.

| Column | Type | Description | Constraints |
|--------|------|-------------|-------------|
| `id` | SERIAL | Primary key | PRIMARY KEY |
| `match_id` | VARCHAR(64) | Unique match identifier | NOT NULL, UNIQUE |
| `tournament_id` | VARCHAR(255) | Tournament identifier | NOT NULL |
| `operator_name` | VARCHAR(255) | First player | NOT NULL |
| `player2_name` | VARCHAR(255) | Second player | NOT NULL |
| `operator_score` | INTEGER | Player 1 final score | NOT NULL |
| `player2_score` | INTEGER | Player 2 final score | NOT NULL |
| `winner_name` | VARCHAR(255) | Match winner | Optional |
| `status` | VARCHAR(32) | Match status | Default 'completed' |
| `round_num` | VARCHAR(128) | Tournament round | Optional |
| `match_num` | INTEGER | Match number in round | Optional |
| `scheduled_time` | TIMESTAMP | Scheduled start time | Optional |
| `start_time` | TIMESTAMP | Actual start time | Optional |
| `end_time` | TIMESTAMP | Match end time | Optional |
| `table_number` | INTEGER | Table assignment | Optional |
| `scorekeeper_id` | VARCHAR(255) | Assigned scorekeeper | Optional |
| `notes` | TEXT | Match notes | Optional |
| `created_at` | TIMESTAMP | Record creation time | Default CURRENT_TIMESTAMP |
| `updated_at` | TIMESTAMP | Last record update | Default CURRENT_TIMESTAMP |

### 7. Games Table

**Purpose**: Individual rack/game results within matches.

| Column | Type | Description | Constraints |
|--------|------|-------------|-------------|
| `id` | SERIAL | Primary key | PRIMARY KEY |
| `match_id` | VARCHAR(64) | Foreign key to matches | NOT NULL, REFERENCES matches(match_id) |
| `game_number` | INTEGER | Rack/game number (1,2,3...) | NOT NULL, >= 1 |
| `winner_id` | VARCHAR(255) | Winning player ID | Optional |
| `winner_name` | VARCHAR(255) | Winning player name | Optional |
| `breaking_player_id` | VARCHAR(255) | Player who broke | Optional |
| `innings` | INTEGER | Number of innings played | Optional, >= 0 |
| `run_out` | BOOLEAN | Winner ran out | Default FALSE |
| `break_and_run` | BOOLEAN | Winner broke and ran | Default FALSE |
| `notes` | TEXT | Game-specific notes | Optional |
| `completed_at` | TIMESTAMP | Game completion time | Default CURRENT_TIMESTAMP |

### 8. Est Rating Transitions Table

**Purpose**: Audit trail of all estimated rating changes.

| Column | Type | Description | Constraints |
|--------|------|-------------|-------------|
| `id` | SERIAL | Primary key | PRIMARY KEY |
| `player_id` | VARCHAR(255) | Player identifier | NOT NULL |
| `player_name` | VARCHAR(255) | Player name | NOT NULL |
| `match_id` | VARCHAR(64) | Associated match | NOT NULL, REFERENCES matches(match_id) |
| `game_id` | INTEGER | Associated game | NOT NULL, REFERENCES games(id) |
| `previous_est_rating` | DOUBLE PRECISION | Rating before change | Optional |
| `new_est_rating` | DOUBLE PRECISION | Rating after change | NOT NULL |
| `formula_version` | VARCHAR(32) | Calculation version | Default 'alfa_v2' |
| `confidence` | DOUBLE PRECISION | Rating confidence | Default 0.5 |
| `robustness` | INTEGER | Sample size robustness | Default 0 |
| `rating_change` | DOUBLE PRECISION | Change amount | Optional |
| `opponent_id` | VARCHAR(255) | Opponent identifier | Optional |
| `opponent_name` | VARCHAR(255) | Opponent name | Optional |
| `opponent_rating` | DOUBLE PRECISION | Opponent rating | Optional |
| `game_outcome` | VARCHAR(32) | Win/loss/draw | NOT NULL |
| `game_context` | JSONB | Additional game context | Optional |
| `tournament_id` | VARCHAR(32) | Tournament identifier | Optional |
| `created_at` | TIMESTAMP | Record creation time | Default CURRENT_TIMESTAMP |
| `updated_at` | TIMESTAMP | Last record update | Default CURRENT_TIMESTAMP |

## Data Change Management Policies

### Archiving Conditions

**Automatic Archiving Triggers:**
1. **Update Operations**: Before `UPDATE` or `DELETE` on `rankings` table
2. **Data Corrections**: When fixing incorrect data
3. **Pre-Update**: Before bulk data operations
4. **Manual Archive**: Administrative data cleanup

**Archive Reasons:**
- `'update'`: Before updating existing ranking data
- `'delete'`: Before deleting ranking records
- `'correction'`: When fixing data errors
- `'pre_update'`: Before bulk operations

### Data Preservation Rules

**Never Deleted Data:**
- Historical tournament results
- Player rating transitions
- Audit log entries
- Archived ranking snapshots

**Archival Strategy:**
1. **Before any change**: Copy affected records to archive table
2. **Include metadata**: Archive reason, timestamp, original ID
3. **Preserve relationships**: Maintain foreign key references where possible
4. **Enable recovery**: Support point-in-time data restoration

### Data Consistency Checks

**Ranking Integrity:**
- Unique `(player_name, ranking_system, snapshot_date)` constraint
- Position uniqueness within ranking snapshots
- Foreign key relationships maintained
- Check constraints on enumerated values

**Tournament Data Integrity:**
- Tournament results reference valid tournament_history
- Match results reference valid tournaments
- Game results reference valid matches
- Cascading deletes preserve referential integrity

### Performance Optimizations

**Indexing Strategy:**
```sql
-- Rankings table indexes
CREATE INDEX idx_rankings_date ON rankings(snapshot_date);
CREATE INDEX idx_rankings_player ON rankings(player_name);
CREATE INDEX idx_rankings_system ON rankings(ranking_system);

-- Archive table indexes
CREATE INDEX idx_rankings_archive_player ON rankings_archive(player_name);
CREATE INDEX idx_rankings_archive_date ON rankings_archive(snapshot_date DESC);
CREATE INDEX idx_rankings_archive_archived_at ON rankings_archive(archived_at DESC);
CREATE INDEX idx_rankings_archive_original_id ON rankings_archive(original_id);

-- Tournament indexes
CREATE INDEX idx_tournament_history_year ON tournament_history(year);
CREATE INDEX idx_tournament_history_date ON tournament_history(date);
CREATE INDEX idx_tournament_history_association ON tournament_history(association);
CREATE INDEX idx_tournament_results_tournament ON tournament_results(tournament_id);
CREATE INDEX idx_tournament_results_player ON tournament_results(player_name);
```

**Materialized Views:**
- `mv_latest_rankings`: Fast access to current rankings
- `mv_tournament_history_recent`: Recent tournament metadata

### Data Migration and Schema Changes

**Migration Process:**
1. **Alembic migrations** for schema changes
2. **Backward compatibility** maintained during transitions
3. **Data validation** before and after migrations
4. **Rollback procedures** documented

**Schema Evolution:**
- New columns added with `IF NOT EXISTS`
- Default values provided for existing records
- Check constraints added incrementally
- Indexes created with `IF NOT EXISTS`

### Backup and Recovery

**Backup Strategy:**
- **Daily automated backups** of PostgreSQL database
- **Point-in-time recovery** capability
- **Archive table preservation** in backups
- **Cross-region replication** for disaster recovery

**Recovery Procedures:**
1. **Data Loss**: Restore from archive tables
2. **Corruption**: Point-in-time recovery
3. **Accidental Deletion**: Restore from backups
4. **Schema Issues**: Rollback migration procedures

### Monitoring and Alerts

**Data Quality Metrics:**
- Ranking snapshot completeness
- Tournament data coverage
- Rating calculation accuracy
- Archive table growth rate

**Alert Conditions:**
- Failed data imports
- Missing ranking snapshots
- Archive table size thresholds
- Rating calculation errors

## API Data Flow

### Read Operations
1. **Pagination**: `get_rankings_paginated()` with limit/offset
2. **Snapshot Selection**: Prioritize detailed data over summary data
3. **Data Merging**: Combine first-class columns with `source_data`
4. **Rating Inclusion**: Join with players table for `est_rating` fields

### Write Operations
1. **Validation**: Input data validation
2. **Archiving**: Automatic archival before changes
3. **Transaction**: Atomic operations with rollback
4. **Audit**: Log all changes in audit tables

### Real-time Updates
1. **Live Rating Engine**: Triggers on game completion
2. **WebSocket Broadcasting**: Real-time rating updates
3. **Cache Invalidation**: Update materialized views
4. **Notification System**: Email alerts for significant changes

## Development Guidelines

### Schema Changes
- Use Alembic for all schema modifications
- Include rollback procedures
- Test migrations on staging environment
- Document impact on existing data

### Data Operations
- Always archive before destructive operations
- Use transactions for multi-table operations
- Implement proper error handling and rollback
- Log all data modifications

### Performance Considerations
- Monitor query execution plans
- Optimize indexes based on access patterns
- Use appropriate data types
- Consider partitioning for large tables

---

**Last Updated**: March 5, 2026
**Document Version**: 1.0