#!/usr/bin/env python3
"""Test fresh batch request avoiding cache."""
import urllib.request
import json
import time

url = "https://options-scanner-backend-2exk6s.azurewebsites.net/api/stock-scan"
# Use different tickers to bypass cache
payload = json.dumps({
    "tickers": ["META", "TSLA", "AMD", "JPM", "V", "DIS", "NFLX", "INTC", "BA", "COIN"],
    "filters": {}
}).encode()

req = urllib.request.Request(
    url,
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST"
)

start = time.time()
try:
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.loads(r.read().decode())
        elapsed = time.time() - start
        num_stocks = len(resp.get("results", []))
        source = resp.get("source", "unknown")
        print(f"OK: {elapsed:.1f}s | {num_stocks} stocks | source={source}")
        for stock in resp.get("results", [])[:3]:
            print(f"  {stock['ticker']}: ${stock['price']:.2f}")
except Exception as e:
    elapsed = time.time() - start
    print(f"ERR after {elapsed:.1f}s: {str(e)[:80]}")
