#!/usr/bin/env python3
"""
Debug script to inspect ExternalPool HTML structure

This script helps identify the correct CSS selectors and HTML patterns
used by ExternalPool so we can fix the scrapers.
"""

import requests
import json
import re
from pathlib import Path
from bs4 import BeautifulSoup
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

class CpDebugger:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
        })
        self.debug_output = Path('scripts/debug_output')
        self.debug_output.mkdir(exist_ok=True)
    
    def inspect_tournament_page(self, url):
        """Fetch and inspect a tournament page."""
        logger.info(f"Inspecting: {url}")
        
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                logger.error(f"  Failed: HTTP {response.status_code}")
                return
            
            html = response.text
            
            # Save raw HTML for manual inspection
            tournament_name = url.split('/')[-2]
            html_file = self.debug_output / f"{tournament_name}_raw.html"
            with open(html_file, 'w') as f:
                f.write(html)
            logger.info(f"  ✓ Saved HTML: {html_file}")
            
            # Analyze structure
            soup = BeautifulSoup(html, 'html.parser')
            analysis = self._analyze_structure(soup, html)
            
            # Save analysis
            analysis_file = self.debug_output / f"{tournament_name}_analysis.json"
            with open(analysis_file, 'w') as f:
                json.dump(analysis, f, indent=2)
            logger.info(f"  ✓ Saved analysis: {analysis_file}")
            
            return analysis
        
        except Exception as e:
            logger.error(f"  Error: {e}")
            return None
    
    def _analyze_structure(self, soup, html):
        """Analyze HTML structure and find selectors."""
        analysis = {
            'page_structure': self._find_main_elements(soup),
            'player_patterns': self._find_player_patterns(soup, html),
            'match_patterns': self._find_match_patterns(soup, html),
            'data_attributes': self._find_data_attributes(soup),
            'script_tags': self._find_script_data(html),
            'recommendations': []
        }
        
        # Generate recommendations
        if analysis['player_patterns']['count'] > 0:
            analysis['recommendations'].append(
                f"Found {analysis['player_patterns']['count']} player pattern matches"
            )
        else:
            analysis['recommendations'].append(
                "No player patterns found - HTML structure may be different"
            )
        
        if analysis['script_tags']:
            analysis['recommendations'].append(
                "Tournament data embedded in JavaScript - inspect script tags"
            )
        
        return analysis
    
    def _find_main_elements(self, soup):
        """Find main page structure elements."""
        structure = {
            'divs_with_class_bracket': len(soup.find_all('div', class_=re.compile(r'bracket', re.I))),
            'divs_with_class_tournament': len(soup.find_all('div', class_=re.compile(r'tournament', re.I))),
            'divs_with_class_player': len(soup.find_all('div', class_=re.compile(r'player', re.I))),
            'divs_with_class_match': len(soup.find_all('div', class_=re.compile(r'match', re.I))),
            'tables': len(soup.find_all('table')),
            'table_rows': len(soup.find_all('tr')),
            'table_cells': len(soup.find_all(re.compile(r'td|th'))),
        }
        return structure
    
    def _find_player_patterns(self, soup, html):
        """Find player name patterns."""
        patterns = {
            'count': 0,
            'by_tag': {},
            'sample_names': [],
        }
        
        # Look for various player name patterns
        # Pattern 1: Names after flag images
        flag_pattern = r'<img[^>]*src=["\'].*?flags?/([a-z]{2})(?:\.svg|\.png)?["\'][^>]*>\s*([A-Z][a-zA-Z\s\-\.\']+)'
        
        matches = list(re.finditer(flag_pattern, html, re.IGNORECASE))
        if matches:
            patterns['by_tag']['flag_images'] = len(matches)
            patterns['count'] += len(matches)
            patterns['sample_names'].extend([m.group(2) for m in matches[:5]])
        
        # Pattern 2: Names in data attributes
        data_pattern = r'data-player[^>]*=["\']([A-Z][a-zA-Z\s\-\.\']+)["\']'
        matches = list(re.finditer(data_pattern, html, re.IGNORECASE))
        if matches:
            patterns['by_tag']['data_attributes'] = len(matches)
            patterns['count'] += len(matches)
            patterns['sample_names'].extend([m.group(1) for m in matches[:5]])
        
        # Pattern 3: Names in specific element types
        for name_elem in soup.find_all(re.compile(r'span|div|td'), string=re.compile(r'^[A-Z][a-zA-Z\s\-\.\']{2,}$')):
            if len(name_elem.string) > 2 and len(name_elem.string) < 50:
                patterns['sample_names'].append(name_elem.string)
                patterns['count'] += 1
        
        patterns['sample_names'] = patterns['sample_names'][:20]  # Limit to 20
        
        return patterns
    
    def _find_match_patterns(self, soup, html):
        """Find match score patterns."""
        patterns = {
            'count': 0,
            'examples': [],
        }
        
        # Pattern: score format (9-6), (9-4), etc.
        score_pattern = r'\((\d)-(\d)\)|\s(\d)-(\d)\s|(\d)\s*-\s*(\d)'
        
        matches = list(re.finditer(score_pattern, html))
        patterns['count'] = len(matches)
        patterns['examples'] = [m.group(0) for m in matches[:20]]
        
        return patterns
    
    def _find_data_attributes(self, soup):
        """Find custom data attributes in HTML."""
        attributes = {}
        
        for tag in soup.find_all(True):
            for attr in tag.attrs:
                if attr.startswith('data-'):
                    key = attr
                    if key not in attributes:
                        attributes[key] = 0
                    attributes[key] += 1
        
        return attributes
    
    def _find_script_data(self, html):
        """Look for tournament data in script tags."""
        scripts = []
        
        # Pattern: Look for JSON data in script tags
        script_pattern = r'<script[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>'
        
        matches = re.finditer(script_pattern, html, re.DOTALL)
        for i, match in enumerate(matches):
            content = match.group(1).strip()
            try:
                data = json.loads(content)
                scripts.append({
                    'index': i,
                    'type': 'json',
                    'size_bytes': len(content),
                    'keys': list(data.keys()) if isinstance(data, dict) else 'array',
                })
            except Exception as e:
                logger.debug("Invalid JSON script block at index %s: %s", i, e)
                scripts.append({
                    'index': i,
                    'type': 'invalid_json',
                    'size_bytes': len(content),
                })
        
        # Pattern: Look for window.data or similar globals
        global_pattern = r'(?:window|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*(\{[^;]*\}|\[[^\]]*\])'
        
        matches = re.finditer(global_pattern, html)
        for match in matches:
            var_name = match.group(1)
            var_content = match.group(2)
            
            # Try to parse as JSON
            try:
                data = json.loads(var_content)
                scripts.append({
                    'index': len(scripts),
                    'type': 'global_json',
                    'variable': var_name,
                    'keys': list(data.keys()) if isinstance(data, dict) else 'array',
                })
            except Exception as e:
                logger.debug("Global variable '%s' is not JSON: %s", var_name, e)
                scripts.append({
                    'index': len(scripts),
                    'type': 'global_non_json',
                    'variable': var_name,
                    'preview': var_content[:100],
                })
        
        return scripts
    
    def run(self):
        """Run debugging on known tournament URLs."""
        logger.info("=" * 70)
        logger.info("CP (external pool) HTML Structure Debugger")
        logger.info("=" * 70)
        
        tournaments = [
            'https://www.digitalpool.com/tournaments/2026-wpba-classics-players-championship/bracket',
            'https://www.digitalpool.com/tournaments/2025-wpba-olhausen-colorado-classic/bracket',
            'https://www.digitalpool.com/tournaments/2025-olhausen-iron-city-invitational-vi/bracket',
        ]
        
        results = {}
        
        for url in tournaments:
            logger.info(f"\n{'='*70}")
            analysis = self.inspect_tournament_page(url)
            if analysis:
                results[url] = analysis
        
        # Save summary
        summary_file = self.debug_output / 'debug_summary.json'
        with open(summary_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"\n{'='*70}")
        logger.info(f"Debug output saved to: {self.debug_output}/")
        logger.info("\nNext steps:")
        logger.info("1. Review HTML files to understand structure")
        logger.info("2. Check analysis.json for found selectors")
        logger.info("3. Update scrapers with correct CSS selectors")
        logger.info("4. Test updated scrapers")
        logger.info("=" * 70)

if __name__ == '__main__':
    debugger = CpDebugger()
    debugger.run()
