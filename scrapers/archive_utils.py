"""
Standardized Data Archival Utilities

Provides consistent archival format for all scrapers following project standards.
All scraped data should be archived with proper metadata, statistics, and structure.

Usage:
    from scrapers.archive_utils import DataArchiver
    
    archiver = DataArchiver('wpba', 'data/wpba_archive')
    archiver.archive_data(data, metadata={'source': 'wpba.com'})
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class DataArchiver:
    """Handles standardized data archival for scrapers"""
    
    ARCHIVE_FORMAT_VERSION = "1.0"
    
    def __init__(self, scraper_name: str, archive_dir: str = None):
        """
        Initialize archiver
        
        Args:
            scraper_name: Name of scraper (e.g., 'wpba', 'wpa', 'tournament')
            archive_dir: Directory to store archives (default: data/{scraper_name}_archive)
        """
        self.scraper_name = scraper_name
        
        if archive_dir is None:
            archive_dir = f'data/{scraper_name}_archive'
        
        self.archive_dir = Path(archive_dir)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.iso_timestamp = datetime.now().isoformat()
    
    def archive_data(
        self,
        data: List[Dict],
        metadata: Optional[Dict[str, Any]] = None,
        statistics: Optional[Dict[str, Any]] = None,
        filename_suffix: str = 'data'
    ) -> Path:
        """
        Archive data with standardized format
        
        Args:
            data: List of data records to archive
            metadata: Additional metadata (merged with standard metadata)
            statistics: Statistics about the data
            filename_suffix: Suffix for filename (default: 'data')
        
        Returns:
            Path to created archive file
        """
        # Build standard metadata
        standard_metadata = {
            'archive_timestamp': self.iso_timestamp,
            'scraper': f'{self.scraper_name}_scraper.py',
            'archive_format_version': self.ARCHIVE_FORMAT_VERSION,
            'total_records': len(data)
        }
        
        if metadata:
            standard_metadata.update(metadata)
        
        # Calculate statistics if not provided
        if statistics is None:
            statistics = self._calculate_statistics(data)
        
        # Build archive structure
        archive = {
            'metadata': standard_metadata,
            'statistics': statistics,
            'data': data
        }
        
        # Generate filename
        filename = f'{self.scraper_name}_{filename_suffix}_{self.timestamp}.json'
        filepath = self.archive_dir / filename
        
        # Save archive
        with open(filepath, 'w') as f:
            json.dump(archive, f, indent=2)
        
        logger.info(f"Archived {len(data)} records to {filepath}")
        return filepath
    
    def archive_summary(
        self,
        summary_data: Dict[str, Any],
        filename_suffix: str = 'summary'
    ) -> Path:
        """
        Archive summary data (smaller, overview information)
        
        Args:
            summary_data: Dictionary of summary information
            filename_suffix: Suffix for filename (default: 'summary')
        
        Returns:
            Path to created summary file
        """
        summary = {
            'metadata': {
                'archive_timestamp': self.iso_timestamp,
                'scraper': f'{self.scraper_name}_scraper.py',
                'archive_format_version': self.ARCHIVE_FORMAT_VERSION
            },
            'summary': summary_data
        }
        
        filename = f'{self.scraper_name}_{filename_suffix}_{self.timestamp}.json'
        filepath = self.archive_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"Archived summary to {filepath}")
        return filepath
    
    def _calculate_statistics(self, data: List[Dict]) -> Dict[str, Any]:
        """Calculate basic statistics from data"""
        if not data:
            return {'total_records': 0}
        
        stats = {
            'total_records': len(data)
        }
        
        # Try to detect common fields and add stats
        if data and isinstance(data[0], dict):
            # Count non-null fields
            sample = data[0]
            for key in sample.keys():
                non_null = sum(1 for record in data if record.get(key) is not None)
                stats[f'{key}_coverage'] = {
                    'count': non_null,
                    'percent': round(non_null / len(data) * 100, 2)
                }
        
        return stats
    
    def create_readme(
        self,
        description: str,
        data_sources: List[str],
        file_types: Dict[str, str],
        usage_examples: Optional[str] = None
    ) -> Path:
        """
        Create standardized README for archive
        
        Args:
            description: Description of what this archive contains
            data_sources: List of data source URLs
            file_types: Dict mapping filename patterns to descriptions
            usage_examples: Optional code examples
        
        Returns:
            Path to created README
        """
        readme_content = f"""# {self.scraper_name.upper()} Data Archive

## Archive Information
- **Created:** {self.iso_timestamp.split('T')[0]}
- **Format Version:** {self.ARCHIVE_FORMAT_VERSION}
- **Scraper:** {self.scraper_name}_scraper.py

## Description

{description}

## Directory Structure

