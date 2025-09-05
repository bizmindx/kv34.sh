#!/usr/bin/env python3
"""
Test for anvil auto-shutdown functionality
"""
import time
import requests
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from containers.node.anvil_manager import AnvilManager

def test_auto_shutdown():
    print("🧪 Testing Anvil Auto-Shutdown...")
    
    # Create anvil manager with short timeout for testing (10 seconds)
    test_anvil = AnvilManager(port=8546, inactivity_timeout=10)
    
    # Test 1: Start anvil
    print("\n1. Starting anvil with 10s auto-shutdown...")
    success = test_anvil.start()
    print(f"   Start result: {success}")
    
    if success:
        # Test 2: Check initial status
        print("\n2. Checking initial status...")
        status = test_anvil.get_status()
        print(f"   Status: {status}")
        
        # Test 3: Simulate activity (should reset timer)
        print("\n3. Simulating activity (should reset timer)...")
        time.sleep(2)
        test_anvil._update_activity()
        status = test_anvil.get_status()
        print(f"   Time since activity: {status['time_since_activity']:.1f}s")
        
        # Test 4: Wait for auto-shutdown
        print("\n4. Waiting for auto-shutdown (10s timeout)...")
        start_wait = time.time()
        while test_anvil.is_running() and (time.time() - start_wait) < 15:
            time.sleep(1)
            status = test_anvil.get_status()
            print(f"   Still running: {test_anvil.is_running()}, Time since activity: {status['time_since_activity']:.1f}s")
        
        # Test 5: Check if auto-shutdown worked
        print("\n5. Checking if auto-shutdown worked...")
        is_running = test_anvil.is_running()
        print(f"   Is running after timeout: {is_running}")
        
        if not is_running:
            print("   ✅ Auto-shutdown worked!")
        else:
            print("   ❌ Auto-shutdown failed")
        
        # Test 6: Test restart functionality
        print("\n6. Testing restart functionality...")
        restart_success = test_anvil.start()
        print(f"   Restart result: {restart_success}")
        
        if restart_success:
            print("   ✅ Restart worked!")
        else:
            print("   ❌ Restart failed")
        
        # Test 7: Cleanup
        print("\n7. Final cleanup...")
        test_anvil.stop()
    
    print("\n✅ Auto-shutdown test completed!")

def test_activity_reset():
    print("\n🔄 Testing Activity Reset...")
    
    # Create anvil manager with short timeout
    test_anvil = AnvilManager(port=8547, inactivity_timeout=5)
    
    # Start anvil
    test_anvil.start()
    
    # Simulate activity every 2 seconds (should prevent shutdown)
    print("Simulating activity every 2s (should prevent shutdown)...")
    for i in range(3):
        time.sleep(2)
        test_anvil._update_activity()
        status = test_anvil.get_status()
        print(f"   Activity {i+1}: Time since activity: {status['time_since_activity']:.1f}s")
    
    # Check if still running
    is_running = test_anvil.is_running()
    print(f"   Still running after activity: {is_running}")
    
    if is_running:
        print("   ✅ Activity reset prevented shutdown!")
    else:
        print("   ❌ Activity reset failed")
    
    # Cleanup
    test_anvil.stop()
    print("✅ Activity reset test completed!")

if __name__ == "__main__":
    test_auto_shutdown()
    test_activity_reset()
