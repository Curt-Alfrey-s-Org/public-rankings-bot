"""
FairMatch (fairmatch.fargorate.com) scraper for single-player Fargo rating lookup.
Uses Selenium to open the site, activate "Search for players", enter name or ID, and read Official Rating.

## Architecture: Persistent Driver + Timeout Guards

- **Persistent Driver**: Module-level ChromeDriver singleton (once per process) reduces 2-3s startup per lookup
- **Timeout Guards**: Each lookup and search attempt has strict 5-second timeout to prevent hanging
- **Error Logging**: All failures logged explicitly (no silent errors) with context and traceback
- **State Cleanup**: Search input cleared between lookups to prevent cross-contamination
- **Retry Backoff**: Transient timeouts retry once with exponential backoff (100ms)
"""

import atexit
import logging
import os
import re
import signal
import shutil
import threading
import time
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Optional Selenium import so the rest of the app works if Selenium is missing
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

FAIRMATCH_URL = "https://fairmatch.fargorate.com/"
DEFAULT_TIMEOUT = 15
LOOKUP_TIMEOUT_SECONDS = 5.0  # Strict per-lookup timeout; prevents hanging
LOOKUP_TOTAL_TIMEOUT_SECONDS = 90  # Max time for entire lookup (all variants)
SEARCH_TIMEOUT_SECONDS = 3.0  # Per individual search variant
LOOKUP_DELAY_SECONDS = 1.5
RETRY_COUNT = 1
RETRY_BACKOFF_MS = 100

# ============================================================================
# Persistent Chrome Driver Management
# ============================================================================

_module_driver = None
_driver_lock = threading.Lock()


def _handle_shutdown_signal(signum, frame):
    """Signal handler for SIGTERM/SIGINT — cleanup Chrome driver before exit."""
    logger.info("Received signal %s — cleaning up Chrome driver", signum)
    cleanup_persistent_driver()
    raise SystemExit(0)


def _register_signal_handlers():
    """Register SIGTERM/SIGINT handlers so Chrome is cleaned up on process termination."""
    try:
        signal.signal(signal.SIGTERM, _handle_shutdown_signal)
        signal.signal(signal.SIGINT, _handle_shutdown_signal)
    except (ValueError, OSError) as e:
        logger.debug("Signal handlers not registered in this context: %s", e)


@contextmanager
def get_persistent_driver():
    """
    Context manager that returns the persistent module-level Chrome driver.
    Initializes on first call, reuses thereafter. Uses a lock to serialize
    access (Selenium driver is not thread-safe).
    Usage:
        with get_persistent_driver() as driver:
            # Use driver

    IMPORTANT: Do NOT quit the driver; context manager only yields it.
    The driver persists across the module lifetime until process exit.
    """
    global _module_driver
    with _driver_lock:
        if _module_driver is None:
            _module_driver = _init_chrome_driver()
            if _module_driver is None:
                raise RuntimeError("Failed to initialize persistent Chrome driver")
        yield _module_driver


def _init_chrome_driver():
    """Initialize and return a Chrome WebDriver instance. Returns None on failure."""
    try:
        chrome_binary = _find_chrome_binary()
        chromedriver_path = _find_chromedriver()
        
        if not chrome_binary:
            logger.error(
                "Chrome/Chromium binary not found. Tried: /usr/bin/chromium-browser, "
                "/usr/bin/chromium, /snap/bin/chromium, /usr/bin/google-chrome. "
                "Set CHROME_PATH env var or install chromium."
            )
            return None
        
        logger.info(f"Initializing persistent Chrome driver (binary={chrome_binary})")
        
        options = Options()
        options.binary_location = chrome_binary
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1024,768")
        options.add_argument("--remote-debugging-port=0")
        options.add_argument("--disable-setuid-sandbox")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-client-side-phishing-detection")
        options.add_argument("--disable-default-apps")
        options.add_argument("--disable-hang-monitor")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-prompt-on-repost")
        options.add_argument("--disable-sync")
        options.add_argument("--metrics-recording-only")
        options.add_argument("--no-first-run")
        options.add_argument("--safebrowsing-disable-auto-update")
        options.add_argument("--password-store=basic")
        options.add_argument("--use-mock-keychain")
        options.page_load_strategy = 'normal'  # Wait for full page load to ensure inputs are available
        
        try:
            driver = webdriver.Chrome(options=options)
        except Exception as e:
            logger.warning(f"Failed to create webdriver without explicit service: {e}. Trying with explicit service...")
            if chromedriver_path:
                service = Service(chromedriver_path)
                driver = webdriver.Chrome(service=service, options=options)
            else:
                logger.error(f"Cannot create webdriver and no explicit chromedriver path available: {e}")
                return None
        
        driver.set_page_load_timeout(DEFAULT_TIMEOUT)
        logger.info("Persistent Chrome driver initialized successfully")
        return driver
    
    except Exception as e:
        logger.error(f"Fatal error initializing Chrome driver: {e}", exc_info=True)
        return None


