#!/usr/bin/env python3
"""
Network Manager for Foundry deployments
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class NetworkManager:
    def __init__(self, config_path: str = "config/network.json"):
        self.config_path = Path(config_path)
        self.networks = {}
        self.default_network = "local"
        self.load_networks()
    
    def load_networks(self):
        """Load network configuration from JSON file"""
        try:
            if not self.config_path.exists():
                logger.error(f"Network config file not found: {self.config_path}")
                return
            
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            # Load networks into dictionary for easy lookup
            for network in config.get("networks", []):
                self.networks[network["network"]] = network
            
            self.default_network = config.get("default_network", "local")
            logger.info(f"Loaded {len(self.networks)} networks, default: {self.default_network}")
            
        except Exception as e:
            logger.error(f"Failed to load network configuration: {e}")
    
    def get_network(self, network_name: str) -> Optional[Dict[str, Any]]:
        """Get network configuration by name"""
        return self.networks.get(network_name)
    
    def get_all_networks(self) -> Dict[str, Any]:
        """Get all available networks"""
        return self.networks
    
    def get_default_network(self) -> Dict[str, Any]:
        """Get default network configuration"""
        return self.networks.get(self.default_network)
    
    def validate_network(self, network_name: str) -> bool:
        """Validate if network exists"""
        return network_name in self.networks
    
    def get_deployment_command(self, network_name: str, script_path: str = "script/Deploy.s.sol", fork: bool = False) -> str:
        """Generate deployment command based on network type and fork parameter for containerized execution"""
        network = self.get_network(network_name)
        if not network:
            logger.error(f"Network not found: {network_name}")
            return ""
        
        if network["deployment_type"] == "local":
            # the --fork-url is not needed for local network
            # Local network: use localhost for container-to-container communication
            return f"forge script {script_path}  --broadcast"
        else:
            # Remote network: direct forge script with rpc-url (containerized)
            return f"forge script {script_path} --rpc-url {network['rpc_url']} --broadcast"
    
    def requires_anvil(self, network_name: str) -> bool:
        """Check if network requires anvil startup"""
        network = self.get_network(network_name)
        return network.get("requires_anvil", False) if network else False
    
    def get_network_info(self, network_name: str) -> Dict[str, Any]:
        """Get network information for API responses"""
        network = self.get_network(network_name)
        if not network:
            return {}
        
        return {
            "network": network["network"],
            "network_name": network["network_name"],
            "chainID": network["chainID"],
            "description": network["description"],
            "deployment_type": network["deployment_type"],
            "requires_anvil": network["requires_anvil"]
        }
    
    def list_networks(self) -> Dict[str, Any]:
        """List all available networks"""
        return {
            "networks": [self.get_network_info(name) for name in self.networks.keys()],
            "default_network": self.default_network,
            "total_networks": len(self.networks)
        }
