#!/usr/bin/env python3
"""
Test script for network feature
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import time
import requests
from containers.network_manager import NetworkManager

def test_network_manager():
    print("🧪 Testing Network Manager...")
    
    # Initialize network manager
    network_manager = NetworkManager()
    
    # Test 1: List all networks
    print("\n1. Listing all networks...")
    networks = network_manager.list_networks()
    print(f"   Total networks: {networks['total_networks']}")
    print(f"   Default network: {networks['default_network']}")
    for network in networks['networks']:
        print(f"   - {network['network']}: {network['network_name']} (Chain ID: {network['chainID']})")
    
    # Test 2: Get specific network info
    print("\n2. Getting local network info...")
    local_info = network_manager.get_network_info("local")
    print(f"   Local network: {local_info}")
    
    # Test 3: Test deployment commands
    print("\n3. Testing deployment commands...")
    
    # Local network command
    local_cmd = network_manager.get_deployment_command("local", "script/Deploy.s.sol")
    print(f"   Local command: {local_cmd}")
    
    # Remote network command
    eth_cmd = network_manager.get_deployment_command("ETH_TESTNET", "script/Deploy.s.sol")
    print(f"   ETH_TESTNET command: {eth_cmd}")
    
    # Test 4: Validate networks
    print("\n4. Validating networks...")
    valid_networks = ["local", "ETH_TESTNET", "BASE_TESTNET", "BSC_TESTNET"]
    for network in valid_networks:
        is_valid = network_manager.validate_network(network)
        print(f"   {network}: {'✅ Valid' if is_valid else '❌ Invalid'}")
    
    # Test 5: Test invalid network
    print("\n5. Testing invalid network...")
    is_valid = network_manager.validate_network("INVALID_NETWORK")
    print(f"   INVALID_NETWORK: {'✅ Valid' if is_valid else '❌ Invalid'}")
    
    # Test 6: Check anvil requirements
    print("\n6. Checking anvil requirements...")
    for network in valid_networks:
        requires_anvil = network_manager.requires_anvil(network)
        print(f"   {network} requires anvil: {requires_anvil}")
    
    print("\n✅ Network manager test completed!")

def test_api_endpoints():
    print("\n🌐 Testing API Endpoints...")
    
    base_url = "http://localhost:5001"
    
    # Test networks endpoint
    print("\n1. Testing /networks endpoint...")
    try:
        response = requests.get(f"{base_url}/networks")
        if response.status_code == 200:
            networks = response.json()
            print(f"   ✅ Success: {networks['total_networks']} networks found")
            for network in networks['networks']:
                print(f"   - {network['network']}: {network['network_name']}")
        else:
            print(f"   ❌ Failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test specific network endpoint
    print("\n2. Testing /networks/local endpoint...")
    try:
        response = requests.get(f"{base_url}/networks/local")
        if response.status_code == 200:
            network_info = response.json()
            print(f"   ✅ Success: {network_info['network_name']} (Chain ID: {network_info['chainID']})")
        else:
            print(f"   ❌ Failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n✅ API endpoints test completed!")

if __name__ == "__main__":
    test_network_manager()
    test_api_endpoints()
