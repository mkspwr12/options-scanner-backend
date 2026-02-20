#!/usr/bin/env python3
"""Test with unique tickers to avoid all cache."""
import urllib.request
import json
import time
import random

url = "https://options-scanner-backend-2exk6s.azurewebsites.net/api/stock-scan"

# Use really unique tickers unlikely to be in cache
unique_tickers = [f"TEST{i}{random.randint(0,9999)}" for i in range(3)]
real_tickers = ["BITF", "MSTR", "MARA"]  # Bitcoin/crypto related, less common

payload = json.dumps({
    "tickers": real_tickers,
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
        print(f"Tickers: {real_tickers}")
        print(f"Result: {elapsed:.1f}s | {num_stocks} stocks | source={source}")
        if num_stocks > 0:
            for stock in resp.get("results", []):
                print(f"  {stock['ticker']}: ${stock['price']:.2f}")
        else:
            print("  (No results)")
except Exception as e:
    elapsed = time.time() - start
    print(f"ERR after {elapsed:.1f}s: {str(e)[:100]}")
