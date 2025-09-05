#!/usr/bin/env python3
"""
Simple test for anvil functionality
"""
import time
import requests
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from containers.node.anvil_manager import anvil_manager

def test_anvil():
    print("🧪 Testing Anvil Functionality...")
    
    # Test 1: Check initial status
    print("\n1. Checking initial anvil status...")
    status = anvil_manager.get_status()
    print(f"   Status: {status}")
    
    # Test 2: Start anvil
    print("\n2. Starting anvil...")
    success = anvil_manager.start()
    print(f"   Start result: {success}")
    
    if success:
        # Test 3: Check if running
        print("\n3. Checking if anvil is running...")
        is_running = anvil_manager.is_running()
        print(f"   Is running: {is_running}")
        
        # Test 4: Test RPC connection
        print("\n4. Testing RPC connection...")
        try:
            response = requests.post(
                "http://localhost:8545",
                json={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1},
                timeout=5
            )
            if response.status_code == 200:
                result = response.json()
                print(f"   RPC response: {result}")
            else:
                print(f"   RPC failed: {response.status_code}")
        except Exception as e:
            print(f"   RPC error: {e}")
        
        # Test 5: Stop anvil
        print("\n5. Stopping anvil...")
        stop_success = anvil_manager.stop()
        print(f"   Stop result: {stop_success}")
        
        # Test 6: Final status check
        print("\n6. Final status check...")
        final_status = anvil_manager.get_status()
        print(f"   Final status: {final_status}")
    
    print("\n✅ Anvil test completed!")

def test_api_endpoints():
    print("\n🌐 Testing API Endpoints...")
    
    base_url = "http://localhost:5001"
    
    # Test anvil status endpoint
    print("\n1. Testing /admin/server/anvil/status endpoint...")
    try:
        response = requests.get(f"{base_url}/admin/server/anvil/status")
        if response.status_code == 200:
            status = response.json()
            print(f"   ✅ Anvil status: {status}")
        else:
            print(f"   ❌ Failed to get status: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test anvil start endpoint
    print("\n2. Testing /admin/server/anvil/start endpoint...")
    try:
        response = requests.post(f"{base_url}/admin/server/anvil/start")
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Start result: {result}")
        else:
            print(f"   ❌ Failed to start: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test anvil stop endpoint
    print("\n3. Testing /admin/server/anvil/stop endpoint...")
    try:
        response = requests.post(f"{base_url}/admin/server/anvil/stop")
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Stop result: {result}")
        else:
            print(f"   ❌ Failed to stop: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

if __name__ == "__main__":
    test_anvil()
    test_api_endpoints()
