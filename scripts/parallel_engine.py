#!/usr/bin/env python3
"""
parallel_engine.py  —  valuefund.substack.com
High-throughput parallel stock analysis engine.

Architecture:
  - ThreadPoolExecutor(N workers) for concurrent yfinance fetches
  - Worker-level rate limiting (sleep per worker, not global)
  - Skip registry integration (dead tickers, staleness)
  - Batch size 50 (vs legacy 10)
  - Progress bar + ETA
  - Atomic DB writes (one connection per worker thread, WAL mode)
  - Automatic retry with exponential backoff on HTTP 429

Usage:
    python parallel_engine.py              # run next batch
    python parallel_engine.py --workers 6  # use 6 parallel workers
    python parallel_engine.py --batch 100  # analyze 100 stocks per run
    python parallel_engine.py --all        # run until queue empty
"""
import sys, os, time, json, sqlite3, argparse, threading
from datetime import date, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE    = r"D:\StockAnalysis"
SCRIPTS = os.path.join(BASE, "scripts")
sys.path.insert(0, SCRIPTS)

# Load config
def _load_cfg():
    try:
        with open(os.path.join(BASE, "config", "smart_config.json")) as f:
            return json.load(f).get('analysis', {})
    except: return {}

CFG = _load_cfg()
DEFAULT_WORKERS    = CFG.get('parallel_workers', 4)
DEFAULT_BATCH      = CFG.get('batch_size', 50)
SLEEP_SEC          = CFG.get('rate_limit_sleep_sec', 1.2)
MAX_CAP            = CFG.get('max_market_cap', 500_000_000)
STALE_DAYS         = CFG.get('staleness_days', 14)
STALE_MOVE         = CFG.get('staleness_price_move_pct', 10.0)

DB_PATH     = r"D:\StockAnalysis\database\stocks.db"
REPORTS_DIR = os.path.join(BASE, "reports")

# ── Import analysis functions from existing analyzer.py ──────────────────────
from analyzer import (
    fetch_and_analyze, generate_markdown_report, save_report,
    insert_into_db, get_analyzed_tickers, CANDIDATE_STOCKS, create_database
)
from skip_registry import (should_skip, should_skip_stale, record_failure,
                           record_success, record_filtered, record_transient,
                           is_filter_verdict, is_transient,
                           reset_recheck_budget, rechecks_granted)  # __VF_SKIPREG_V2__

# __VF_HARDENING_V1__  run lock + completion sentinel -------------------------
# Added 2026-09-01. Rationale:
#   * The weekly scheduled run was launched via Start-Process from an MCP
#     PowerShell host that caps calls at ~60s and kills its child tree on
#     timeout. The engine died mid-batch at 66/296 with no trace in the log
#     tail, and nothing downstream could tell a finished run from a killed one.
#   * Nothing prevented a second launch racing the first over the same SQLite
#     DB and skip registry.
import atexit as _atexit
import json as _json

LOCK_PATH     = os.path.join(BASE, "logs", "parallel_engine.lock")
SENTINEL_PATH = os.path.join(BASE, "logs", "parallel_engine_last_run.json")

EXIT_LOCKED = 5   # another run holds the lock


def _pid_alive(pid: int) -> bool:
    """True if pid is a live process. Never signals the process."""
    if not pid or pid <= 0:
        return False
    if os.name == 'nt':
        # NOTE: os.kill(pid, 0) on Windows calls TerminateProcess -- it would
        # kill the very process we are probing. Use OpenProcess instead.
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            k32 = ctypes.windll.kernel32
            h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not h:
                return False
            code = ctypes.c_ulong()
            ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
            k32.CloseHandle(h)
            return bool(ok) and code.value == STILL_ACTIVE
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


