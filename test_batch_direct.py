#!/usr/bin/env python3
"""Direct test of batch method."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.providers.massive_provider import MassiveProvider
os.environ['MASSIVE_API_KEY'] = os.getenv('MASSIVE_API_KEY', '')

if not os.getenv('MASSIVE_API_KEY'):
    print("ERROR: MASSIVE_API_KEY not set")
    sys.exit(1)

provider = MassiveProvider()

print("Testing batch method...")
try:
    # Test with a known working symbol
    results = provider.get_stock_scan_data_batch(["AAPL"], days=90)
    print(f"Results: {list(results.keys())}")
    print(f"AAPL data: {results.get('AAPL', {}) is not None}")
    if results.get('AAPL'):
        aapl = results['AAPL']
        print(f"  Symbol: {aapl.get('symbol')}")
        print(f"  Price: {aapl.get('price')}")
        print(f"  Closes: {len(aapl.get('closes', []))} bars")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