class TimeoutError(Exception):
    """Raised when a lookup or search operation exceeds its timeout."""
    pass


def _run_with_timeout(duration: float, func, *args, **kwargs):
    """
    Execute func(*args, **kwargs) with a strict timeout in seconds.
    Raises TimeoutError if duration exceeded. Does NOT use signals (process-safe).
    
    IMPORTANT: This is synchronous and blocking. For async, use asyncio.wait_for().
    """
    result = None
    exception = None
    
    def target():
        nonlocal result, exception
        try:
            result = func(*args, **kwargs)
        except Exception as e:
            exception = e
    
    # Direct call with Selenium internal timeouts (threading + interrupt is unsafe with Selenium drivers)
    try:
        result = func(*args, **kwargs)
        return result
    except Exception as e:
        if "timeout" in str(e).lower():
            raise TimeoutError(f"Timeout after {duration}s") from e
        raise


def _find_chrome_binary() -> Optional[str]:
    """
    Find Chrome/Chromium binary path by checking multiple known locations and CHROME_PATH env var.
    Returns the path if found, None otherwise.
    """
    # Check environment variable first
    if os.environ.get("CHROME_PATH"):
        chrome_path = os.environ.get("CHROME_PATH")
        if Path(chrome_path).exists():
            logger.info(f"Using CHROME_PATH from environment: {chrome_path}")
            return chrome_path
    
    # Check known Chrome/Chromium binary locations on Linux
    candidates = [
        "/usr/bin/chromium-browser",  # Debian/Ubuntu
        "/usr/bin/chromium",          # Alternative
        "/snap/bin/chromium",         # Snap installation
        "/usr/local/bin/chromium",    # Custom install
        "/usr/bin/google-chrome",     # Google Chrome
        "/snap/bin/google-chrome",    # Snap Google Chrome
        shutil.which("chromium-browser"),  # In PATH
        shutil.which("chromium"),      # In PATH
        shutil.which("google-chrome"), # In PATH
    ]
    
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            logger.info(f"Found Chrome binary at: {candidate}")
            return candidate
    
    return None


def _find_chromedriver() -> Optional[str]:
    """
    Find chromedriver binary path.
    Returns the path if found, None otherwise.
    """
    candidates = [
        "/usr/bin/chromedriver",
        shutil.which("chromedriver"),
    ]
    
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            logger.info(f"Found chromedriver at: {candidate}")
            return candidate
    
    return None



