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
import json, os, sqlite3, threading
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
def _load():
    if os.path.exists(REGISTRY_PATH):
        with open(REGISTRY_PATH) as f:
            return json.load(f)
    return {"skipped": {}, "whitelist": [], "stats": {"total_saved_skips": 0}}

def _save(reg):
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    with open(REGISTRY_PATH, 'w') as f:
        json.dump(reg, f, indent=2)


# â”€â”€ Public API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def should_skip(ticker: str) -> tuple[bool, str]:
    """
    Returns (skip: bool, reason: str).
    True = don't analyze this ticker right now.
    """
    reg = _load()

    # Whitelist override â€” always analyze
    if ticker in reg.get('whitelist', []):
        return False, "whitelisted"

    # Dead ticker check
    info = reg.get('skipped', {}).get(ticker)
    if info and info.get('failures', 0) >= SKIP_AFTER:
        return True, f"dead ticker ({info['failures']} failures: {info.get('last_reason','?')})"

    return False, ""


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


def record_failure(ticker: str, reason: str):
    """Record a failed yfinance fetch. After SKIP_AFTER failures, ticker is auto-skipped."""
    reg = _load()
    skipped = reg.setdefault('skipped', {})
    entry = skipped.setdefault(ticker, {'failures': 0, 'first_seen': datetime.now().isoformat()[:10]})
    entry['failures'] = entry.get('failures', 0) + 1
    entry['last_reason'] = reason[:120]
    entry['last_seen'] = datetime.now().isoformat()[:10]
    if entry['failures'] >= SKIP_AFTER:
        entry['auto_skipped'] = True
    _save(reg)


def record_success(ticker: str):
    """Reset failure count on successful fetch."""
    reg = _load()
    if ticker in reg.get('skipped', {}):
        del reg['skipped'][ticker]
        _save(reg)


def add_to_whitelist(ticker: str):
    """Force-include a ticker regardless of failure count."""
    reg = _load()
    if ticker not in reg.get('whitelist', []):
        reg.setdefault('whitelist', []).append(ticker)
        _save(reg)


def get_stats() -> dict:
    """Return summary stats about the skip registry."""
    reg = _load()
    skipped = reg.get('skipped', {})
    dead = [t for t, v in skipped.items() if v.get('failures', 0) >= SKIP_AFTER]
    warned = [t for t, v in skipped.items() if 0 < v.get('failures', 0) < SKIP_AFTER]
    return {
        'dead_tickers': len(dead),
        'warned_tickers': len(warned),
        'whitelisted': len(reg.get('whitelist', [])),
        'top_dead': dead[:10],
        'top_warned': [(t, skipped[t]['failures']) for t in warned[:5]],
    }


def print_report():
    stats = get_stats()
    print(f"Skip Registry Report:")
    print(f"  Dead (auto-skip): {stats['dead_tickers']} tickers")
    print(f"  Warned (1-2 fails): {stats['warned_tickers']} tickers")
    print(f"  Whitelisted: {stats['whitelisted']} tickers")
    if stats['top_dead']:
        print(f"  Top dead: {', '.join(stats['top_dead'][:8])}")


if __name__ == '__main__':
    print_report()