```
{self.scraper_name}_archive/
├── README.md                              # This file
"""
        
        for pattern, desc in file_types.items():
            readme_content += f"├── {pattern}    # {desc}\n"
        
        readme_content += "```\n\n"
        
        readme_content += """## File Naming Convention

All timestamped files follow the pattern: `<scraper>_<type>_YYYYMMDD_HHMMSS.json`
- Example: `{}_data_20260219_121332.json`
- Timestamp format: `YYYYMMDD_HHMMSS` (Year/Month/Day_Hour/Minute/Second)

## Data Format Standards

### Metadata Structure
All archive files include a `metadata` object with:
- `archive_timestamp`: ISO 8601 timestamp (when archive was created)
- `scraper`: Script used to collect data
- `archive_format_version`: Schema version (currently 1.0)
- `total_records`: Count of records in archive

### Standard Archive Structure
```json
{{
  "metadata": {{
    "archive_timestamp": "2026-02-19T12:00:00",
    "scraper": "{}_scraper.py",
    "archive_format_version": "1.0",
    "total_records": 100
  }},
  "statistics": {{
    "total_records": 100,
    "field_coverage": {{}}
  }},
  "data": [
    // Array of records
  ]
}}
```

## Data Sources

""".format(self.scraper_name, self.scraper_name)
        
        for source in data_sources:
            readme_content += f"- {source}\n"
        
        if usage_examples:
            readme_content += f"\n## Usage Examples\n\n{usage_examples}\n"
        else:
            readme_content += f"""
## Usage Examples

### Load Archive Data
```python
import json

with open('data/{self.scraper_name}_archive/{self.scraper_name}_data_YYYYMMDD_HHMMSS.json') as f:
    archive = json.load(f)
    
    metadata = archive['metadata']
    statistics = archive['statistics']
    data = archive['data']
    
    print(f"Archive from: {{metadata['archive_timestamp']}}")
    print(f"Total records: {{metadata['total_records']}}")
```

### Search Archive
```python
import json

with open('data/{self.scraper_name}_archive/{self.scraper_name}_data_YYYYMMDD_HHMMSS.json') as f:
    archive = json.load(f)
    
    # Search records
    results = [record for record in archive['data'] if 'search_term' in str(record)]
```
"""
        
        readme_content += """
## Maintenance Notes

- Archives are immutable once created (do not modify)
- Keep at least 3 most recent archives for comparison
- Older archives (>6 months) can be compressed: `gzip filename.json`
- Backup archives to external storage periodically

## Related Files

- **Scraper:** `scrapers/{}_scraper.py`
- **Archive Utility:** `scrapers/archive_utils.py`
- **Database:** `database/schema.sql`
""".format(self.scraper_name)
        
        readme_path = self.archive_dir / 'README.md'
        with open(readme_path, 'w') as f:
            f.write(readme_content)
        
        logger.info(f"Created README at {readme_path}")
        return readme_path
    
    def load_latest_archive(self, filename_pattern: str = None) -> Optional[Dict]:
        """
        Load the most recent archive file
        
        Args:
            filename_pattern: Pattern to match (e.g., 'data', 'summary')
        
        Returns:
            Archive data dictionary or None if no archives found
        """
        if filename_pattern:
            pattern = f'{self.scraper_name}_{filename_pattern}_*.json'
        else:
            pattern = f'{self.scraper_name}_*.json'
        
        archives = sorted(self.archive_dir.glob(pattern), reverse=True)
        
        if not archives:
            logger.warning(f"No archives found matching {pattern}")
            return None
        
        latest = archives[0]
        logger.info(f"Loading latest archive: {latest}")
        
        with open(latest, 'r') as f:
            return json.load(f)
    
    def list_archives(self) -> List[Dict[str, Any]]:
        """
        List all archives with metadata
        
        Returns:
            List of dicts with archive information
        """
        archives = []
        
        for archive_file in sorted(self.archive_dir.glob('*.json'), reverse=True):
            try:
                with open(archive_file, 'r') as f:
                    data = json.load(f)
                    metadata = data.get('metadata', {})
                    
                    archives.append({
                        'filename': archive_file.name,
                        'path': str(archive_file),
                        'timestamp': metadata.get('archive_timestamp'),
                        'total_records': metadata.get('total_records', 0),
                        'size_bytes': archive_file.stat().st_size
                    })
            except Exception as e:
                logger.warning(f"Could not read {archive_file}: {e}")
        
        return archives


def quick_archive(
    scraper_name: str,
    data: List[Dict],
    data_source: str,
    additional_metadata: Optional[Dict] = None
) -> Path:
    """
    Quick archival function for simple use cases
    
    Args:
        scraper_name: Name of scraper (e.g., 'wpba')
        data: Data to archive
        data_source: Source URL or description
        additional_metadata: Optional extra metadata
    
    Returns:
        Path to created archive
    """
    archiver = DataArchiver(scraper_name)
    
    metadata = {'data_source': data_source}
    if additional_metadata:
        metadata.update(additional_metadata)
    
    return archiver.archive_data(data, metadata=metadata)
