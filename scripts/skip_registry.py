#!/usr/bin/env python3
"""
skip_registry.py  â€”  valuefund.substack.com
Persistent dead-ticker tracking. Automatically skips tickers that
consistently fail yfinance lookups, saving batch time.

Key features:
- Track failure count + reason per ticker
- Auto-skip after N failures (default 3)
- Manual whitelist override
- Staleness filter: skip recently-analyzed stocks unless price moved >X%
- Full audit trail with timestamps
"""
import json, os, re, sqlite3, threading
_reg_lock = threading.Lock()
from datetime import datetime, timedelta

REGISTRY_PATH = r"D:\StockAnalysis\config\skip_registry.json"
DB_PATH       = r"D:\StockAnalysis\database\stocks.db"
CONFIG_PATH   = r"D:\StockAnalysis\config\smart_config.json"

# â”€â”€ Load config â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _cfg():
    try:
        with open(CONFIG_PATH) as f: c = json.load(f)
        return c.get('analysis', {})
    except:
        return {}

SKIP_AFTER = _cfg().get('skip_after_n_failures', 3)
STALE_DAYS = _cfg().get('staleness_days', 14)
STALE_MOVE = _cfg().get('staleness_price_move_pct', 10.0)


# â”€â”€ Registry I/O â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_file_lock = threading.Lock()

# ── In-process registry cache ────────────────────────────────────────────────
# WHY: should_skip() re-opened and re-parsed the whole ~940 KB registry on
# EVERY call.  build_queue() calls it once per candidate ticker (~12,300), at
# ~13 ms each, so ~3 minutes of pure CPU burned before any real work started.
#
# The cache stores the PARSED REGISTRY, not the skip decision.  Every call
# still evaluates the same whitelist / failure-count logic against the same
# data, so queue composition is bit-for-bit identical to the uncached path.
# (Caching the decision itself is what could silently drop valid tickers, so
# deliberately not doing that.)
#
# Invalidation: (mtime_ns, size) of the file.  An external edit is picked up
# on the next call; _save() refreshes the cache in-process so a write does
# not force a 940 KB re-parse on the very next read.
_cache_lock  = threading.Lock()
_cache_stamp = None      # (st_mtime_ns, st_size) the cached copy came from
_cache_data  = None      # parsed registry dict


def _stat_stamp():
    try:
        st = os.stat(REGISTRY_PATH)
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def _read_from_disk():
    try:
        if os.path.exists(REGISTRY_PATH):
            with _file_lock:
                with open(REGISTRY_PATH) as f:
                    return json.load(f)
    except (json.JSONDecodeError, OSError):
        pass  # corrupted file — return defaults
    return {"skipped": {}, "whitelist": [], "stats": {"total_saved_skips": 0}}


def _load(use_cache: bool = True):
    """Return the parsed registry. Cached unless the file changed on disk."""
    global _cache_stamp, _cache_data
    if not use_cache:
        return _read_from_disk()

    stamp = _stat_stamp()
    with _cache_lock:
        if _cache_data is not None and _cache_stamp == stamp:
            return _cache_data

    data = _read_from_disk()
    with _cache_lock:
        _cache_stamp = stamp
        _cache_data  = data
    return data


def cache_clear():
    """Drop the in-process cache (used by verification / long-lived daemons)."""
    global _cache_stamp, _cache_data
    with _cache_lock:
        _cache_stamp = None
        _cache_data  = None


def _save(reg):
    global _cache_stamp, _cache_data
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    with _file_lock:
        tmp = REGISTRY_PATH + ".tmp"
        with open(tmp, 'w') as f:
            json.dump(reg, f, indent=2)
        os.replace(tmp, REGISTRY_PATH)
    # The object we just wrote IS the current on-disk state — adopt it as the
    # cache instead of forcing the next reader to re-parse 940 KB.
    with _cache_lock:
        _cache_stamp = _stat_stamp()
        _cache_data  = reg


# â”€â”€ Public API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# __VF_SKIPREG_V2__ ─ verdict classification + decay window ───────────────────
DEAD_RECHECK_DAYS   = _cfg().get('dead_recheck_days', 90)
FILTER_RECHECK_DAYS = _cfg().get('filter_recheck_days', 30)
RECHECK_MAX_PER_RUN = _cfg().get('recheck_max_per_run', 100)

