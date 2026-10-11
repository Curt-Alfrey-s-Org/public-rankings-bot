# Scraper Data Archival Standards

## Overview

All scrapers in this project MUST follow standardized archival practices to ensure data is organized, searchable, and maintainable. This document defines requirements and best practices.

## Standard Directory Structure

```
data/
├── {scraper_name}_archive/
│   ├── README.md                              # Archive documentation
│   ├── {scraper}_data_YYYYMMDD_HHMMSS.json   # Timestamped data archives
│   ├── {scraper}_summary_YYYYMMDD_HHMMSS.json # Summary files
│   └── reference_data.json                    # Static reference info (optional)
```

### Example Archives

```
data/
├── wpa_archive/
│   ├── README.md
│   ├── wpa_women_rankings_20260219_121332.json
│   ├── wpa_summary_20260219_121332.json
│   └── organization_reference.json
├── wpba_archive/
│   ├── README.md
│   ├── wpba_rankings_20260219_143022.json
│   └── wpba_summary_20260219_143022.json
├── tournament_archive/
│   ├── README.md
│   ├── tournament_history_20260219_150045.json
│   └── tournament_summary_20260219_150045.json
```

## File Naming Convention

### Required Format

**Pattern:** `{scraper}_{type}_YYYYMMDD_HHMMSS.json`

**Components:**
- `{scraper}`: Lowercase scraper name (wpba, wpa, tournament, etc.)
- `{type}`: Data type (data, summary, rankings, history, etc.)
- `YYYYMMDD`: Date (Year/Month/Day)
- `HHMMSS`: Time (Hour/Minute/Second in 24-hour format)

**Examples:**
- ✅ `wpa_women_rankings_20260219_121332.json`
- ✅ `wpba_rankings_20260219_143022.json`
- ✅ `tournament_history_20260218_091500.json`
- ❌ `wpa_data.json` (no timestamp)
- ❌ `rankings_2026-02-19.json` (wrong format)
- ❌ `WPA_Data_20260219.json` (uppercase, no time)

### Static Reference Files

Files that don't change frequently can use descriptive names:
- `organization_reference.json`
- `field_definitions.json`
- `schema_documentation.json`

## Standard Archive Structure

All timestamped archive files MUST follow this structure:

```json
{
  "metadata": {
    "archive_timestamp": "2026-02-19T12:13:32.075438",
    "scraper": "wpa_scraper.py",
    "data_source": "https://wpapool.com/rankings",
    "archive_format_version": "1.0",
    "total_records": 312
  },
  "statistics": {
    "total_records": 312,
    "field_coverage": {
      "license_number": {"count": 312, "percent": 100.0},
      "country": {"count": 310, "percent": 99.36}
    },
    "custom_stats": {}
  },
  "data": [
    // Array of data records
  ]
}
```

### Required Metadata Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `archive_timestamp` | ISO 8601 string | When archive was created | `"2026-02-19T12:13:32.075438"` |
| `scraper` | string | Scraper filename | `"wpa_scraper.py"` |
| `archive_format_version` | string | Format version | `"1.0"` |
| `total_records` | integer | Number of records | `312` |

### Optional Metadata Fields

| Field | Type | Description |
|-------|------|-------------|
| `data_source` | string | Source URL or description |
| `ranking_system` | string | System identifier (e.g., "WPA_Women") |
| `scrape_date` | string | When data was scraped (if different from archive) |
| `scraper_version` | string | Version of scraper script |
| `notes` | string | Additional information |

### Statistics Section

The `statistics` section should include:
- `total_records`: Count of records (required)
- Field coverage stats (recommended)
- Domain-specific statistics (recommended)

Example:
```json
"statistics": {
  "total_records": 312,
  "players_with_licenses": 312,
  "organizations": {
    "BCA": 140,
    "ACBS": 91,
    "EPBF": 65
  },
  "country_distribution": {
    "USA": 140,
    "CHN": 45
  }
}
```

## Using the Archive Utility

### Basic Usage

```python
from scrapers.archive_utils import DataArchiver

# Initialize archiver
archiver = DataArchiver('wpba')

# Scrape data
data = scraper.scrape_rankings()

# Archive with metadata
archiver.archive_data(
    data=data,
    metadata={
        'data_source': 'https://wpba.com/rankings',
        'ranking_system': 'WPBA_Women'
    },
    filename_suffix='rankings'
)
```

### Quick Archive Function

```python
from scrapers.archive_utils import quick_archive

data = scraper.scrape_rankings()

quick_archive(
    scraper_name='wpba',
    data=data,
    data_source='https://wpba.com/rankings'
)
```

### Creating Archive README

```python
archiver = DataArchiver('wpba')

archiver.create_readme(
    description="WPBA Women's Rankings Archive",
    data_sources=['https://wpba.com/rankings'],
    file_types={
        'wpba_rankings_*.json': 'Current rankings data',
        'wpba_summary_*.json': 'Summary statistics'
    }
)
```

## Scraper Integration Pattern

### Standard Scraper Template

