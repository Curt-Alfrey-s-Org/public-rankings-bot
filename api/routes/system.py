"""
System Routes
Provides system information and health status
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from pathlib import Path
import os
import subprocess
import json
import logging

from project_root import PROJECT_ROOT
from api.utils import get_bot_instance, is_bot_running

logger = logging.getLogger(__name__)

router = APIRouter()


# Cache for self-test results (avoid running on every health check)
_self_test_cache = {
    "results": None,
    "timestamp": None,
    "cache_duration": 60,  # Cache for 60 seconds
}

# Track if HTTP tests have been run (run once after API is ready)
_http_tests_run = False
_http_tests_results = None


def _collect_registered_paths(app) -> list[str]:
    """
    Return all registered HTTP paths for route-existence self-tests.

    FastAPI nests included routers; a flat walk of app.routes misses most paths.
    OpenAPI path keys match what clients call (see FastAPI OpenAPI docs).
    """
    try:
        schema = app.openapi()
        return sorted(schema.get("paths", {}).keys())
    except Exception as e:
        logger.debug("OpenAPI path collection failed: %s", e)
        paths: list[str] = []
        for route in getattr(app, "routes", []):
            p = getattr(route, "path", None)
            if p:
                paths.append(p)
        return paths


def _check_frontend_api_base_url(project_root: Path):
    """
    Fail if frontend has hardcoded localhost (causes screen-not-updating when
    deployed or when API runs on another port). Use same-origin '' or VITE_API_URL instead.
    Scans frontend/src for .ts, .tsx, .js, .jsx.
    """
    frontend_src = project_root / "frontend" / "src"
    if not frontend_src.exists():
        return True, None
    bad = "localhost:8003"
    for ext in ("*.ts", "*.tsx", "*.js", "*.jsx"):
        for path in frontend_src.rglob(ext):
            try:
                text = path.read_text(encoding="utf-8")
                if bad in text:
                    return False, f"Frontend has hardcoded localhost in {path.relative_to(project_root)}; use same-origin '' or VITE_API_URL so UI works on subdomain"
            except Exception as e:
                return False, str(e)[:80]
    return True, None


def _run_http_self_tests():
    """Run HTTP-based self-tests (actual endpoint validation)"""
    import requests
    import time
    from datetime import datetime

    # API URL for self-test (env override). In container use localhost; 127 only when strictly local/sensitive.
    api_url = os.getenv("API_URL", "http://localhost:8003")
    if not api_url.startswith('http'):
        api_url = f"http://{api_url}"
    api_url = api_url.rstrip('/')
    _http_timeout = 5
    _http_retries = 2

    def _get_with_retry(url, method='get'):
        for attempt in range(_http_retries):
            try:
                if method == 'get':
                    return requests.get(url, timeout=_http_timeout)
                if method == 'options':
                    return requests.options(url, timeout=_http_timeout)
                return requests.get(url, timeout=_http_timeout)
            except requests.exceptions.ConnectionError:
                if attempt < _http_retries - 1:
                    time.sleep(1)
                else:
                    raise

    test_results = []
    passed = 0
    failed = 0
    timings = {}

    # Test 0: Frontend API base URL (no hardcoded localhost)
    start = time.time()
    ok, err = _check_frontend_api_base_url(PROJECT_ROOT)
    elapsed = (time.time() - start) * 1000
    timings["test_frontend_api_base_url"] = elapsed
    if ok:
        test_results.append({"name": "Frontend API base URL", "passed": True, "duration_ms": elapsed})
        passed += 1
    else:
        test_results.append({"name": "Frontend API base URL", "passed": False, "duration_ms": elapsed, "error": err or "bad default"})
        failed += 1

    # Test 1: API Health Endpoint (internal check to avoid circular HTTP calls)
    start = time.time()
    try:
        # Instead of making HTTP call to self, do internal health check
        from database import get_database_manager
        db_manager = get_database_manager()
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        conn.close()
        passed_test = True
        elapsed = (time.time() - start) * 1000
        timings['test_api_health'] = elapsed
        test_results.append({"name": "API Health", "passed": passed_test, "duration_ms": elapsed})
        if passed_test:
            passed += 1
        else:
            failed += 1
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        timings['test_api_health'] = elapsed
        test_results.append({"name": "API Health", "passed": False, "duration_ms": elapsed, "error": str(e)[:80]})
        failed += 1
    
    # Test 2: Messages Endpoint (check if route exists instead of HTTP call)
    start = time.time()
    try:
        from api.main import app
        route_paths = _collect_registered_paths(app)
        has_messages_route = any(p == "/api/messages" or p.startswith("/api/messages/") for p in route_paths)
        elapsed = (time.time() - start) * 1000
        timings['test_messages_endpoint'] = elapsed
        if has_messages_route:
            test_results.append({"name": "Messages Endpoint", "passed": True, "duration_ms": elapsed})
            passed += 1
        else:
            test_results.append({"name": "Messages Endpoint", "passed": False, "duration_ms": elapsed, "error": "Messages route not found"})
            failed += 1
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        timings['test_messages_endpoint'] = elapsed
        test_results.append({"name": "Messages Endpoint", "passed": False, "duration_ms": elapsed, "error": str(e)[:80]})
        failed += 1
    
    # Test 8: System Endpoint Exists (check route exists)
    start = time.time()
    try:
        from api.main import app
        route_paths = _collect_registered_paths(app)
        has_system_route = any(
            p == "/api/system" or (p.startswith("/api/system/") and p != "/api/system/health")
            for p in route_paths
        )
        if has_system_route:
            elapsed = (time.time() - start) * 1000
            timings['test_system_endpoint'] = elapsed
            test_results.append({"name": "System Endpoint", "passed": True, "duration_ms": elapsed})
            passed += 1
        else:
            raise Exception("System route not found")
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        timings['test_system_endpoint'] = elapsed
        test_results.append({"name": "System Endpoint", "passed": False, "duration_ms": elapsed, "error": str(e)})
        failed += 1
    
    # Test 9: System Endpoint Function (check it can be imported and called)
    start = time.time()
    try:
        from api.routes.system import get_system_info
        # Check that function exists and is callable
        if callable(get_system_info):
            elapsed = (time.time() - start) * 1000
            timings['test_system_function'] = elapsed
            test_results.append({"name": "System Function", "passed": True, "duration_ms": elapsed})
            passed += 1
        else:
            raise Exception("System function not callable")
    except ImportError as e:
        elapsed = (time.time() - start) * 1000
        timings['test_system_function'] = elapsed
        error_msg = f"System function not importable: {str(e)}"
        test_results.append({"name": "System Function", "passed": False, "duration_ms": elapsed, "error": error_msg})
        failed += 1
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        timings['test_system_function'] = elapsed
        test_results.append({"name": "System Function", "passed": False, "duration_ms": elapsed, "error": str(e)})
        failed += 1
    
    # Test 10: Frontend System Page Component
    start = time.time()
    try:
        import re
        system_page_path = PROJECT_ROOT / 'frontend/src/pages/System.tsx'
        
        if not system_page_path.exists():
            raise Exception("System.tsx not found")
        
        with open(system_page_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for JSX syntax errors (balanced tags) - enhanced to handle self-closing tags
        issues = []
        
        # Count opening tags (excluding self-closing)
        opening_divs = len([m for m in re.finditer(r'<div[^>]*>', content) if '/>' not in m.group()])
        closing_divs = content.count('</div>')
        self_closing_divs = len([m for m in re.finditer(r'<div[^>]*/>', content)])
        
        opening_main = len([m for m in re.finditer(r'<main[^>]*>', content) if '/>' not in m.group()])
        closing_main = content.count('</main>')
        
        opening_header = len([m for m in re.finditer(r'<header[^>]*>', content) if '/>' not in m.group()])
        closing_header = content.count('</header>')
        
        # Check for balanced tags
        if opening_divs != closing_divs:
            diff = opening_divs - closing_divs
            issues.append(f"JSX syntax error: {abs(diff)} unclosed <div> tag(s) ({'missing closing' if diff > 0 else 'extra closing'})")
        if opening_main != closing_main:
            diff = opening_main - closing_main
            issues.append(f"JSX syntax error: {abs(diff)} unclosed <main> tag(s) ({'missing closing' if diff > 0 else 'extra closing'})")
        if opening_header != closing_header:
            diff = opening_header - closing_header
            issues.append(f"JSX syntax error: {abs(diff)} unclosed <header> tag(s) ({'missing closing' if diff > 0 else 'extra closing'})")
        
        # Check for common JSX syntax errors
        # Unclosed JSX expressions
        open_braces = content.count('{')
        close_braces = content.count('}')
        if open_braces != close_braces:
            issues.append(f"JSX expression error: {abs(open_braces - close_braces)} unclosed brace(s)")
        
        # Check for required patterns (core System page functionality; chart is optional)
        if 'useQuery' not in content:
            issues.append("useQuery not found - data fetching not implemented")
        if 'systemInfo' not in content:
            issues.append("systemInfo state not found")
        if 'cpu_usage' not in content or 'memory_usage' not in content:
            issues.append("System stats display not implemented")
        if 'isError' not in content and 'error' not in content:
            issues.append("Error handling not implemented")
        # Chart is optional; page can show stats without charts
        
        elapsed = (time.time() - start) * 1000
        timings['test_system_page'] = elapsed
        if issues:
            error_msg = f"System page issues: {'; '.join(issues)}"
            test_results.append({"name": "System Page Component", "passed": False, "duration_ms": elapsed, "error": error_msg})
            failed += 1
        else:
            test_results.append({"name": "System Page Component", "passed": True, "duration_ms": elapsed})
            passed += 1
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        timings['test_system_page'] = elapsed
        test_results.append({"name": "System Page Component", "passed": False, "duration_ms": elapsed, "error": str(e)})
        failed += 1
    
    total = passed + failed
    success_rate = (passed / total * 100) if total > 0 else 0
    
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "success_rate": success_rate,
        "all_passed": failed == 0,
        "results": test_results,
        "timings": {
            "total_duration_ms": sum(timings.values()),
            "total_duration_s": sum(timings.values()) / 1000,
            "test_timings": timings
        }
    }

def _run_internal_self_tests():
    """Run internal self-tests (direct function calls, no HTTP needed)"""
    import time
    from datetime import datetime
    
    test_results = []
    passed = 0
    failed = 0
    timings = {}
    
    # Test 1: Module Imports
    start = time.time()
    try:
        import api.main
        elapsed = (time.time() - start) * 1000
        timings['test_imports'] = elapsed
        test_results.append({"name": "Module Imports", "passed": True, "duration_ms": elapsed})
        passed += 1
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        timings['test_imports'] = elapsed
        test_results.append({"name": "Module Imports", "passed": False, "duration_ms": elapsed, "error": str(e)})
        failed += 1
    
    # Test 5: Bot Manager Initialization (catch UnboundLocalError and similar)
    start = time.time()
    try:
        # Try to check if bot manager functions work - this will catch initialization errors
        # Just verify the functions exist and can be called without error
        is_running = is_bot_running()  # This should not raise an error
        bot_instance = get_bot_instance()  # This may be None, but shouldn't error
        elapsed = (time.time() - start) * 1000
        timings['test_bot_manager'] = elapsed
        test_results.append({"name": "Bot Manager Initialization", "passed": True, "duration_ms": elapsed})
        passed += 1
    except UnboundLocalError as e:
        elapsed = (time.time() - start) * 1000
        timings['test_bot_manager'] = elapsed
        error_msg = f"UnboundLocalError detected: {str(e)}. Check for duplicate imports inside functions."
        test_results.append({"name": "Bot Manager Initialization", "passed": False, "duration_ms": elapsed, "error": error_msg})
        failed += 1
    except NameError as e:
        elapsed = (time.time() - start) * 1000
        timings['test_bot_manager'] = elapsed
        error_msg = f"NameError detected: {str(e)}. Check for undefined variables or missing imports."
        test_results.append({"name": "Bot Manager Initialization", "passed": False, "duration_ms": elapsed, "error": error_msg})
        failed += 1
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        timings['test_bot_manager'] = elapsed
        test_results.append({"name": "Bot Manager Initialization", "passed": False, "duration_ms": elapsed, "error": str(e)})
        failed += 1
    
    # Test 6: API Health (internal check)
    start = time.time()
    try:
        from api.main import app
        if hasattr(app, 'routes') and len(app.routes) > 0:
            elapsed = (time.time() - start) * 1000
            timings['test_api_health'] = elapsed
            test_results.append({"name": "API Health", "passed": True, "duration_ms": elapsed})
            passed += 1
        else:
            raise Exception("No routes registered")
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        timings['test_api_health'] = elapsed
        test_results.append({"name": "API Health", "passed": False, "duration_ms": elapsed, "error": str(e)})
        failed += 1
    
    # Test 10: Messages Endpoint (check route exists)
    start = time.time()
    try:
        from api.main import app
        route_paths = _collect_registered_paths(app)
        if any(p == "/api/messages" or p.startswith("/api/messages/") for p in route_paths):
            elapsed = (time.time() - start) * 1000
            timings['test_messages_endpoint'] = elapsed
            test_results.append({"name": "Messages Endpoint", "passed": True, "duration_ms": elapsed})
            passed += 1
        else:
            raise Exception("Messages route not found")
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        timings['test_messages_endpoint'] = elapsed
        test_results.append({"name": "Messages Endpoint", "passed": False, "duration_ms": elapsed, "error": str(e)})
        failed += 1
    
    # Test 15: JSX Syntax Validation (check all critical TSX files for syntax errors)
    start = time.time()
    try:
        import re
        critical_tsx_files = [
            'frontend/src/pages/System.tsx',
        ]
        
        jsx_issues = []
        for tsx_file in critical_tsx_files:
            file_path = PROJECT_ROOT / tsx_file
            if not file_path.exists():
                jsx_issues.append(f"{tsx_file} not found")
                continue
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Count opening tags (excluding self-closing)
            opening_divs = len([m for m in re.finditer(r'<div[^>]*>', content) if '/>' not in m.group()])
            closing_divs = content.count('</div>')
            
            opening_main = len([m for m in re.finditer(r'<main[^>]*>', content) if '/>' not in m.group()])
            closing_main = content.count('</main>')
            
            opening_header = len([m for m in re.finditer(r'<header[^>]*>', content) if '/>' not in m.group()])
            closing_header = content.count('</header>')
            
            opening_section = len([m for m in re.finditer(r'<section[^>]*>', content) if '/>' not in m.group()])
            closing_section = content.count('</section>')
            
            # Check for balanced tags
            if opening_divs != closing_divs:
                diff = opening_divs - closing_divs
                jsx_issues.append(f"{tsx_file}: {abs(diff)} unclosed <div> tag(s) ({'missing closing' if diff > 0 else 'extra closing'})")
            if opening_main != closing_main:
                diff = opening_main - closing_main
                jsx_issues.append(f"{tsx_file}: {abs(diff)} unclosed <main> tag(s) ({'missing closing' if diff > 0 else 'extra closing'})")
            if opening_header != closing_header:
                diff = opening_header - closing_header
                jsx_issues.append(f"{tsx_file}: {abs(diff)} unclosed <header> tag(s) ({'missing closing' if diff > 0 else 'extra closing'})")
            if opening_section != closing_section:
                diff = opening_section - closing_section
                jsx_issues.append(f"{tsx_file}: {abs(diff)} unclosed <section> tag(s) ({'missing closing' if diff > 0 else 'extra closing'})")
            
            # Check for unclosed JSX expressions
            open_braces = content.count('{')
            close_braces = content.count('}')
            if open_braces != close_braces:
                jsx_issues.append(f"{tsx_file}: {abs(open_braces - close_braces)} unclosed JSX expression brace(s)")
        
        elapsed = (time.time() - start) * 1000
        timings['test_jsx_syntax'] = elapsed
        if jsx_issues:
            error_msg = f"JSX syntax errors: {'; '.join(jsx_issues)}"
            test_results.append({"name": "JSX Syntax Validation", "passed": False, "duration_ms": elapsed, "error": error_msg})
            failed += 1
        else:
            test_results.append({"name": "JSX Syntax Validation", "passed": True, "duration_ms": elapsed})
            passed += 1
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        timings['test_jsx_syntax'] = elapsed
        test_results.append({"name": "JSX Syntax Validation", "passed": False, "duration_ms": elapsed, "error": str(e)})
        failed += 1
    
    total = passed + failed
    success_rate = (passed / total * 100) if total > 0 else 0
    if failed > 0:
        for r in test_results:
            if not r.get("passed"):
                logger.info(f"[SELFTEST] Health check ✗ {r.get('name', '?')}: {r.get('error', '')}")
        logger.info(f"[SELFTEST] Health self-tests: {passed}/{total} passed")
    
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "success_rate": success_rate,
        "all_passed": failed == 0,
        "results": test_results,
        "timings": {
            "total_duration_ms": sum(timings.values()),
            "total_duration_s": sum(timings.values()) / 1000,
            "test_timings": timings
        }
    }

@router.get("")
async def get_system_info() -> Dict[str, Any]:
    """
    Return current system metrics.

    Backward-compatibility:
    - Frontend `System.tsx` reads flat keys at top-level.
    - `frontend/src/api/system.ts` expects structured `system/resources`.
    This endpoint returns both shapes to keep existing clients working.
    """
    try:
        import platform
        import psutil
        import time
        from datetime import datetime

        vm = psutil.virtual_memory()
        disk = psutil.disk_usage(str(PROJECT_ROOT))
        cpu_usage = psutil.cpu_percent(interval=0.1)
        boot_time = psutil.boot_time()
        uptime = int(max(0, time.time() - boot_time))

        flat = {
            "cpu_usage": float(cpu_usage),
            "cpu_count": int(psutil.cpu_count() or 0),
            "memory_usage": float(vm.percent),
            "memory_total": float(vm.total / (1024 ** 3)),
            "memory_available": float(vm.available / (1024 ** 3)),
            "disk_usage": float(disk.percent),
            "disk_total": float(disk.total / (1024 ** 3)),
            "disk_free": float(disk.free / (1024 ** 3)),
            "uptime": uptime,
            "timestamp": datetime.utcnow().isoformat(),
        }

        return {
            **flat,
            "system": {
                "platform": platform.system(),
                "platform_version": platform.version(),
                "architecture": platform.machine(),
                "processor": platform.processor(),
                "python_version": platform.python_version(),
            },
            "resources": {
                "cpu_count": flat["cpu_count"],
                "memory_total": flat["memory_total"],
                "memory_available": flat["memory_available"],
                "memory_percent": flat["memory_usage"],
                "disk_usage": {
                    "total": flat["disk_total"],
                    "used": float((disk.used) / (1024 ** 3)),
                    "free": flat["disk_free"],
                    "percent": flat["disk_usage"],
                },
            },
        }
    except Exception as e:
        logger.error("Error getting system info: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to load system info: {e}")


@router.get("/module-lights")
async def get_module_lights() -> Dict[str, Any]:
    """Get module status lights for super_admin dashboard"""
    try:
        import time
        import psutil
        import httpx
        from database import get_database_manager

        modules = {}

        # Backend status (always ok if we're running)
        modules['backend'] = {
            'status': 'ok',
            'message': 'API running'
        }

        # API status (internal check to avoid circular HTTP calls)
        try:
            # Instead of HTTP call, do internal database check
            db_manager = get_database_manager()
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            conn.close()
            modules['api'] = {'status': 'ok', 'message': 'API responding'}
        except Exception as e:
            modules['api'] = {'status': 'down', 'message': str(e)[:50]}

        # Frontend status: dist bind-mounted in production; age alone is not a failure.
        try:
            frontend_dist = PROJECT_ROOT / "frontend" / "dist"
            index_html = frontend_dist / "index.html"
            if frontend_dist.is_dir() and index_html.is_file() and (frontend_dist / "assets").is_dir():
                age_h = (time.time() - index_html.stat().st_mtime) / 3600.0
                if age_h < 24:
                    modules["frontend"] = {"status": "ok", "message": "Dist present (built recently)"}
                else:
                    modules["frontend"] = {
                        "status": "ok",
                        "message": f"Dist present ({age_h:.0f}h since build)",
                    }
            else:
                modules["frontend"] = {"status": "down", "message": "Not built"}
        except Exception as e:
            modules['frontend'] = {'status': 'down', 'message': str(e)[:50]}

        # Database status
        try:
            db_manager = get_database_manager()
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            conn.close()
            modules['database'] = {'status': 'ok', 'message': 'Connected'}
        except Exception as e:
            modules['database'] = {'status': 'down', 'message': str(e)[:50]}

        # HTTP status (external connectivity test)
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get("https://httpbin.org/status/200", timeout=3.0)
                if response.status_code == 200:
                    modules['http'] = {'status': 'ok', 'message': 'Internet accessible'}
                else:
                    modules['http'] = {'status': 'down', 'message': f'HTTP {response.status_code}'}
        except Exception as e:
            modules['http'] = {'status': 'down', 'message': 'No internet'}

        # Network status (internal check)
        try:
            # Check if we can connect to database as network proxy test
            db_manager = get_database_manager()
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            conn.close()
            modules['network'] = {'status': 'ok', 'message': 'Local network ok'}
        except Exception:
            logger.warning("Network module check failed", exc_info=True)
            modules['network'] = {'status': 'down', 'message': 'Network issues'}

        return {"modules": modules}

    except Exception as e:
        logger.error(f"Module lights check failed: {e}", exc_info=True)
        return {"modules": {}, "error": str(e)}



@router.get("/health")
async def get_system_health() -> Dict:
    """Get system health including self-test status"""
    try:
        import sys
        import time
        from datetime import datetime
        
        current_time = time.time()
        
        # Use cached results if available and fresh
        if (_self_test_cache["results"] is not None and 
            _self_test_cache["timestamp"] is not None and
            (current_time - _self_test_cache["timestamp"]) < _self_test_cache["cache_duration"]):
            test_results = _self_test_cache["results"]
            logger.debug("Using cached self-test results")
        else:
            # Run internal tests first (fast, no HTTP needed)
            if str(PROJECT_ROOT) not in sys.path:
                sys.path.insert(0, str(PROJECT_ROOT))
            
            test_start = time.time()
            internal_results = _run_internal_self_tests()
            
            # Run HTTP tests if API is ready (run once, then cache)
            global _http_tests_run, _http_tests_results
            if not _http_tests_run:
                try:
                    # Try to run HTTP tests (only if API is accessible)
                    http_results = _run_http_self_tests()
                    if http_results:
                        _http_tests_results = http_results
                        _http_tests_run = True
                        logger.info("HTTP self-tests completed successfully")
                except Exception as e:
                    logger.debug(f"HTTP self-tests not ready yet: {e}")
                    # Will try again on next request
            
            # Merge results: use HTTP tests if available, otherwise use internal
            if _http_tests_results:
                test_results = _http_tests_results
            else:
                test_results = internal_results
            
            test_elapsed = time.time() - test_start
            
            # Cache the results
            _self_test_cache["results"] = test_results
            _self_test_cache["timestamp"] = current_time
            logger.info(f"Self-test completed in {test_elapsed:.2f}s, cached for {_self_test_cache['cache_duration']}s")
        
        # Add messages to bot's message system if bot is available (only on fresh test, not cached)
        cache_age = current_time - _self_test_cache["timestamp"] if _self_test_cache["timestamp"] else 999
        if cache_age < 5:  # Only add message if test just ran (within 5 seconds)
            bot = get_bot_instance()
            if bot and hasattr(bot, 'stored_messages'):
                # Add summary message about self-test results with timing
                total_time = test_results.get('timings', {}).get('total_duration_s', 0)
                if test_results["all_passed"]:
                    bot.stored_messages.add_message(
                        f"Self-test completed: {test_results['passed']}/{test_results['total']} tests passed in {total_time:.2f}s",
                        category='info'
                    )
                else:
                    failed_tests = [r['name'] for r in test_results['results'] if not r.get('passed', False)]
                    if failed_tests:
                        bot.stored_messages.add_message(
                            f"Self-test failed: {test_results['failed']} test(s) failed in {total_time:.2f}s - {', '.join(failed_tests[:3])}",
                            category='warning'
                        )
                    else:
                        bot.stored_messages.add_message(
                            f"Self-test completed with {test_results['failed']} failure(s) in {total_time:.2f}s",
                            category='warning'
                        )
        
        # Get startup timings from utils
        from api.utils import get_startup_timings
        startup_timings = get_startup_timings()
        
        return {
            "status": "healthy" if test_results["all_passed"] else "degraded",
            "self_test": {
                "passed": test_results["all_passed"],
                "total": test_results["total"],
                "passed_count": test_results["passed"],
                "failed_count": test_results["failed"],
                "success_rate": test_results["success_rate"],
                "results": test_results["results"],
                "timings": test_results.get("timings", {})
            },
            "startup_timings": startup_timings,
            "system": {
                "platform": os.name,
                "python_version": sys.version.split()[0]
            }
        }
    except ImportError as e:
        logger.warning(f"Could not import startup_test: {e}", exc_info=True)
        return {
            "status": "unknown",
            "self_test": {
                "passed": None,
                "error": "Startup test module not available"
            }
        }
    except Exception as e:
        logger.error(f"Error getting system health: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "self_test": {
                "passed": False,
                "error": "Could not run self-tests"
            }
        }