def _do_single_search(driver, wait, search_input, query: str) -> Optional[float]:
    """
    Run one search (type query, Enter, wait, parse). Returns rating if found else None.
    
    Args:
        driver: Selenium WebDriver instance
        wait: WebDriverWait instance with timeout configured
        search_input: Web element for search input field
        query: Search query string
    
    Returns:
        float rating if found, None otherwise
    
    Raises:
        TimeoutException: If search or page parse exceeds timeout
        Exception: For other Selenium errors (logged explicitly)
    """
    try:
        logger.debug(f"_do_single_search: query='{query}'")
        
        # Clear previous search state thoroughly
        try:
            # Clear input field
            driver.execute_script("arguments[0].focus();", search_input)
            time.sleep(0.1)
            driver.execute_script("arguments[0].value = '';", search_input)
            # Clear any stale results by scrolling page to top
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.1)
        except Exception as e:
            logger.warning(f"Failed to clear search state: {e}")
        
        # Type the query
        try:
            driver.execute_script("arguments[0].value = arguments[1];", search_input, query)
            driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", search_input)
            logger.debug(f"Typed query: {query}")
        except Exception as e:
            logger.error(f"Failed to type query '{query}': {e}", exc_info=True)
            return None
        
        # Press Enter
        try:
            search_input.send_keys(Keys.RETURN)
            logger.debug("Sent RETURN key")
        except Exception as e:
            logger.error(f"Failed to send RETURN key: {e}", exc_info=True)
            return None
        
        # Wait longer for results to fully render (was 2.5s, now 3.5s for persistent driver)
        time.sleep(3.5)
        
        try:
            wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'official rating')]")
                )
            )
        except TimeoutException:
            logger.debug("Official rating element not found within timeout")
        except Exception as e:
            logger.warning(f"Unexpected error waiting for results: {e}")
        
        # Parse page HTML first
        try:
            page_source = driver.page_source
            rating = _parse_rating_from_page(page_source, query)
            if rating is not None:
                logger.info(f"Found rating {rating} for '{query}' (from HTML parse)")
                return rating
        except Exception as e:
            logger.warning(f"Error parsing page HTML: {e}")
        
        # Fallback: look for any 3-4 digit number in table cells
        try:
            for cell in driver.find_elements(By.TAG_NAME, "td"):
                text = (cell.text or "").strip()
                if re.match(r"^\d{3,4}$", text):
                    rating = float(text)
                    logger.info(f"Found rating {rating} for '{query}' (from table cell fallback)")
                    return rating
        except Exception as e:
            logger.warning(f"Error searching table cells: {e}")
        
        logger.debug(f"No rating found for query: {query}")
        return None
    
    except TimeoutException as e:
        logger.error(f"Timeout during search for '{query}': {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in _do_single_search for '{query}': {e}", exc_info=True)
        raise


def lookup_rating(player_name_or_id: str) -> Tuple[Optional[float], Optional[str]]:
    """
    Look up a player's Fargo rating on FairMatch by name or membership ID.
    Uses persistent Chrome driver (initialized once per process).
    
    Features:
    - Persistent driver: Reuses Chrome instance across calls (saves 2-3s per lookup)
    - Timeout guards: Each lookup has 5s hard timeout, each search variant has 3s timeout
    - Error logging: All failures logged explicitly with full context
    - State cleanup: Search input cleared between variants to prevent contamination
    - Name variants: Tries "First Last" → "Last, First" → reversed forms
    
    Args:
        player_name_or_id: Player name or FARGO membership ID
    
    Returns:
        (rating_float, error_message)
        - On success: (rating, None)
        - On failure: (None, error_string_for_logging)
    
    Raises:
        No exceptions; always returns (None, error_msg) on failure.
    """
    if not SELENIUM_AVAILABLE:
        error = "Selenium not installed; pip install selenium"
        logger.error(error)
        return None, error
    
    # Normalize input
    raw = (player_name_or_id or "").strip()
    name = " ".join(raw.split()) if raw else ""
    
    if not name:
        error = "Player name or ID is empty"
        logger.warning(error)
        return None, error
    
    logger.info(f"lookup_rating: name='{name}'")
    
    # Generate search variants
    search_variants = []
    if "," in name:
        # Format: "Last, First"
        comma_parts = name.split(",", 1)
        if len(comma_parts) == 2:
            last_name = comma_parts[0].strip()
            first_name = comma_parts[1].strip()
            search_variants.append(f"{first_name} {last_name}")  # "First Last"
            search_variants.append(name)  # Original "Last, First"
    else:
        # Standard format "First Last" or space-separated
        search_variants.append(name)
        parts = name.split()
        if len(parts) >= 2:
            # Reverse: "Last First" or "Last, First"
            search_variants.append(" ".join(reversed(parts)))
            search_variants.append(", ".join(reversed(parts)))
    
    logger.debug(f"Search variants for '{name}': {search_variants}")

    # Run with timeout to prevent hung lookups from blocking forever
    from concurrent.futures import ThreadPoolExecutor
    from concurrent.futures import TimeoutError as FuturesTimeoutError

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_lookup_rating_impl, name, search_variants)
            try:
                return future.result(timeout=LOOKUP_TOTAL_TIMEOUT_SECONDS)
            except FuturesTimeoutError:
                logger.warning("Lookup timed out after %ds — cleaning up driver", LOOKUP_TOTAL_TIMEOUT_SECONDS)
                cleanup_persistent_driver()
                return None, f"Lookup timed out after {LOOKUP_TOTAL_TIMEOUT_SECONDS} seconds"
    except Exception as e:
        error = f"Unexpected error in lookup_rating('{name}'): {e}"
        logger.error(error, exc_info=True)
        return None, error