class RunLock:
    """PID-aware lockfile with stale-lock recovery."""

    def __init__(self, path=LOCK_PATH, force=False):
        self.path = path
        self.force = force
        self.acquired = False

    def acquire(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if os.path.exists(self.path):
            holder = {}
            try:
                with open(self.path) as f:
                    holder = _json.load(f)
            except Exception:
                holder = {}
            pid = int(holder.get('pid', 0) or 0)
            started = holder.get('started', '?')
            if _pid_alive(pid) and not self.force:
                tprint("  " + "!" * 62)
                tprint("  [ERROR] LOCKED: another parallel_engine run (PID "
                       + str(pid) + ", started " + str(started)
                       + ") is still active.")
                tprint("  [ERROR] Lockfile: " + self.path)
                tprint("  [ERROR] Refusing to start a concurrent run -- two runs "
                       "would race over stocks.db and the skip registry.")
                tprint("  [ERROR] Pass --force to override if you are certain "
                       "the holder is dead.")
                tprint("  " + "!" * 62)
                return False
            tprint("  [warn] Removing stale lock from PID " + str(pid)
                   + " (started " + str(started) + ", no longer running).")
            try:
                os.remove(self.path)
            except Exception as e:
                tprint("  [warn] could not remove stale lock: " + str(e))

        try:
            with open(self.path, 'w') as f:
                _json.dump({'pid': os.getpid(),
                            'started': datetime.now().isoformat(timespec='seconds'),
                            'argv': sys.argv[1:]}, f)
            self.acquired = True
            _atexit.register(self.release)
            return True
        except Exception as e:
            tprint("  [warn] could not write lockfile (" + str(e)
                   + ") -- continuing unlocked.")
            return True

    def release(self):
        if not self.acquired:
            return
        self.acquired = False
        try:
            if os.path.exists(self.path):
                os.remove(self.path)
        except Exception:
            pass


def write_sentinel(completed, exit_code, summary=None, args_ns=None, error=None):
    """
    Write logs/parallel_engine_last_run.json.

    `completed` is the load-bearing field: any caller about to git-commit the
    dashboard should refuse unless completed is true AND exit_code is 0.
    """
    summary = summary or {}
    payload = {
        'timestamp':   datetime.now().isoformat(timespec='seconds'),
        'date':        date.today().isoformat(),
        'pid':         os.getpid(),
        'completed':   bool(completed),
        'exit_code':   int(exit_code),
        'analyzed':    summary.get('ok', 0),
        'attempted':   summary.get('attempted', 0),
        'queue_total': summary.get('queue_total', 0),
        'skipped':     summary.get('skipped', 0),
        'errors':      summary.get('errors', 0),
        'elapsed_sec': round(summary.get('elapsed', 0.0), 1),
        'workers':     getattr(args_ns, 'workers', None),
        'batch':       getattr(args_ns, 'batch', None),
        'queue_stats': dict(LAST_QUEUE_STATS),
        'error':       error,
    }
    try:
        os.makedirs(os.path.dirname(SENTINEL_PATH), exist_ok=True)
        with open(SENTINEL_PATH, 'w') as f:
            _json.dump(payload, f, indent=2)
    except Exception as e:
        tprint("  [warn] could not write run sentinel: " + str(e))
# -- end __VF_HARDENING_V1__ --------------------------------------------------


# Optional generators
try:
    from generate_dashboard import generate_html_index as _gen_html
    from generate_docx      import generate_docx_report as _gen_docx
    from generate_thesis    import short_thesis, detailed_thesis
    _HAS_GEN = True
except ImportError:
    _HAS_GEN = False

# ── Thread-safe print lock ────────────────────────────────────────────────────
_print_lock = threading.Lock()
def tprint(*args, **kwargs):
    with _print_lock:
        print(*args, **kwargs)

# ── Thread-safe DB writer ─────────────────────────────────────────────────────
_db_lock = threading.Lock()

def safe_insert(data: dict, report_path: str):
    """Thread-safe DB insert with thesis generation."""
    if _HAS_GEN:
        try:
            data['short_thesis']    = short_thesis(data)
            data['detailed_thesis'] = detailed_thesis(data)
        except Exception as e:
            data['short_thesis']    = ''
            data['detailed_thesis'] = ''

    with _db_lock:
        insert_into_db(data, report_path)


# ── Worker function ───────────────────────────────────────────────────────────
def analyze_one(ticker: str, exchange: str, notes: str, worker_id: int) -> dict:
    """
    Fetch + analyze one stock. Returns result dict.
    Called from thread pool — must be thread-safe.
    """
    result = {'ticker': ticker, 'exchange': exchange, 'status': 'pending',
              'worker': worker_id, 'elapsed': 0.0}
    t0 = time.time()

    # Skip registry check
    skip, reason = should_skip(ticker)
    if skip:
        result.update(status='skip_dead', reason=reason)
        return result

    try:
        data, err = fetch_and_analyze(ticker, exchange, notes)
        elapsed = time.time() - t0

        if data:
            record_success(ticker)
            rpt   = generate_markdown_report(data)
            rpath = save_report(ticker, rpt)
            safe_insert(data, rpath)

            # Generate DOCX (best-effort)
            if _HAS_GEN:
                try: _gen_docx(data)
                except: pass

            result.update(
                status='ok',
                score=data.get('promise_score', 0),
                grade=data.get('grade', '?'),
                elapsed=elapsed,
                piotroski=data.get('piotroski_score'),
                altman_z=data.get('altman_z'),
                mos=data.get('margin_of_safety'),
            )
        else:
            err = err or 'unknown'
            if is_filter_verdict(err):
                record_filtered(ticker, err)       # screening verdict, not dead
            elif is_transient(err):
                record_transient(ticker, err)      # infra fault, not dead
            else:
                record_failure(ticker, err)
            result.update(status='skip', reason=err, elapsed=elapsed)

    except Exception as e:
        if is_transient(str(e)):
            record_transient(ticker, str(e)[:80])
        else:
            record_failure(ticker, str(e)[:80])
        result.update(status='error', reason=str(e)[:80], elapsed=time.time()-t0)

    # Per-worker rate limiting
    time.sleep(SLEEP_SEC)
    return result


# ── Progress tracker ──────────────────────────────────────────────────────────
class Progress:
    def __init__(self, total: int):
        self.total   = total
        self.done    = 0
        self.ok      = 0
        self.skipped = 0
        self.errors  = 0
        self.start   = time.time()
        self._lock   = threading.Lock()

    def update(self, result: dict):
        with self._lock:
            self.done += 1
            s = result.get('status', '')
            if s == 'ok':      self.ok += 1
            elif s == 'skip' or s == 'skip_dead': self.skipped += 1
            else:              self.errors += 1

            elapsed   = time.time() - self.start
            rate      = self.done / elapsed if elapsed > 0 else 0
            remaining = (self.total - self.done) / rate if rate > 0 else 0
            pct       = self.done / self.total * 100

            status_icon = {'ok': 'OK', 'skip': '--', 'skip_dead': 'XX', 'error': 'ER'}.get(s, '??')
            tprint(
                f"  [{status_icon}] {result['ticker']:10s} | "
                f"{self.done:3d}/{self.total} ({pct:5.1f}%) | "
                f"{self.ok} analyzed | "
                f"ETA {remaining/60:.1f}m | "
                f"{result.get('elapsed',0):.1f}s"
                + (f" | Score={result.get('score',0):.0f} {result.get('grade','?')}"
                   if s == 'ok' else f" | {result.get('reason','')[:40]}")
            )


# ── Build work queue ──────────────────────────────────────────────────────────
LAST_QUEUE_STATS = {
    'universe': 0, 'already_done': 0, 'dead_skipped': 0,
    'filtered_skipped': 0, 'rechecks': 0,
    'stale': 0, 'queue_total': 0, 'batch': 0,
}


def build_queue(batch_size: int, force_refresh: bool = False) -> list:
    """
    Returns list of (ticker, exchange, notes) to analyze.
    Applies: already-done filter, dead-ticker skip, staleness filter.
    Side effect: populates LAST_QUEUE_STATS.
    """
    analyzed = get_analyzed_tickers()

    # Load universe (CANDIDATE_STOCKS + any extras from universe.csv)
    universe = list(CANDIDATE_STOCKS)
    uni_path = os.path.join(BASE, "config", "universe.csv")
    if os.path.exists(uni_path):
        import csv
        with open(uni_path) as f:
            for row in csv.DictReader(f):
                t = row.get('ticker','').strip().upper()
                e = row.get('exchange','OTC').strip()
                n = row.get('notes','').strip()
                if t: universe.append((t, e, n))

    # De-duplicate
    seen = set()
    unique = []
    for t, e, n in universe:
        if t not in seen:
            seen.add(t)
            unique.append((t, e, n))

    # Filter: not yet done OR stale OR forcing refresh
    stale_n = 0
    if force_refresh:
        candidates = unique
    else:
        # Never-analyzed tickers go first (highest priority)
        candidates = [(t, e, n) for t, e, n in unique if t not in analyzed]

        # Then re-queue anything older than STALE_DAYS, oldest analysis first.
        # (staleness_days / staleness_price_move_pct live in config/smart_config.json)
        last_seen = {}
        try:
            _c = sqlite3.connect(DB_PATH)
            for _t, _d in _c.execute(
                "SELECT ticker, analysis_date FROM analyzed_stocks "
                "WHERE julianday('now') - julianday(analysis_date) >= ?",
                (STALE_DAYS,)
            ):
                if _t and _d:
                    last_seen[_t.strip().upper()] = _d
            _c.close()
        except Exception as _e:
            tprint(f"  [warn] staleness query failed: {_e}")

        stale = [(t, e, n) for t, e, n in unique if t in last_seen]
        stale.sort(key=lambda x: last_seen[x[0]])   # oldest analysis_date first
        stale_n = len(stale)
        candidates = candidates + stale

    # Apply skip registry (dead + filtered tickers, with decay rechecks)
    reset_recheck_budget()
    queue = []
    dead_skipped = 0
    filt_skipped = 0
    for t, e, n in candidates:
        skip, reason = should_skip(t)
        if skip:
            if reason.startswith('filtered'): filt_skipped += 1
            else:                             dead_skipped += 1
            continue
        queue.append((t, e, n))

    tprint(f"\n  Universe      : {len(unique):,}")
    tprint(f"  Already done  : {len(analyzed):,}")
    tprint(f"  Dead (skipped): {dead_skipped:,}")
    tprint(f"  Filtered (skip): {filt_skipped:,}")
    tprint(f"  Rechecks granted: {rechecks_granted():,}")
    tprint(f"  Stale (>={STALE_DAYS}d) : {stale_n:,}")
    tprint(f"  Queue         : {len(queue):,}")
    tprint(f"  This batch    : {min(len(queue), batch_size):,}")

    # Record stats so the caller can distinguish "nothing to do because
    # everything is genuinely fresh" from "nothing done because broken".
    LAST_QUEUE_STATS.update(
        universe=len(unique),
        already_done=len(analyzed),
        dead_skipped=dead_skipped,
        filtered_skipped=filt_skipped,
        rechecks=rechecks_granted(),
        stale=stale_n,
        queue_total=len(queue),
        batch=min(len(queue), batch_size),
    )

    return queue[:batch_size]


# ── Main parallel runner ──────────────────────────────────────────────────────
def run_parallel(workers: int = DEFAULT_WORKERS,
                 batch_size: int = DEFAULT_BATCH,
                 run_all: bool = False) -> dict:
    """
    Run one batch (or all) using parallel workers.
    Returns summary dict.
    """
    create_database()
    os.makedirs(REPORTS_DIR, exist_ok=True)

    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    tprint(f"\n{'='*66}")
    tprint(f"  valuefund.substack.com — Parallel Analysis Engine")
    tprint(f"  {now} | Workers={workers} | Batch={batch_size}")
    tprint(f"{'='*66}")

    summary = {'ok': 0, 'skipped': 0, 'errors': 0, 'results': [],
               'elapsed': 0.0, 'attempted': 0, 'queue_total': 0, 'rounds': 0}

    if run_all:
        # Process everything in queue, loop until empty
        round_n = 0
        first_queue_total = None
        while True:
            queue = build_queue(batch_size)
            if first_queue_total is None:
                first_queue_total = LAST_QUEUE_STATS['queue_total']
            if not queue:
                tprint("\n  Queue empty — all candidates analyzed!")
                break
            round_n += 1
            tprint(f"\n  --- Round {round_n} ---")
            r = _run_batch(queue, workers)
            summary['ok']        += r['ok']
            summary['skipped']   += r['skipped']
            summary['errors']    += r['errors']
            summary['elapsed']   += r['elapsed']
            summary['attempted'] += len(queue)
            summary['results']   += r['results']
            tprint(f"  Round {round_n}: {r['ok']} analyzed, {r['skipped']} skipped")
        summary['rounds']      = round_n
        summary['queue_total'] = first_queue_total or 0
        tprint(f"\n  TOTAL: {summary['ok']} stocks analyzed across {round_n} rounds")
    else:
        queue = build_queue(batch_size)
        summary['queue_total'] = LAST_QUEUE_STATS['queue_total']
        if not queue:
            tprint("\n  Queue empty — nothing to analyze.")
        else:
            r = _run_batch(queue, workers)
            summary.update(r)
            summary['attempted']   = len(queue)
            summary['queue_total'] = LAST_QUEUE_STATS['queue_total']
            summary['rounds']      = 1

    # Regenerate dashboard + theses after batch.
    # NOTE: this used to be skipped entirely on an empty queue, which meant
    # database/index.html silently went stale on no-op days. Always run it.
    tprint("\n  Regenerating dashboard...")
    try:
        if _HAS_GEN: _gen_html()
        else:
            from analyzer import generate_html_index
            generate_html_index()
        tprint("  Dashboard: OK")
    except Exception as e:
        tprint(f"  Dashboard error: {e}")

    return summary


# ── Run health evaluation ─────────────────────────────────────────────────────
# Exit codes consumed by daily_analysis.bat -> Windows Task Scheduler Last Result
EXIT_OK          = 0   # healthy run, or queue legitimately empty
EXIT_DID_NOTHING = 3   # queue had work but ZERO stocks were analyzed  <-- the Jul-16..26 bug
EXIT_BELOW_MIN   = 4   # analyzed fewer than an explicitly-required minimum

# Yield below this fraction of the attempted batch logs a WARNING (not a failure).
LOW_YIELD_WARN_PCT = 0.05
LOW_YIELD_MIN_BATCH = 20   # don't warn on tiny batches, the ratio is meaningless


def evaluate_run(summary: dict, fail_under: int = 0,
                 min_yield_pct: float = 0.0) -> int:
    """
    Decide whether this run was healthy and return a process exit code.

    Distinguishes the two look-alike cases that let 14 days pass unnoticed:
      * queue_total == 0  -> genuinely nothing to do (everything fresh) -> OK
      * queue_total > 0 but analyzed == 0 -> the pipeline is broken     -> FAIL
    """
    ok          = summary.get('ok', 0)
    attempted   = summary.get('attempted', 0)
    queue_total = summary.get('queue_total', 0)
    errors      = summary.get('errors', 0)
    skipped     = summary.get('skipped', 0)

    tprint(f"\n{'='*66}")
    tprint(f"  RUN HEALTH: analyzed={ok} attempted={attempted} "
           f"queue_total={queue_total} skipped={skipped} errors={errors}")

    if queue_total == 0:
        tprint("  [INFO] Queue was empty and nothing was stale — nothing to do. "
               "This is a legitimate no-op, not a failure.")
        tprint(f"{'='*66}")
        return EXIT_OK

    if attempted == 0:
        # queue_total > 0 but we never submitted anything: should not happen
        tprint("  " + "!"*62)
        tprint("  [ERROR] PIPELINE DID NOTHING: queue reported "
               f"{queue_total:,} tickers but 0 were attempted.")
        tprint("  [ERROR] The run 'succeeded' without doing any work. Investigate "
               "build_queue()/batch slicing before trusting tomorrow's data.")
        tprint("  " + "!"*62)
        tprint(f"{'='*66}")
        return EXIT_DID_NOTHING

    if ok == 0:
        # 2026-08-30 fix: ok==0 is NOT itself a failure signal. Near the tail
        # of the queue (universe fully analyzed, only stale-but-now-ineligible
        # tickers left to re-check), a batch can legitimately be 100% clean
        # skips -- e.g. market cap grew past the ceiling, or a ticker is
        # confirmed dead. That produced false EXIT_DID_NOTHING alerts on
        # 2026-07-30, 2026-08-24, 2026-08-26 (queue sizes of 1-10, all
        # skipped, errors=0). The real failure signal is ERRORS, not a zero
        # analyzed count -- an outage/rate-limit/auth break shows up as
        # errors>0 (or skipped<attempted with nothing accounted for), not as
        # clean, explained skips.
        if errors == 0 and skipped == attempted:
            tprint(f"  [OK] Run healthy: all {attempted} remaining queue items "
                   f"were cleanly skipped for a valid reason (0 errors) -- "
                   "no pipeline failure, just an exhausted tail of the queue.")
            tprint(f"{'='*66}")
            return EXIT_OK
        tprint("  " + "!"*62)
        tprint(f"  [ERROR] PIPELINE DID NOTHING: attempted {attempted} tickers "
               f"from a queue of {queue_total:,} and analyzed ZERO.")
        tprint(f"  [ERROR] {skipped} skipped, {errors} errored. Every single "
               "ticker failed — this is a broken run, not a quiet day.")
        tprint("  [ERROR] Likely causes: data-source outage / rate limiting / "
               "auth or network failure / skip-registry over-matching.")
        tprint("  " + "!"*62)
        tprint(f"{'='*66}")
        return EXIT_DID_NOTHING

    if fail_under and ok < fail_under:
        tprint("  " + "!"*62)
        tprint(f"  [ERROR] LOW YIELD: analyzed {ok}, required at least "
               f"{fail_under} (--fail-under).")
        tprint("  " + "!"*62)
        tprint(f"{'='*66}")
        return EXIT_BELOW_MIN

    # Rechecks (decayed dead/filtered tickers given one retry) are EXPECTED
    # to mostly re-skip, so they must not count against the yield floor.
    rechecks = min(LAST_QUEUE_STATS.get('rechecks', 0), attempted)
    eff_att  = attempted - rechecks
    if min_yield_pct and eff_att >= LOW_YIELD_MIN_BATCH:
        floor = eff_att * (min_yield_pct / 100.0)
        if rechecks:
            tprint(f"  [INFO] yield floor computed on {eff_att} non-recheck "
                   f"attempts ({rechecks} rechecks excluded).")
        if ok < floor:
            tprint("  " + "!" * 62)
            tprint(f"  [ERROR] YIELD BELOW FLOOR: analyzed {ok} of {eff_att} "
                   f"non-recheck attempts ({ok / eff_att * 100:.1f}%), floor is "
                   f"{min_yield_pct:.0f}%.")
            tprint("  [ERROR] Treating this as a failed run. Do NOT publish the "
                   "dashboard from this batch.")
            tprint("  " + "!" * 62)
            tprint(f"{'=' * 66}")
            return EXIT_BELOW_MIN


    if attempted >= LOW_YIELD_MIN_BATCH and ok < attempted * LOW_YIELD_WARN_PCT:
        tprint(f"  [WARNING] SUSPICIOUSLY LOW YIELD: only {ok} of {attempted} "
               f"attempted ({ok/attempted*100:.1f}%) were analyzed successfully.")
        tprint("  [WARNING] Not treated as a failure (the remaining universe is "
               "mostly dead tickers), but worth a look if it repeats.")
        tprint(f"{'='*66}")
        return EXIT_OK

    tprint(f"  [OK] Run healthy: {ok} analyzed "
           f"({ok/attempted*100:.1f}% of attempted).")
    tprint(f"{'='*66}")
    return EXIT_OK


def _run_batch(queue: list, workers: int) -> dict:
    """Execute one batch with thread pool."""
    prog = Progress(len(queue))
    results = []

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix='vf') as pool:
        futures = {
            pool.submit(analyze_one, t, e, n, i % workers): (t, e, n)
            for i, (t, e, n) in enumerate(queue)
        }
        for future in as_completed(futures):
            res = future.result()
            results.append(res)
            prog.update(res)

    ok      = [r for r in results if r['status'] == 'ok']
    skipped = [r for r in results if r['status'] in ('skip', 'skip_dead')]
    errors  = [r for r in results if r['status'] == 'error']

    tprint(f"\n  {'='*60}")
    tprint(f"  Batch complete: {len(ok)} analyzed | {len(skipped)} skipped | {len(errors)} errors")

    if ok:
        top = sorted(ok, key=lambda r: r.get('score', 0), reverse=True)[:5]
        tprint("  Top picks:")
        for i, r in enumerate(top, 1):
            tprint(f"    {i}. {r['ticker']:10s} {r.get('grade','?')} {r.get('score',0):.0f}pts")

    elapsed = time.time() - prog.start
    tprint(f"  Time: {elapsed:.1f}s | Rate: {len(queue)/elapsed*60:.0f} stocks/min")

    return {'ok': len(ok), 'skipped': len(skipped), 'errors': len(errors),
            'results': results, 'elapsed': elapsed}


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Parallel stock analysis engine')
    parser.add_argument('--workers', type=int, default=DEFAULT_WORKERS,
                        help=f'Parallel workers (default {DEFAULT_WORKERS})')
    parser.add_argument('--batch',   type=int, default=DEFAULT_BATCH,
                        help=f'Stocks per batch (default {DEFAULT_BATCH})')
    parser.add_argument('--all',     action='store_true',
                        help='Run until queue is empty')
    parser.add_argument('--fail-under', type=int, default=0, metavar='N',
                        help='Exit 4 if fewer than N stocks were analyzed '
                             '(default 0 = disabled)')
    parser.add_argument('--min-yield-pct', type=float, default=0.0, metavar='PCT',
                        help='Exit 4 if analyzed/attempted falls below PCT '
                             'percent (default 0 = disabled). Opt-in: see the '
                             '2026-08-30 note in evaluate_run about false '
                             'alarms on exhausted-tail batches.')
    parser.add_argument('--no-lock', action='store_true',
                        help='Skip the concurrency lockfile')
    parser.add_argument('--force', action='store_true',
                        help='Steal the lock even if the holder looks alive')
    args = parser.parse_args()

    lock = RunLock(force=args.force)
    if not args.no_lock:
        if not lock.acquire():
            write_sentinel(completed=False, exit_code=EXIT_LOCKED,
                           args_ns=args, error='another run holds the lock')
            sys.exit(EXIT_LOCKED)

    summary = {}
    try:
        summary = run_parallel(workers=args.workers, batch_size=args.batch,
                               run_all=args.all)
    except BaseException as exc:
        # BaseException, not Exception: a KeyboardInterrupt / SystemExit from a
        # killed parent must still leave a sentinel saying completed=false.
        import traceback
        traceback.print_exc()
        tprint("\n  [ERROR] Run aborted: " + str(exc))
        write_sentinel(completed=False, exit_code=1, summary=summary,
                       args_ns=args, error=str(exc)[:300])
        lock.release()
        sys.exit(1)

    code = evaluate_run(summary, fail_under=args.fail_under,
                        min_yield_pct=args.min_yield_pct)
    write_sentinel(completed=True, exit_code=code, summary=summary, args_ns=args)
    lock.release()
    tprint(f"  Exiting with code {code}")
    sys.exit(code)
