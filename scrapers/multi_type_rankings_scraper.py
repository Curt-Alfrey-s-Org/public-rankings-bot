#!/usr/bin/env python3
"""
Multi-type Rankings Scraper with Player Merging
Fetches WPBA and WPA data, merges shared players in one pass.
No complex deduplication logic - just merge at scrape time.
"""

import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from difflib import SequenceMatcher
from scrapers.wpa_scraper import WPAScraper
from scrapers.wpba_scraper import WPBAScraper
from scrapers.org_metadata_scraper import OrgMetadataScraper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _ollama_name_match(name_a: str, name_b: str) -> Optional[bool]:
    """Ask Ollama whether two player names refer to the same person.
    Returns True/False if Ollama is available and confident, None otherwise."""
    try:
        from api.services.ollama_name_resolver import resolve_name_match
        result = asyncio.get_event_loop().run_until_complete(
            resolve_name_match(name_a, name_b, context={"system_a": "WPBA", "system_b": "WPA"})
        )
        if result is None:
            return None
        if result.confidence >= 0.8:
            return result.same_person
        return None
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            from api.services.ollama_name_resolver import resolve_name_match
            result = loop.run_until_complete(
                resolve_name_match(name_a, name_b, context={"system_a": "WPBA", "system_b": "WPA"})
            )
            if result is None:
                return None
            if result.confidence >= 0.8:
                return result.same_person
            return None
        finally:
            loop.close()
    except Exception as e:
        logger.debug("Ollama name match unavailable: %s", e)
        return None


