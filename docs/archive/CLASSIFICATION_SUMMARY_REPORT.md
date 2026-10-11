# Tournament Match Classification Summary Report

**Generated:** 2026-02-16  
**Source Data:** `data/alfa_matches.csv`  
**Classified Data:** `data/alfa_matches_classified.csv`  
**Total Matches Analyzed:** 12,000

---

## Executive Summary

Tournament match data has been successfully classified by format, table size, and location. The analysis reveals a **homogeneous dataset** with all matches belonging to a single context group, which provides **excellent coverage** for model training in that specific context.

### Key Findings:
- ✓ **Single dominant format:** All 12,000 matches are 9-ball format
- ✓ **Consistent table size:** All matches played on 9ft tables  
- ⚠ **Location data gap:** Location information is missing from the dataset (all entries marked as "Unknown")
- ✓ **Excellent training data:** 12,000 matches in primary context far exceeds the 100-match threshold for statistical significance

---

## 1. Breakdown by Format

| Format | Match Count | Percentage | Status |
|--------|------------|-----------|--------|
| 9-ball | 12,000 | 100.00% | ✓ Primary Format |
| **Total** | **12,000** | **100.00%** | |

**Analysis:**  
The dataset is entirely composed of 9-ball tournament matches. This is the standard pool format for competitive play with 9 numbered balls and 1 cue ball.

---

## 2. Breakdown by Table Size

| Table Size | Match Count | Percentage | Status |
|-----------|-----------|-----------|--------|
| 9ft | 12,000 | 100.00% | ✓ All Matches |
| **Total** | **12,000** | **100.00%** | |

**Analysis:**  
All matches were played on 9-foot pool tables, the standard professional tournament size. There is no variation in table dimensions, which is consistent with formal ALFA tournament standards.

---

## 3. Breakdown by Location/Venue

| Location | Match Count | Percentage | Status |
|----------|-----------|-----------|--------|
| Unknown | 12,000 | 100.00% | ⚠ Data Gap |
| **Total** | **12,000** | **100.00%** | |

**Issue Identified:**  
The `location_id` field in the source data is completely empty. All 12,000 matches are classified as occurring at "Unknown" locations. This represents a **data quality gap** that limits venue-specific analysis.

**Recommendation:**  
- Investigate source data to populate location/venue information
- Consider cross-referencing with tournament metadata or event records
- May indicate location data exists in separate tables or needs data cleaning

---

## 4. Context Combinations (Format + Table Size + Location)

| Context Combination | Match Count | Percentage | Model Training Status |
|-------------------|-----------|-----------|----------------------|
| tournament_9ball_9ft_unknown | 12,000 | 100.00% | ✓ **SUFFICIENT** |
| **Total Unique Contexts** | **1** | — | |

**Analysis:**  
All matches belong to a single context group combining:
- Format: **9-ball**
- Table Size: **9ft**
- Location: **Unknown** (data not available)

This unified context provides **exceptional data volume** (12,000 matches) for developing 9-ball/9ft specific models.

---

## 5. Format + Table Size Combinations

| Format + Table Size | Match Count | Percentage | Training Data | Status |
|-------------------|-----------|-----------|---|--------|
| 9ball_9ft | 12,000 | 100.00% | Excellent | ✓ **SUFFICIENT** |
| **Total** | **12,000** | **100.00%** | | |

**Analysis:**  
The format-table combination is completely uniform across the dataset. This indicates:
- **Pros:** Consistent evaluation context for 9-ball on standard tables
- **Cons:** No diversity in formats or table sizes for comparative analysis
- **Impact:** Models trained on this data will be highly optimized for 9-ball/9ft scenarios

---

## 6. Data Availability Assessment for Model Training

### Training Data Sufficiency (≥100 matches threshold)

| Category | Count |
|----------|-------|
| Context groups with **SUFFICIENT** data (≥100 matches) | 1 |
| Context groups with **INSUFFICIENT** data (<100 matches) | 0 |
| Total matches in sufficient groups | 12,000 |
| Total matches in insufficient groups | 0 |

### Sufficient Contexts (Ready for Training):

1. **tournament_9ball_9ft_unknown**
   - Match Count: **12,000**
   - Percentage of Total: **100.00%**
   - Assessment: ✓ **EXCELLENT** - Far exceeds minimum threshold
   - Model Recommendations:
     - ✓ Suitable for ELO/rating model development
     - ✓ Sufficient for win probability prediction models
     - ✓ Adequate for strength-of-schedule analysis
     - ✓ Can support advanced ML models with cross-validation

### Data Quality Confidence:
- **Sample Size:** 12,000 matches provides strong statistical confidence
- **Minimum Significance Level:** Exceeded by 120x (12,000 ÷ 100)
- **Recommended Confidence Interval:** 95% (±1% margin of error with this sample size)
- **Statistical Power:** Very High (can detect small effect sizes)

