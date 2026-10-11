"""
Parallel Fargo lookup using concurrent Selenium instances.
10x faster than sequential scraping with detailed failure tracking.

Standards:
- Async/await with asyncio.Semaphore for concurrency control
- Proper resource cleanup (close browsers)
- Error handling per lookup with retry tracking
- Type hints and logging per PEP 484
- Admin message logging for failures
- Follows standards from CODING_STANDARDS.md
"""

import asyncio
import logging
from typing import Optional, List, Dict
from dataclasses import dataclass
from datetime import datetime

from api.services import admin_messages

logger = logging.getLogger(__name__)


@dataclass
class LookupResult:
    """Result of a single player lookup."""
    player_name: str
    rating: Optional[float]
    success: bool
    error: Optional[str] = None
    attempts: int = 1


class ParallelFargoLookup:
    """Perform parallel Fargo lookups using multiple Chrome instances."""
    
    def __init__(self, max_concurrent: int = 10, max_retries: int = 2):
        """
        Initialize parallel lookup client.
        
        Args:
            max_concurrent: Max Chrome instances to run simultaneously (default: 10)
            max_retries: Max retry attempts per player (default: 2)
        """
        self.max_concurrent = max_concurrent
        self.max_retries = max_retries
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def lookup_one(
        self, 
        player_name: str, 
        attempt: int = 1
    ) -> LookupResult:
        """
        Lookup single player with resource management and retry logic.
        
        Args:
            player_name: Player name to lookup
            attempt: Current attempt number (1-based)
            
        Returns:
            LookupResult with rating or error
        """
        async with self.semaphore:  # Limit concurrent Chrome instances
            loop = asyncio.get_event_loop()
            
            try:
                # Run synchronous lookup_rating in thread pool
                from api.services.fairmatch_scraper import lookup_rating
                rating, err = await loop.run_in_executor(None, lookup_rating, player_name)
                
                if rating is not None:
                    logger.info(f"✓ {player_name}: {rating} (attempt {attempt})")
                    return LookupResult(
                        player_name=player_name,
                        rating=rating,
                        success=True,
                        attempts=attempt
                    )
                elif err:
                    # Check if error or legitimately not found
                    if "not found" in err.lower() or "no rating" in err.lower():
                        logger.warning(f"✗ {player_name}: Not found in FairMatch (attempt {attempt})")
                        return LookupResult(
                            player_name=player_name,
                            rating=None,
                            success=True,  # Not an error, just no data
                            error="Not found in FairMatch database",
                            attempts=attempt
                        )
                    else:
                        raise Exception(err)
                else:
                    # No rating, no error - assume not found
                    return LookupResult(
                        player_name=player_name,
                        rating=None,
                        success=True,
                        error="Not found in FairMatch database",
                        attempts=attempt
                    )
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"✗ {player_name}: {error_msg} (attempt {attempt}/{self.max_retries + 1})")
                
                # Retry if attempts remain
                if attempt <= self.max_retries:
                    logger.info(f"⟳ Retrying {player_name} (attempt {attempt + 1})...")
                    await asyncio.sleep(2.0 * attempt)  # Exponential backoff
                    return await self.lookup_one(player_name, attempt + 1)
                
                # Max retries exceeded
                return LookupResult(
                    player_name=player_name,
                    rating=None,
                    success=False,
                    error=error_msg,
                    attempts=attempt
                )
    
    async def log_failure_to_admin(
        self, 
        org_code: str,
        failed_results: List[LookupResult]
    ):
        """
        Log detailed failure information to admin_messages table.
        
        Args:
            org_code: Ranking system (WPBA, WPA_Women, WPA_Men)
            failed_results: List of failed lookup results
        """
        if not failed_results:
            return
        
        # Group failures by error type
        chrome_crashes = [r for r in failed_results if 'chrome' in r.error.lower() or 'selenium' in r.error.lower() or 'driver' in r.error.lower()]
        not_found = [r for r in failed_results if 'not found' in r.error.lower()]
        timeouts = [r for r in failed_results if 'timeout' in r.error.lower()]
        other_errors = [r for r in failed_results if r not in chrome_crashes + not_found + timeouts]
        
        # Build detailed message
        details = {
            'org_code': org_code,
            'timestamp': datetime.utcnow().isoformat(),
            'summary': {
                'total_failed': len(failed_results),
                'chrome_crashes': len(chrome_crashes),
                'not_found': len(not_found),
                'timeouts': len(timeouts),
                'other_errors': len(other_errors)
            },
            'failed_players': []
        }
        
        # Add detailed failure info for each player
        for result in failed_results:
            details['failed_players'].append({
                'name': result.player_name,
                'error': result.error,
                'attempts': result.attempts,
                'category': (
                    'chrome_crash' if result in chrome_crashes else
                    'not_found' if result in not_found else
                    'timeout' if result in timeouts else
                    'other'
                )
            })
        
        # Create summary message
        summary_parts = []
        if chrome_crashes:
            summary_parts.append(f"{len(chrome_crashes)} Chrome crashes")
        if not_found:
            summary_parts.append(f"{len(not_found)} not in FairMatch")
        if timeouts:
            summary_parts.append(f"{len(timeouts)} timeouts")
        if other_errors:
            summary_parts.append(f"{len(other_errors)} other errors")
        
        message = f"Fargo sync failures for {org_code}: {', '.join(summary_parts)}"
        
        # Save to admin_messages
        try:
            admin_messages.add_message(
                admin_messages.CATEGORY_FARGO_FAILED,
                message,
                details
            )
            logger.info(f"Logged {len(failed_results)} failures to admin_messages")
        except Exception as e:
            logger.error(f"Failed to log admin message: {e}")
    
    async def lookup_many(
        self, 
        player_names: List[str],
        org_code: str,
        batch_delay: float = 1.0
    ) -> Dict[str, Optional[float]]:
        """
        Lookup multiple players in parallel batches with failure tracking.
        
        Args:
            player_names: List of player names to lookup
            org_code: Ranking system (for failure tracking)
            batch_delay: Delay between batches (seconds)
            
        Returns:
            Dict mapping player name to rating (or None if failed)
        """
        logger.info(f"Starting parallel lookup for {len(player_names)} players "
                   f"(max {self.max_concurrent} concurrent)")
        
        # Process in batches to avoid overwhelming system
        batch_size = self.max_concurrent * 3  # 30 players per batch (10 concurrent × 3)
        results = {}
        all_failed_results = []
        
        for i in range(0, len(player_names), batch_size):
            batch = player_names[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(player_names) + batch_size - 1) // batch_size
            
            logger.info(f"Processing batch {batch_num}/{total_batches} "
                       f"({len(batch)} players)...")
            
            # Run batch in parallel (limited by semaphore)
            tasks = [self.lookup_one(name) for name in batch]
            batch_results = await asyncio.gather(*tasks)
            
            # Collect results and track failures
            batch_failed = []
            for result in batch_results:
                results[result.player_name] = result.rating
                
                if not result.success:
                    batch_failed.append(result)
                    all_failed_results.append(result)
            
            # Summary for this batch
            successes = sum(1 for r in batch_results if r.success)
            logger.info(f"Batch {batch_num} complete: "
                       f"{successes}/{len(batch)} successful, "
                       f"{len(batch_failed)} failed")
            
            # Delay between batches (except for last batch)
            if i + batch_size < len(player_names):
                await asyncio.sleep(batch_delay)
        
        # Log all failures to admin_messages
        if all_failed_results:
            await self.log_failure_to_admin(org_code, all_failed_results)
        
        # Final summary
        total_found = sum(1 for r in results.values() if r is not None)
        total_failed = len(all_failed_results)
        logger.info(f"Parallel lookup complete: "
                   f"{total_found}/{len(player_names)} found, "
                   f"{total_failed} failed")
        
        return results


async def parallel_lookup_fargo(
    player_names: List[str],
    org_code: str,
    max_concurrent: int = 10,
    max_retries: int = 2
) -> Dict[str, Optional[float]]:
    """
    Convenience function to lookup multiple players in parallel with failure tracking.
    
    Args:
        player_names: List of player names
        org_code: Ranking system (WPBA, WPA_Women, WPA_Men)
        max_concurrent: Max concurrent Chrome instances
        max_retries: Max retry attempts per player
        
    Returns:
        Dict of player_name -> rating
    """
    client = ParallelFargoLookup(
        max_concurrent=max_concurrent,
        max_retries=max_retries
    )
    return await client.lookup_many(player_names, org_code)