class MultiTypeRankingsScraper:
    """Scrape and merge WPBA/WPA players in one pass"""
    
    def __init__(self):
        """Initialize scraper with all sub-scrapers"""
        self.wpa_scraper = WPAScraper()
        self.wpba_scraper = WPBAScraper()
        self.metadata_scraper = OrgMetadataScraper()

        # Save location for scraped data
        self.scraped_data_dir = Path("scraped_data/multi_type")
        self.scraped_data_dir.mkdir(parents=True, exist_ok=True)

        # Ranking types we support
        self.ranking_types = [
            {'code': 'WPBA_Women', 'display': 'WPBA Women', 'org': 'WPBA', 'division': 'Women'},
            {'code': 'WPA_Men', 'display': 'WPA Men', 'org': 'WPA', 'division': 'Men'},
            {'code': 'WPA_Women', 'display': 'WPA Women', 'org': 'WPA', 'division': 'Women'},
            {'code': 'WPA_Heyball', 'display': 'WPA Heyball', 'org': 'WPA', 'division': 'Heyball'},
            {'code': 'WPA_Artistic', 'display': 'WPA Artistic', 'org': 'WPA', 'division': 'Artistic'},
        ]
    
    def scrape_and_merge(self) -> List[Dict]:
        """
        Scrape WPBA and WPA rankings, merge shared players.
        
        Returns:
            Single unified list with merged player data:
            {
                'name': 'Alice Smith',
                'wpba_rank': 5,
                'wpba_points': 1200.0,
                'wpa_rank': 8,
                'wpa_points': 950.0,
                'wpa_division': 'Women',  # 'Men' or 'Women' for WPA
                'country': 'USA',
                'license': 'A12345',
                'org': 'both'  # 'wpba', 'wpa', or 'both'
            }
        """
        logger.info("Scraping WPBA rankings...")
        wpba_data = self.wpba_scraper.scrape_rankings()
        logger.info("✓ Got %d WPBA players", len(wpba_data))
        
        logger.info("Scraping WPA Men + Women rankings (single /rankings/ crawl)...")
        wpa_bundle = self.wpa_scraper.scrape_all_html_divisions(persist=True)
        wpa_men_data = wpa_bundle.get("men") or []
        wpa_women_data = wpa_bundle.get("women") or []
        logger.info("✓ Got %d WPA Men players", len(wpa_men_data))
        logger.info("✓ Got %d WPA Women players", len(wpa_women_data))
        
        # Combine WPA data with division info
        wpa_data = []
        for p in wpa_men_data:
            p['wpa_division'] = 'Men'
            wpa_data.append(p)
        for p in wpa_women_data:
            p['wpa_division'] = 'Women'
            wpa_data.append(p)
        logger.info("✓ Got %d total WPA players (%d Men, %d Women)", 
                   len(wpa_data), len(wpa_men_data), len(wpa_women_data))
        
        logger.info("Merging WPBA + WPA into unified records...")
        
        # Build lookup for fast matching
        wpa_by_name = {p['name'].lower(): p for p in wpa_data}
        
        merged = {}
        matched_wpa_names = set()
        
        # 1. Process WPBA players
        for wpba_player in wpba_data:
            name_lower = wpba_player['name'].lower()
            
            # Look for matching WPA player (exact first, then fuzzy)
            wpa_match_key = self._find_match(wpba_player['name'], wpa_by_name)
            
            if wpa_match_key:
                matched_wpa_names.add(wpa_match_key)
                wpa_player_data = wpa_by_name[wpa_match_key]
                
                # Merge: WPBA name is authority; license from WPA or WPBA when present
                merged[name_lower] = {
                    'name': wpba_player['name'],
                    'wpba_rank': wpba_player.get('rank'),
                    'wpba_points': wpba_player.get('points'),
                    'wpa_rank': wpa_player_data.get('rank'),
                    'wpa_points': wpa_player_data.get('points'),
                    'wpa_division': wpa_player_data.get('wpa_division'),
                    'country': wpa_player_data.get('country'),
                    'license': wpa_player_data.get('license_number') or wpba_player.get('license_number'),
                    'org': 'both'
                }
                logger.debug(f"✓ Merged: {wpba_player['name']} (WPBA#{wpba_player.get('rank')} WPA#{wpa_player_data.get('rank')})")
            else:
                # WPBA only (include license_number from WPBA PDF when present)
                merged[name_lower] = {
                    'name': wpba_player['name'],
                    'wpba_rank': wpba_player.get('rank'),
                    'wpba_points': wpba_player.get('points'),
                    'wpa_rank': None,
                    'wpa_points': None,
                    'wpa_division': None,
                    'country': None,
                    'license': wpba_player.get('license_number'),
                    'org': 'wpba'
                }
                logger.debug(f"  WPBA only: {wpba_player['name']}")
        
        # 2. Add WPA-only players
        wpa_only_count = 0
        for wpa_player in wpa_data:
            name_lower = wpa_player['name'].lower()
            
            if name_lower not in matched_wpa_names and name_lower not in merged:
                merged[name_lower] = {
                    'name': wpa_player['name'],
                    'wpba_rank': None,
                    'wpba_points': None,
                    'wpa_rank': wpa_player.get('rank'),
                    'wpa_points': wpa_player.get('points'),
                    'wpa_division': wpa_player.get('wpa_division'),
                    'country': wpa_player.get('country'),
                    'license': wpa_player.get('license_number'),
                    'org': 'wpa'
                }
                wpa_only_count += 1
                logger.debug(f"  WPA only: {wpa_player['name']}")
        
        result = list(merged.values())
        logger.info("✓ Merged into %d unified player records (%d WPBA+WPA, %d WPA-only)", 
                   len(result), len(result) - wpa_only_count, wpa_only_count)
        return result
    
    @staticmethod
    def _find_match(player_name: str, lookup_dict: Dict, threshold: float = 0.85) -> Optional[str]:
        """
        Find matching player in lookup_dict using fuzzy name matching.
        Falls back to LLM arbitration for ambiguous scores (0.60-0.84).

        Args:
            player_name: Name to match
            lookup_dict: Dict with lowercase names as keys
            threshold: Similarity score (0.0-1.0) required to match

        Returns:
            Matched key from lookup_dict or None
        """
        name_lower = player_name.lower()

        if name_lower in lookup_dict:
            return name_lower

        best_match_key = None
        best_score = 0

        for lookup_name in lookup_dict.keys():
            if abs(len(name_lower) - len(lookup_name)) > 5:
                continue

            score = SequenceMatcher(None, name_lower, lookup_name).ratio()
            if score > best_score:
                best_score = score
                best_match_key = lookup_name

        if best_score >= threshold:
            return best_match_key

        AMBIGUOUS_LOW = 0.60
        if AMBIGUOUS_LOW <= best_score < threshold and best_match_key:
            llm_result = _ollama_name_match(player_name, lookup_dict[best_match_key].get("name", best_match_key))
            if llm_result is True:
                logger.info(
                    "LLM confirmed match: '%s' <-> '%s' (SequenceMatcher=%.2f)",
                    player_name, best_match_key, best_score,
                )
                return best_match_key
            elif llm_result is False:
                logger.debug(
                    "LLM rejected match: '%s' <-> '%s' (SequenceMatcher=%.2f)",
                    player_name, best_match_key, best_score,
                )

        return None
    
    def scrape_all_rankings(self) -> Dict[str, List[Dict]]:
        """
        Scrape all ranking types (old API for backward compatibility)
        
        Returns:
            Dict mapping ranking_type to list of rankings
        """
        logger.info("Starting multi-type rankings scrape (legacy API)")
        wpa_all = self.wpa_scraper.scrape_all_divisions(include_artistic=True, persist=True)
        results = {
            'WPBA_Women': self.wpba_scraper.scrape_rankings(),
            'WPA_Men': wpa_all.get('men') or [],
            'WPA_Women': wpa_all.get('women') or [],
            'WPA_Heyball': (wpa_all.get('heyball_men') or []) + (wpa_all.get('heyball_women') or []),
            'WPA_Artistic': wpa_all.get('artistic') or [],
        }
        
        logger.info("Multi-type scrape complete: %s", 
                   {k: len(v) for k, v in results.items()})
        
        return results

    def _scrape_wpa_division(self, division: str) -> List[Dict]:
        """Scrape WPA rankings for a specific division (Heyball, Artistic, etc.)."""
        logger.info("Fetching WPA %s rankings", division)
        try:
            rankings = self.wpa_scraper.scrape_rankings(division=division)
            logger.info("Scraped %s WPA %s rankings", len(rankings), division)
            return rankings
        except Exception as e:
            logger.error("WPA %s scrape failed: %s", division, e)
            raise
    
    def _scrape_wpa_men(self) -> List[Dict]:
        """
        Scrape WPA Men rankings
        
        Returns:
            List of ranking dicts
        """
        logger.info("Fetching WPA Men rankings")
        
        try:
            rankings = self.wpa_scraper.scrape_rankings(division='Men')
            logger.info("Scraped %s WPA Men rankings", len(rankings))
            return rankings
            
        except Exception as e:
            logger.error("WPA Men scrape failed: %s", e)
            raise
    
    def _scrape_wpa_women(self) -> List[Dict]:
        """
        Scrape WPA Women rankings
        
        Returns:
            List of ranking dicts
        """
        logger.info("Fetching WPA Women rankings")
        
        try:
            rankings = self.wpa_scraper.scrape_rankings(division='Women')
            logger.info("Scraped %s WPA Women rankings", len(rankings))
            return rankings
            
        except Exception as e:
            logger.error("WPA Women scrape failed: %s", e)
            raise
    
    
    def deduplicate_rankings(self, all_rankings: Dict[str, List[Dict]]) -> Tuple[Dict[str, List[Dict]], Dict]:
        """
        (Legacy API - kept for backward compatibility)
        Old deduplication logic replaced by scrape_and_merge()
        """
        logger.warning("deduplicate_rankings() is deprecated - use scrape_and_merge() instead")
        return all_rankings, {'total_before': 0, 'total_after': 0, 'duplicates_removed': 0}


