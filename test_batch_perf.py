#!/usr/bin/env python3
"""Test batched stock scan API endpoint performance."""
import time
import urllib.request
import json

url = "https://options-scanner-backend-2exk6s.azurewebsites.net/api/stock-scan"
payload = json.dumps({
    "tickers": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AMD", "JPM", "V"],
    "filters": {}
}).encode("utf-8")

headers = {"Content-Type": "application/json"}
req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

start = time.time()
try:
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode())
        elapsed = time.time() - start
        print(f"✅ Batch Stock Scan Complete in {elapsed:.1f} seconds")
        print(f"📊 Results: {len(data.get('results', []))} stocks fetched")
        if data.get("results"):
            for stock in data.get("results", [])[:5]:
                print(f"  {stock['ticker']}: ${stock['price']:.2f} (RSI: {stock['rsi']})")
        else:
            print(f"Full response: {json.dumps(data, indent=2)[:500]}")
except Exception as e:
    elapsed = time.time() - start
    print(f"❌ Error after {elapsed:.1f}s: {str(e)[:100]}")
