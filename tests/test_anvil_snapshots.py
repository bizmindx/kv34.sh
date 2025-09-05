#!/usr/bin/env python3
"""
Test for anvil snapshot functionality
"""
import time
import requests
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from containers.node.anvil_manager import AnvilManager

def test_snapshot_functionality():
    print("🧪 Testing Anvil Snapshot Functionality...")
    
    # Create anvil manager with short timeout for testing
    test_anvil = AnvilManager(port=8548, inactivity_timeout=10)
    
    # Test 1: Start fresh anvil
    print("\n1. Starting fresh anvil...")
    success = test_anvil.start()
    print(f"   Start result: {success}")
    
    if success:
        # Test 2: Get initial block number
        print("\n2. Getting initial block number...")
        response = requests.post(
            "http://localhost:8548",
            json={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1},
            timeout=5
        )
        initial_block = int(response.json()["result"], 16)
        print(f"   Initial block: {initial_block}")
        
        # Test 3: Mine some blocks to create state
        print("\n3. Mining some blocks to create state...")
        for i in range(5):
            response = requests.post(
                "http://localhost:8548",
                json={"jsonrpc": "2.0", "method": "evm_mine", "params": [], "id": 1},
                timeout=5
            )
            time.sleep(0.1)
        
        # Get block number after mining
        response = requests.post(
            "http://localhost:8548",
            json={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1},
            timeout=5
        )
        after_mining_block = int(response.json()["result"], 16)
        print(f"   After mining block: {after_mining_block}")
        
        # Test 4: Stop anvil (creates snapshot)
        print("\n4. Stopping anvil (creates snapshot)...")
        test_anvil.stop()
        
        # Check snapshot info
        snapshot_info = test_anvil.get_snapshot_info()
        print(f"   Snapshots: {snapshot_info['total_snapshots']}")
        
        # Test 5: Start anvil (should restore from snapshot)
        print("\n5. Starting anvil (should restore from snapshot)...")
        restart_success = test_anvil.start()
        print(f"   Restart result: {restart_success}")
        
        if restart_success:
            # Test 6: Get block number after restart
            print("\n6. Getting block number after restart...")
            response = requests.post(
                "http://localhost:8548",
                json={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1},
                timeout=5
            )
            after_restart_block = int(response.json()["result"], 16)
            print(f"   After restart block: {after_restart_block}")
            
            # Test 7: Verify state persistence
            print("\n7. Verifying state persistence...")
            if after_restart_block == after_mining_block:
                print("   ✅ State persisted correctly!")
                print(f"   Block number maintained: {after_restart_block}")
            else:
                print("   ❌ State was not persisted!")
                print(f"   Expected: {after_mining_block}, Got: {after_restart_block}")
        
        # Test 8: Test restart with fresh state
        print("\n8. Testing restart with fresh state...")
        fresh_restart = test_anvil.restart()
        print(f"   Fresh restart result: {fresh_restart}")
        
        if fresh_restart:
            # Get block number after fresh restart
            response = requests.post(
                "http://localhost:8548",
                json={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1},
                timeout=5
            )
            fresh_block = int(response.json()["result"], 16)
            print(f"   Fresh restart block: {fresh_block}")
            
            if fresh_block < after_mining_block:
                print("   ✅ Fresh restart worked (lower block number)")
            else:
                print("   ❌ Fresh restart failed (same block number)")
        
        # Test 9: Cleanup
        print("\n9. Final cleanup...")
        test_anvil.stop()
    
    print("\n✅ Snapshot test completed!")

def test_api_endpoints():
    print("\n🌐 Testing API Endpoints...")
    
    base_url = "http://localhost:5001"
    
    # Test anvil status with snapshots
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
    
    # Test anvil restart endpoint
    print("\n2. Testing /admin/server/anvil/restart endpoint...")
    try:
        response = requests.post(f"{base_url}/admin/server/anvil/restart")
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Restart result: {result}")
        else:
            print(f"   ❌ Failed to restart: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

if __name__ == "__main__":
    test_snapshot_functionality()
    test_api_endpoints()