def main():
    """Test the multi-type scraper with merged data"""
    scraper = MultiTypeRankingsScraper()
    
    # New simplified approach: scrape and merge in one call
    merged_players = scraper.scrape_and_merge()
    
    # Print results
    print("\n" + "="*60)
    print("✓ SCRAPE AND MERGE RESULTS")
    print("="*60)
    print(f"Total unified players: {len(merged_players)}")
    
    # Count by organization
    both_count = sum(1 for p in merged_players if p['org'] == 'both')
    wpba_only = sum(1 for p in merged_players if p['org'] == 'wpba')
    wpa_only = sum(1 for p in merged_players if p['org'] == 'wpa')
    
    print(f"\nBreakdown:")
    print(f"  In both WPBA and WPA:  {both_count}")
    print(f"  WPBA only:             {wpba_only}")
    print(f"  WPA only:              {wpa_only}")
    
    # Show examples of merged players
    print(f"\nTop 10 merged players (in both orgs):")
    merged_both = [p for p in merged_players if p['org'] == 'both']
    for i, player in enumerate(merged_both[:10], 1):
        wpba_str = f"WPBA#{player['wpba_rank']}" if player['wpba_rank'] else "—"
        wpa_str = f"WPA#{player['wpa_rank']}" if player['wpa_rank'] else "—"
        country = player['country'] or 'N/A'
        print(f"  {i}. {player['name']:30} | {wpba_str:10} {wpa_str:10} | {country}")
    
    # Show some WPBA-only examples
    if wpba_only > 0:
        print(f"\nSample WPBA-only players (first 5):")
        wpba_players = [p for p in merged_players if p['org'] == 'wpba']
        for i, player in enumerate(wpba_players[:5], 1):
            rank_str = f"#{player['wpba_rank']}" if player['wpba_rank'] else "—"
            print(f"  {i}. {player['name']:30} | {rank_str}")
    
    # Show some WPA-only examples
    if wpa_only > 0:
        print(f"\nSample WPA-only players (first 5):")
        wpa_players = [p for p in merged_players if p['org'] == 'wpa']
        for i, player in enumerate(wpa_players[:5], 1):
            rank_str = f"#{player['wpa_rank']}" if player['wpa_rank'] else "—"
            print(f"  {i}. {player['name']:30} | {rank_str}")
    
    print("\n" + "="*60)


if __name__ == '__main__':
    main()