FILTER_PREFIX = "FILTER: "

# Legacy reason strings written before the FILTER: prefix existed.
_LEGACY_FILTER_RX = re.compile(r'^(too large|too small)|price unavailable:\s*[0-9]', re.I)
_TRANSIENT_RX = re.compile(
    r'curl:|connection timed out|connection closed|connection reset|max retries|'
    r'timed out|\bssl\b|\b429\b|rate limit|too many request|winerror|'
    r'access is denied|permission denied|temporarily unavailable|'
    r'remote end closed|name resolution', re.I)

# Tickers granted a recheck this process. should_skip() is called twice per
# ticker (build_queue, then analyze_one) -- a granted ticker must stay granted
# or the second call would re-skip it after the budget is spent.
_recheck_granted = set()
_recheck_lock = threading.Lock()


def is_filter_verdict(reason: str) -> bool:
    r = (reason or '').strip()
    return r.startswith(FILTER_PREFIX) or bool(_LEGACY_FILTER_RX.search(r))


def is_transient(reason: str) -> bool:
    return bool(_TRANSIENT_RX.search(reason or ''))


def _days_since(datestr) -> float:
    try:
        return (datetime.now() - datetime.strptime(str(datestr)[:10], '%Y-%m-%d')).days
    except Exception:
        return 10**6   # unparseable -> treat as ancient -> eligible for recheck


def reset_recheck_budget():
    with _recheck_lock:
        _recheck_granted.clear()


def rechecks_granted() -> int:
    with _recheck_lock:
        return len(_recheck_granted)


def _try_grant_recheck(ticker: str) -> bool:
    with _recheck_lock:
        if ticker in _recheck_granted:
            return True
        if len(_recheck_granted) >= RECHECK_MAX_PER_RUN:
            return False
        _recheck_granted.add(ticker)
        return True


def should_skip(ticker: str) -> tuple[bool, str]:
    """
    Returns (skip: bool, reason: str).  True = don't analyze right now.

    Three entry kinds live in the registry:
      * filtered=True          -> screening verdict (too big / too cheap).
                                  Re-evaluated every FILTER_RECHECK_DAYS.
      * failures >= SKIP_AFTER -> genuine data failures ("dead").
                                  Re-tried once every DEAD_RECHECK_DAYS.
      * 0 < failures < SKIP_AFTER -> warned, still analyzed normally.
    Rechecks are capped at RECHECK_MAX_PER_RUN per process.
    """
    reg = _load()

    if ticker in reg.get('whitelist', []):
        return False, "whitelisted"

    info = reg.get('skipped', {}).get(ticker)
    if not info:
        return False, ""

    with _recheck_lock:
        if ticker in _recheck_granted:
            return False, "recheck"

    age = _days_since(info.get('last_seen') or info.get('first_seen'))

    if info.get('filtered'):
        if age >= FILTER_RECHECK_DAYS and _try_grant_recheck(ticker):
            return False, f"recheck-filter ({age:.0f}d since verdict)"
        return True, f"filtered ({info.get('last_reason','?')[:50]}; " \
                     f"recheck in {max(0, FILTER_RECHECK_DAYS-age):.0f}d)"

    if info.get('failures', 0) >= SKIP_AFTER:
        if age >= DEAD_RECHECK_DAYS and _try_grant_recheck(ticker):
            return False, f"recheck-dead ({age:.0f}d since last failure)"
        return True, f"dead ticker ({info['failures']} failures: " \
                     f"{info.get('last_reason','?')}; recheck in " \
                     f"{max(0, DEAD_RECHECK_DAYS-age):.0f}d)"

    return False, ""


def record_filtered(ticker: str, reason: str):
    """A SCREENING verdict (too big / too cheap). Never counts toward dead."""
    with _reg_lock:
        reg = _load()
        skipped = reg.setdefault('skipped', {})
        entry = skipped.get(ticker) or {'first_seen': datetime.now().isoformat()[:10]}
        entry['filtered']    = True
        entry['failures']    = 0
        entry.pop('auto_skipped', None)
        entry['last_reason'] = reason[:120]
        entry['last_seen']   = datetime.now().isoformat()[:10]
        skipped[ticker] = entry
        _save(reg)


