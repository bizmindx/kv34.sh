#!/usr/bin/env python3
"""
Test script for containerized anvil manager
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import time
import requests
from containers.node.anvil_container_manager import AnvilContainerManager

def test_anvil_container():
    print("🧪 Testing Containerized Anvil Manager...")
    
    # Initialize containerized anvil manager
    anvil_manager = AnvilContainerManager()
    
    # Test 1: Check initial status
    print("\n1. Checking initial status...")
    status = anvil_manager.get_status()
    print(f"   Status: {status}")
    
    # Test 2: Start forked anvil container
    print("\n2. Starting forked anvil container...")
    success = anvil_manager.start(fork_url="https://reth-ethereum.ithaca.xyz/rpc")
    print(f"   Start result: {success}")
    
    if success:
        # Test 3: Check if running
        print("\n3. Checking if anvil container is running...")
        is_running = anvil_manager.is_running()
        print(f"   Is running: {is_running}")
        
        # Test 4: Check status
        print("\n4. Checking container status...")
        status = anvil_manager.get_status()
        print(f"   Status: {status}")
        
        # Test 5: Test RPC connection
        print("\n5. Testing RPC connection...")
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
        
        # Test 6: Stop anvil container
        print("\n6. Stopping anvil container...")
        stop_success = anvil_manager.stop()
        print(f"   Stop result: {stop_success}")
        
        # Test 7: Final status check
        print("\n7. Final status check...")
        final_status = anvil_manager.get_status()
        print(f"   Final status: {final_status}")
    
    print("\n✅ Containerized anvil manager test completed!")

if __name__ == "__main__":
    test_anvil_container()