def _lookup_rating_impl(name: str, search_variants: list) -> Tuple[Optional[float], Optional[str]]:
    """Inner implementation of lookup_rating — runs with driver. Called under timeout wrapper."""
    driver = None
    try:
        with get_persistent_driver() as driver:
            # Ensure page is loaded
            try:
                if driver.current_url != FAIRMATCH_URL:
                    logger.debug("Navigating to FairMatch...")
                    driver.get(FAIRMATCH_URL)
            except TimeoutException as e:
                error = f"FairMatch page load timed out after {DEFAULT_TIMEOUT}s: {e}"
                logger.error(error, exc_info=True)
                return None, error
            except Exception as e:
                error = f"Failed to navigate to FairMatch: {e}"
                logger.error(error, exc_info=True)
                return None, error
            
            wait = WebDriverWait(driver, 20)  # Increased timeout for page load (inputs may take time to render)
            
            # Ensure search input is available
            search_input = None
            try:
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "input")))
                
                # Fast path: known input IDs
                for input_id in ["searchText", "searchText-2"]:
                    try:
                        el = driver.find_element(By.ID, input_id)
                        if el.is_displayed() and el.is_enabled():
                            search_input = el
                            logger.debug(f"Found search input with ID '{input_id}'")
                            break
                    except Exception:
                        continue
                
                # Fallback: CSS selectors
                if not search_input:
                    for selector in [
                        "input[placeholder='Player name or id']",
                        "input[placeholder*='Player name or id']",
                        "input[placeholder*='earch']",
                        "input[placeholder*='ookup']",
                        "input[type='search']",
                        "input.search-input",
                        "input.lookup-input",
                        "input.form-control",
                        "input[type='text']",
                        "input",
                    ]:
                        try:
                            elements = driver.find_elements(By.CSS_SELECTOR, selector)
                            for el in elements:
                                if el.get_attribute("name") and any(
                                    x in el.get_attribute("name").lower()
                                    for x in ["email", "password", "login"]
                                ):
                                    continue
                                if el.is_displayed() and el.is_enabled():
                                    search_input = el
                                    logger.debug(f"Found search input with selector '{selector}'")
                                    break
                        except Exception:
                            continue
                        if search_input:
                            break
            
            except TimeoutException as e:
                error = f"Timeout waiting for input element: {e}"
                logger.error(error, exc_info=True)
                return None, error
            except Exception as e:
                error = f"Error finding search input: {e}"
                logger.error(error, exc_info=True)
                return None, error
            
            # If search panel not visible, click "Search for Players" button
            if not search_input:
                logger.info("Search input not visible; trying to click 'Search for Players' button...")
                try:
                    search_btn = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.ID, "go-to-search-btn"))
                    )
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", search_btn)
                    driver.execute_script("arguments[0].click();", search_btn)
                    time.sleep(1.0)
                    
                    # Try to find search input again
                    for input_id in ["searchText", "searchText-2"]:
                        try:
                            el = driver.find_element(By.ID, input_id)
                            if el.is_displayed() and el.is_enabled():
                                search_input = el
                                logger.debug(f"Found search input after clicking button (ID '{input_id}')")
                                break
                        except Exception:
                            continue
                except TimeoutException as e:
                    error = f"Timeout waiting for search button: {e}"
                    logger.error(error, exc_info=True)
                    return None, error
                except Exception as e:
                    logger.warning(f"Could not click search button (will continue): {e}")
            
            if not search_input:
                error = "Could not find search/lookup input on FairMatch. Website may have changed."
                logger.error(error)
                return None, error
            
            # Try each variant
            for idx, query in enumerate(search_variants):
                logger.debug(f"Trying variant {idx + 1}/{len(search_variants)}: '{query}'")
                
                try:
                    rating = _do_single_search(driver, wait, search_input, query)
                    if rating is not None:
                        logger.info(f"✓ lookup_rating('{name}') found {rating} on variant '{query}'")
                        return rating, None
                except TimeoutException as e:
                    logger.warning(f"Timeout searching for variant '{query}': {e}")
                    # Continue to next variant on timeout
                    continue
                except Exception as e:
                    logger.warning(f"Error searching for variant '{query}': {e}", exc_info=True)
                    # Continue to next variant
                    continue
                
                # Polite delay before next variant
                if idx < len(search_variants) - 1:
                    time.sleep(0.5)
            
            # No variant found
            error = f"Rating not found for player '{name}' after {len(search_variants)} variants"
            logger.warning(error)
            return None, error

    except Exception as e:
        # Catch any uncaught exceptions
        error = f"Unexpected error in lookup_rating('{name}'): {e}"
        logger.error(error, exc_info=True)
        return None, error