```python
#!/usr/bin/env python3
"""
{Scraper Name} Scraper
Scrapes data from {source}
"""

import logging
from typing import List, Dict
from scrapers.archive_utils import DataArchiver

logger = logging.getLogger(__name__)


class MyScraper:
    """Scraper for {source}"""
    
    def __init__(self):
        self.base_url = "https://example.com"
        self.archiver = DataArchiver('myscraper')
    
    def scrape_data(self) -> List[Dict]:
        """Scrape data from source"""
        # Scraping logic here
        data = []
        return data
    
    def scrape_and_archive(self) -> Dict:
        """Scrape data and create archive"""
        logger.info("Starting scrape...")
        
        # Scrape data
        data = self.scrape_data()
        
        # Archive data
        archive_path = self.archiver.archive_data(
            data=data,
            metadata={
                'data_source': self.base_url,
                'scraper_version': '1.0'
            },
            filename_suffix='data'
        )
        
        logger.info(f"Archived to {archive_path}")
        
        return {
            'records_scraped': len(data),
            'archive_path': str(archive_path),
            'timestamp': self.archiver.iso_timestamp
        }


if __name__ == '__main__':
    scraper = MyScraper()
    result = scraper.scrape_and_archive()
    print(f"Scraped {result['records_scraped']} records")
```

## README Template

Each archive directory MUST include a README.md. Use the archiver utility to generate:

```python
archiver.create_readme(
    description="Description of what this archive contains",
    data_sources=["https://source1.com", "https://source2.com"],
    file_types={
        'pattern_*.json': 'Description of file type'
    }
)
```

## Archive Management

### Loading Archives

```python
from scrapers.archive_utils import DataArchiver

archiver = DataArchiver('wpba')

# Load most recent archive
latest = archiver.load_latest_archive('rankings')

# Access data
metadata = latest['metadata']
data = latest['data']
stats = latest['statistics']
```

### Listing Archives

```python
archiver = DataArchiver('wpba')

archives = archiver.list_archives()

for archive in archives:
    print(f"{archive['filename']} - {archive['total_records']} records")
```

## Best Practices

### DO:
✅ Use `DataArchiver` for all archival operations
✅ Include comprehensive metadata
✅ Calculate meaningful statistics
✅ Create README for each archive directory
✅ Use descriptive filename suffixes
✅ Keep archives immutable (never modify after creation)
✅ Include data source URLs
✅ Document field definitions in README
✅ Compress old archives (>6 months) with gzip

### DON'T:
❌ Create archives without timestamps
❌ Modify existing archive files
❌ Use non-standard filename formats
❌ Skip metadata or statistics sections
❌ Store archives outside `data/` directory
❌ Create archives without corresponding README
❌ Use uppercase in filenames
❌ Include credentials or API keys in archives

## Data Quality Standards

All archived data MUST:
- Be valid JSON
- Include complete metadata
- Be deduplicated (no duplicate records)
- Have consistent field names
- Include non-null values where expected

## Archive Maintenance

### Regular Maintenance Tasks

1. **Weekly:**
   - Review recent archives for completeness
   - Verify archive file sizes are reasonable

2. **Monthly:**
   - Compare archive statistics for anomalies
   - Update README files with new patterns

3. **Quarterly:**
   - Compress archives older than 6 months
   - Archive to external backup storage
   - Review and clean up legacy files

### Compression

For archives older than 6 months:
```bash
gzip data/wpba_archive/wpba_rankings_20250815_*.json
```

### Backup

Regular backups to external storage:
```bash
rsync -av data/*_archive/ /backup/rankings-bot/archives/
```

## Migration Guide

### Migrating Existing Scrapers

1. **Import archive utility:**
   ```python
   from scrapers.archive_utils import DataArchiver
   ```

2. **Initialize archiver in __init__:**
   ```python
   self.archiver = DataArchiver('scraper_name')
   ```

3. **Replace manual file writing with archiver:**
   ```python
   # Old way
   with open(f'data/output_{date}.json', 'w') as f:
       json.dump(data, f)
   
   # New way
   self.archiver.archive_data(
       data=data,
       metadata={'data_source': source_url}
   )
   ```

4. **Create README:**
   ```python
   self.archiver.create_readme(
       description="...",
       data_sources=["..."],
       file_types={...}
   )
   ```

## Examples

### Example: WPA Archive
See `data/wpa_archive/` for reference implementation:
- Proper file naming
- Complete metadata
- Statistics section
- README documentation
- Organization reference

### Example: Simple Scraper

```python
from scrapers.archive_utils import quick_archive

data = my_scraper.get_rankings()

quick_archive(
    scraper_name='my_scraper',
    data=data,
    data_source='https://example.com/rankings'
)
```

## Compliance Checklist

Before completing a scraper, verify:

- [ ] Archive directory created (`data/{scraper}_archive/`)
- [ ] Timestamped archives use correct format
- [ ] All archives include metadata section
- [ ] All archives include statistics section
- [ ] README.md created in archive directory
- [ ] Scraper uses `DataArchiver` utility
- [ ] File naming follows convention
- [ ] No sensitive data in archives
- [ ] Archives are valid JSON
- [ ] Data is deduplicated

## Support

For questions or issues:
- Review `scrapers/archive_utils.py` source code
- Check `data/wpa_archive/` reference implementation
- Refer to project documentation

## Version History

- **1.0** (2026-02-19): Initial archival standards established
