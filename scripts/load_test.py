"""Small standard-library HTTP load test for reproducible portfolio metrics."""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor


def request_once(url: str) -> tuple[float, bool]:
    payload = json.dumps({"text": "The dashboard is fast and support was excellent.", "product": "LoadTest", "source": "review"}).encode()
    request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            success = response.status == 201
    except Exception:
        success = False
    return (time.perf_counter() - started) * 1_000, success


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000/api/v1/analyze")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    args = parser.parse_args()
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        results = list(pool.map(lambda _: request_once(args.url), range(args.requests)))
    elapsed = time.perf_counter() - started
    latencies, successes = zip(*results)
    ordered = sorted(latencies)
    report = {"requests": args.requests, "successful": sum(successes), "error_rate": 1 - sum(successes) / args.requests, "throughput_requests_per_second": args.requests / elapsed, "latency_ms": {"mean": statistics.mean(latencies), "p50": statistics.median(latencies), "p95": ordered[int(0.95 * (len(ordered) - 1))]}}
    print(json.dumps(report, indent=2))
    if report["error_rate"] > 0.01:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