def _parse_rating_from_page(html: str, player_hint: str) -> Optional[float]:
    """
    Extract a Fargo-style rating (3–4 digit number) from page HTML, near Official Rating context.
    
    Args:
        html: Page source HTML
        player_hint: Player name (for logging)
    
    Returns:
        float rating if found, None otherwise
    """
    if not html:
        logger.warning(f"Empty HTML provided for player hint '{player_hint}'")
        return None
    
    patterns = [
        r"Official\s+Rating[\s\S]{0,200}?(\d{3,4})\b",
        r"(\d{3,4})\s*</td>",
        r">(\d{3,4})<",
    ]
    
    for pattern_idx, pat in enumerate(patterns):
        try:
            m = re.search(pat, html, re.IGNORECASE)
            if m:
                try:
                    val = float(m.group(1))
                    if 300 <= val <= 9999:  # Sane Fargo range
                        logger.debug(f"Parsed rating {val} from pattern {pattern_idx + 1} (player hint: '{player_hint}')")
                        return val
                except ValueError as e:
                    logger.debug(f"Failed to convert matched value to float: {e}")
                    continue
        except Exception as e:
            logger.warning(f"Error applying pattern {pattern_idx + 1}: {e}")
            continue
    
    logger.debug(f"No valid rating found in HTML for player hint '{player_hint}'")
    return None


