#!/usr/bin/env python3
"""
audit_skip_registry.py  --  read-only audit of config/skip_registry.json

Answers: is the dead-ticker registry over-matching? Specifically, are tickers
being permanently retired for reasons that are NOT "this ticker has no data"?

Writes nothing. Prints a report.
"""
import json, os, re, sys
from collections import Counter, defaultdict
from datetime import datetime

REG = r"D:\StockAnalysis\config\skip_registry.json"
CFG = r"D:\StockAnalysis\config\smart_config.json"

with open(CFG) as f:
    skip_after = json.load(f).get('analysis', {}).get('skip_after_n_failures', 3)

with open(REG) as f:
    reg = json.load(f)

skipped = reg.get('skipped', {})
whitelist = reg.get('whitelist', [])

dead = {t: v for t, v in skipped.items() if v.get('failures', 0) >= skip_after}
warned = {t: v for t, v in skipped.items() if 0 < v.get('failures', 0) < skip_after}


def classify(reason: str) -> str:
    r = (reason or '').lower()
    if 'too large' in r or 'market cap' in r or 'too small' in r:
        return 'VALUATION_FILTER (recoverable - cap can change)'
    if 'price unavailable' in r or 'no price' in r:
        return 'NO_PRICE (often transient)'
    if '404' in r or 'not found' in r or 'no data found' in r or 'delisted' in r:
        return 'GENUINELY_DEAD (404 / delisted)'
    if '429' in r or 'rate limit' in r or 'too many request' in r:
        return 'RATE_LIMIT (transient - should never be fatal)'
    if 'timeout' in r or 'timed out' in r or 'connection' in r or 'ssl' in r \
       or 'max retries' in r or 'remote end closed' in r:
        return 'NETWORK (transient - should never be fatal)'
    if 'json' in r or 'expecting value' in r or 'decode' in r:
        return 'PARSE_ERROR (usually transient upstream)'
    if 'missing' in r or 'insufficient' in r or 'no financial' in r \
       or 'none' == r.strip():
        return 'INCOMPLETE_FUNDAMENTALS (ambiguous)'
    return 'OTHER'


buckets = Counter()
bucket_examples = defaultdict(list)
reasons = Counter()

for t, v in dead.items():
    reason = v.get('last_reason', '') or ''
    reasons[reason[:70]] += 1
    b = classify(reason)
    buckets[b] += 1
    if len(bucket_examples[b]) < 6:
        bucket_examples[b].append((t, reason[:60]))

# failure-count distribution: how many died at exactly the threshold?
fc = Counter(v.get('failures', 0) for v in dead.values())

# age: when were they last seen?
years = Counter()
for v in dead.values():
    ls = v.get('last_seen', '') or v.get('first_seen', '') or '?'
    years[ls[:7]] += 1

print("=" * 74)
print("  SKIP REGISTRY AUDIT  --  config/skip_registry.json")
print(f"  skip_after_n_failures = {skip_after}")
print("=" * 74)
print(f"  Entries in registry : {len(skipped):,}")
print(f"  Dead (auto-skipped) : {len(dead):,}")
print(f"  Warned (1-{skip_after-1} fails)  : {len(warned):,}")
print(f"  Whitelisted         : {len(whitelist):,}")

print("\n-- DEAD TICKERS BY ROOT CAUSE " + "-" * 44)
recoverable = 0
for b, n in buckets.most_common():
    pct = n / max(len(dead), 1) * 100
    print(f"  {n:6,}  ({pct:5.1f}%)  {b}")
    if not b.startswith('GENUINELY_DEAD'):
        recoverable += n
    for t, r in bucket_examples[b][:3]:
        print(f"              e.g. {t:14s} {r}")

print("\n-- FAILURE COUNT DISTRIBUTION " + "-" * 44)
for k in sorted(fc):
    marker = "  <-- died at the threshold, never given a 4th chance" \
             if k == skip_after else ""
    print(f"  failures={k:<3} {fc[k]:6,}{marker}")

print("\n-- LAST SEEN (month) " + "-" * 53)
for k in sorted(years, reverse=True)[:12]:
    print(f"  {k}  {years[k]:6,}")

print("\n-- TOP 15 RAW REASONS " + "-" * 52)
for r, n in reasons.most_common(15):
    print(f"  {n:6,}  {r}")

print("\n" + "=" * 74)
print(f"  VERDICT: {recoverable:,} of {len(dead):,} dead tickers "
      f"({recoverable/max(len(dead),1)*100:.1f}%) were retired for reasons "
      f"that are\n  NOT a confirmed 404/delisting.")
print("=" * 74)