def record_transient(ticker: str, reason: str):
    """Network / rate-limit / local-IO fault. Logged, never counted."""
    with _reg_lock:
        reg = _load()
        skipped = reg.setdefault('skipped', {})
        entry = skipped.get(ticker)
        if entry is None:
            # Don't create an entry for a ticker we know nothing bad about.
            return
        entry['transient_count'] = entry.get('transient_count', 0) + 1
        entry['last_transient']  = reason[:120]
        _save(reg)
# ── end __VF_SKIPREG_V2__ ─────────────────────────────────────────────────────


def should_skip_stale(ticker: str, current_price: float = None) -> tuple[bool, str]:
    """
    Returns (skip: bool, reason: str).
    Skip if stock was analyzed recently AND price hasn't moved much.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT analysis_date, current_price FROM analyzed_stocks WHERE ticker=?",
            (ticker,)
        ).fetchone()
        conn.close()

        if not row: return False, ""
        analysis_date_str, old_price = row

        # Parse date
        analysis_date = datetime.strptime(analysis_date_str, '%Y-%m-%d')
        days_old = (datetime.now() - analysis_date).days

        if days_old < STALE_DAYS:
            # Check if price has moved significantly
            if current_price and old_price and old_price > 0:
                move_pct = abs(current_price - old_price) / old_price * 100
                if move_pct >= STALE_MOVE:
                    return False, f"price moved {move_pct:.1f}% â€” re-analyzing"
            return True, f"fresh ({days_old}d old, re-analyzes after {STALE_DAYS}d)"
    except:
        pass
    return False, ""


# NOTE: the mutators below now hold _reg_lock for the whole read-modify-write.
# Since _load() returns the SHARED cached dict, two worker threads mutating it
# concurrently would otherwise interleave. (The old code copy-on-read, so it
# merely lost updates instead of corrupting them — this is strictly safer.)
def record_failure(ticker: str, reason: str):
    """Record a failed yfinance fetch. After SKIP_AFTER failures, ticker is auto-skipped."""
    with _reg_lock:
        reg = _load()
        skipped = reg.setdefault('skipped', {})
        entry = skipped.setdefault(ticker, {'failures': 0, 'first_seen': datetime.now().isoformat()[:10]})
        if entry.get('filtered'):
            # Was a screening verdict; now a genuine failure. Start counting.
            entry['filtered'] = False
            entry['failures'] = 0
        entry['failures'] = entry.get('failures', 0) + 1
        entry['last_reason'] = reason[:120]
        entry['last_seen'] = datetime.now().isoformat()[:10]
        if entry['failures'] >= SKIP_AFTER:
            entry['auto_skipped'] = True
        _save(reg)


def record_success(ticker: str):
    """Reset failure count on successful fetch."""
    with _reg_lock:
        reg = _load()
        if ticker in reg.get('skipped', {}):
            del reg['skipped'][ticker]
            _save(reg)


def add_to_whitelist(ticker: str):
    """Force-include a ticker regardless of failure count."""
    with _reg_lock:
        reg = _load()
        if ticker not in reg.get('whitelist', []):
            reg.setdefault('whitelist', []).append(ticker)
            _save(reg)


def get_stats() -> dict:
    """Return summary stats about the skip registry."""
    reg = _load()
    skipped = reg.get('skipped', {})
    filtered = [t for t, v in skipped.items() if v.get('filtered')]
    dead = [t for t, v in skipped.items()
            if not v.get('filtered') and v.get('failures', 0) >= SKIP_AFTER]
    warned = [t for t, v in skipped.items() if 0 < v.get('failures', 0) < SKIP_AFTER]
    return {
        'dead_tickers': len(dead),
        'filtered_tickers': len(filtered),
        'warned_tickers': len(warned),
        'whitelisted': len(reg.get('whitelist', [])),
        'top_dead': dead[:10],
        'top_warned': [(t, skipped[t]['failures']) for t in warned[:5]],
    }


def print_report():
    stats = get_stats()
    print(f"Skip Registry Report:")
    print(f"  Dead (auto-skip): {stats['dead_tickers']} tickers")
    print(f"  Filtered (screen): {stats['filtered_tickers']} tickers")
    print(f"  Warned (1-2 fails): {stats['warned_tickers']} tickers")
    print(f"  Whitelisted: {stats['whitelisted']} tickers")
    if stats['top_dead']:
        print(f"  Top dead: {', '.join(stats['top_dead'][:8])}")


if __name__ == '__main__':
    print_report()