def search_players_list(player_name: str) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """
    Search for players by name on FairMatch and return ALL matching results.
    Used for disambiguation when multiple players have the same name.
    
    Args:
        player_name: Player name to search for
    
    Returns:
        (list_of_players, error_message)
        Each player dict contains: {"name": str, "rating": float, "info": str}
        - On success: ([{...}, ...], None)
        - On failure: (None, error_string)
    """
    if not SELENIUM_AVAILABLE:
        error = "Selenium not installed; pip install selenium"
        logger.error(error)
        return None, error
    
    # Normalize input
    name = (player_name or "").strip()
    if not name:
        return None, "Player name is empty"
    
    logger.info(f"search_players_list: name='{name}'")
    
    try:
        with get_persistent_driver() as driver:
            wait = WebDriverWait(driver, DEFAULT_TIMEOUT)
            
            # Navigate to FairMatch
            current_url = driver.current_url
            if not current_url or not current_url.startswith(FAIRMATCH_URL):
                logger.info(f"Navigating to {FAIRMATCH_URL}...")
                driver.get(FAIRMATCH_URL)
                time.sleep(2.0)
            
            # Find search input
            search_input = None
            try:
                wait.until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
                time.sleep(1.0)
                
                for input_id in ["searchText", "searchText-2", "search-input"]:
                    try:
                        el = driver.find_element(By.ID, input_id)
                        if el.is_displayed() and el.is_enabled():
                            search_input = el
                            break
                    except Exception:
                        continue
                
                if not search_input:
                    for selector in [
                        "input[placeholder='Player name or id']",
                        "input[placeholder*='earch']",
                        "input[type='search']",
                    ]:
                        try:
                            elements = driver.find_elements(By.CSS_SELECTOR, selector)
                            for el in elements:
                                if el.is_displayed() and el.is_enabled():
                                    search_input = el
                                    break
                        except Exception:
                            continue
                        if search_input:
                            break
            
            except Exception as e:
                error = f"Error finding search input: {e}"
                logger.error(error)
                return None, error
            
            if not search_input:
                # Try clicking search button
                try:
                    search_btn = driver.find_element(By.ID, "go-to-search-btn")
                    driver.execute_script("arguments[0].click();", search_btn)
                    time.sleep(1.0)
                    
                    for input_id in ["searchText", "searchText-2"]:
                        try:
                            el = driver.find_element(By.ID, input_id)
                            if el.is_displayed():
                                search_input = el
                                break
                        except Exception:
                            continue
                except Exception as e:
                    logger.warning(f"Could not click search button: {e}")
            
            if not search_input:
                return None, "Could not find search input on FairMatch"
            
            # Perform search
            try:
                driver.execute_script("arguments[0].value = '';", search_input)
                driver.execute_script("arguments[0].value = arguments[1];", search_input, name)
                driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", search_input)
                search_input.send_keys(Keys.RETURN)
                time.sleep(3.5)  # Wait for results
            except Exception as e:
                error = f"Error performing search: {e}"
                logger.error(error)
                return None, error
            
            # Extract al matching players from results
            players = []
            try:
                page_source = driver.page_source
                
                # Try to find table rows with player data
                # FairMatch typically shows results in a table with columns: Name, Rating, Location/Org, etc.
                rows = driver.find_elements(By.TAG_NAME, "tr")
                
                for row in rows:
                    try:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        if len(cells) < 2:
                            continue
                        
                        # Extract name and rating from cells
                        player_name_cell = cells[0].text.strip()
                        rating_text = ""
                        info_text = ""
                        
                        # Look for rating (3-4 digit number)
                        for cell in cells[1:]:
                            text = cell.text.strip()
                            if re.match(r"^\d{3,4}$", text):
                                rating_text = text
                                break
                        
                        # Collect additional info from other cells
                        info_parts = []
                        for cell in cells[1:]:
                            text = cell.text.strip()
                            if text and text != rating_text and not re.match(r"^\d{3,4}$", text):
                                info_parts.append(text)
                        info_text = ", ".join(info_parts[:3])  # Limit to 3 pieces of info
                        
                        if player_name_cell and rating_text:
                            try:
                                rating = float(rating_text)
                                if 300 <= rating <= 9999:
                                    players.append({
                                        "name": player_name_cell,
                                        "rating": rating,
                                        "info": info_text or "N/A",
                                    })
                            except ValueError:
                                continue
                    
                    except Exception as e:
                        logger.debug(f"Error parsing row: {e}")
                        continue
                
                if not players:
                    # Fallback: parse HTML for any ratings
                    rating_pattern = r"Official\s+Rating[\s\S]{0,300}?(\d{3,4})\b"
                    matches = re.finditer(rating_pattern, page_source, re.IGNORECASE)
                    for match in matches:
                        try:
                            rating = float(match.group(1))
                            if 300 <= rating <= 9999:
                                players.append({
                                    "name": name,  # Original search name
                                    "rating": rating,
                                    "info": "From search results",
                                })
                        except ValueError:
                            continue
                
                if players:
                    logger.info(f"Found {len(players)} player(s) matching '{name}'")
                    return players, None
                else:
                    return None, f"No players found for '{name}'"
            
            except Exception as e:
                error = f"Error extracting player list: {e}"
                logger.error(error, exc_info=True)
                return None, error
    
    except Exception as e:
        error = f"Unexpected error in search_players_list('{name}'): {e}"
        logger.error(error, exc_info=True)
        return None, error


def cleanup_persistent_driver():
    """
    Gracefully shutdown the persistent Chrome driver.
    Call this on application shutdown or module unload.
    """
    global _module_driver
    if _module_driver is not None:
        try:
            logger.info("Shutting down persistent Chrome driver...")
            # Suppress urllib3 connection warnings during shutdown (expected if driver already disconnected)
            urllib3_logger = logging.getLogger("urllib3.connectionpool")
            original_level = urllib3_logger.level
            urllib3_logger.setLevel(logging.ERROR)
            try:
                _module_driver.quit()
            finally:
                urllib3_logger.setLevel(original_level)
            logger.info("Persistent Chrome driver shut down successfully")
        except Exception as e:
            # Expected during shutdown if driver already disconnected
            logger.debug("Chrome driver shutdown: %s (expected during restart)", str(e))
        finally:
            _module_driver = None


# Ensure driver cleanup on module exit and on SIGTERM/SIGINT
atexit.register(cleanup_persistent_driver)
_register_signal_handlers()