---

## 7. Distribution Summary Table

```
table_size    9ft      All
format                  
9ball       12,000   12,000
All         12,000   12,000
```

**Interpretation:**
- Single row (one format) and single column (one table size) indicates homogeneous data
- All data points to same intersection: 9-ball on 9ft tables
- No distribution variation to analyze

---

## 8. Detailed Statistics by Format

### 9-ball Format
- **Total Matches:** 12,000
- **Table Size Distribution:** 9ft: 12,000 (100%)
- **Unique Locations:** 1 (Unknown)
- **Training Readiness:** ✓ Full dataset ready
- **Modeling Potential:** High (large, consistent sample)

---

## Observations & Recommendations

### Data Strengths ✓
1. **Large Sample Size (12,000):** Statistically robust dataset for model training
2. **Format Consistency:** All 9-ball matches enable focused model specialization
3. **Table Standardization:** All 9ft ensures apples-to-apples comparison
4. **No Sparse Contexts:** All data in single context eliminates fragmentation

### Data Gaps ⚠
1. **Missing Location Data:** No venue classification limits geographic/venue-level insights
2. **Format Homogeneity:** No 8-ball, 10-ball, or other formats for comparative analysis
3. **Table Size Lack:** Only 9ft tables; no 7ft or 8ft variations for multi-table models
4. **Single Context:** Cannot analyze cross-context patterns or transfer learning

### Recommendations for Enhancement 🔧

#### Immediate (High Priority):
1. **Populate Location Field:** Extract venue/location data from tournament records
   - Check tournament_id field for metadata
   - Cross-reference with venue master tables if available
   - Add location classification to subsequent imports

2. **Data Quality Check:** Verify if location data exists in:
   - Source database (may not be exported)
   - Tournament metadata files
   - Event records or tournament brackets

#### Medium Priority:
3. **Expand Format Coverage:** Identify tournaments with 8-ball and 10-ball matches
   - Assess availability of different format tournaments
   - Include in future data imports
   - Would enable cross-format modeling

4. **Table Size Variation:** Collect matches from 7ft and 8ft tables
   - Determine if tournaments use different table sizes
   - Include in expanded dataset
   - Would support table-size-adjusted rating models

#### Long-term (Enhancement):
5. **Temporal Analysis:** Analyze match distribution over time
6. **Player Pool Characteristics:** Segment by skill level or player region
7. **Competitive Context:** Classify by tournament tier or stakes
8. **Equipment Tracking:** Utilize equipment field (currently empty) for cue/ball standardization

---

## Model Training Readiness Summary

### Primary Context: tournament_9ball_9ft_unknown

| Aspect | Assessment | Recommendation |
|--------|-----------|---|
| **Data Volume** | ✓ Excellent (12,000 matches) | Ready for immediate use |
| **Statistical Significance** | ✓ Very High | Can detect effects <1% with high confidence |
| **Format Consistency** | ✓ Perfect (100% 9-ball) | Specialized models appropriate |
| **Table Consistency** | ✓ Perfect (100% 9ft) | No normalization needed |
| **Location Diversity** | ⚠ None (all Unknown) | Venue analysis not possible yet |
| **Cross-validation Potential** | ✓ Good (large n=12,000) | Can do 5-10 fold CV |
| **Generalization Limits** | ⚠ High (single context only) | Results specific to 9-ball/9ft |

### Recommended Models for Development:
1. ✓ **Fargo Rating System:** Excellent candidate (consistent rules/format)
2. ✓ **Win Probability Predictor:** Strong sample for ML training
3. ✓ **Strength-of-Schedule Analysis:** Can reliably compute with 12,000 matches
4. ✓ **Performance Consistency Metrics:** Large sample enables robust statistics
5. ⚠ **Multi-format Models:** Not recommended (insufficient format diversity)
6. ⚠ **Venue-specific Models:** Not feasible (missing location data)

---

## Conclusion

The tournament match dataset contains **12,000 9-ball matches on 9-foot tables**, providing an **excellent foundation for 9-ball-specific rating and predictive models**. The large, consistent sample size far exceeds minimum training requirements and enables high-confidence statistical analysis.

The primary limitation is the absence of location/venue data and lack of format/table size diversity. To unlock additional modeling possibilities (cross-format analysis, venue effects, etc.), future data collection should prioritize populating location information and including matches played in different formats and on different table sizes.

**Overall Assessment:** ✓ **READY FOR MODEL TRAINING** in the primary context (9-ball, 9ft, unknown venue).

---

**Report Generated:** February 16, 2026  
**Data Preparation Script:** `scripts/alfa_rating_data_prep.py`  
**Classification Method:** Context-based grouping (format + table_size + location)
