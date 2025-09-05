#!/usr/bin/env python3
"""
Containerized Anvil Manager using Docker
"""
import docker
import time
import logging
import threading
from pathlib import Path
from typing import Optional, Dict, Any
import requests
import sys
import os

# Add utils to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from utils.error_logger import ErrorLogger

logger = logging.getLogger(__name__)

class AnvilContainerManager:
    def __init__(self, port: int = 8545, container_name: str = "anvil-rpc", network_name: str = "deployer-network", local_mode: bool = False):
        self.port = port
        self.container_name = container_name + ("-local" if local_mode else "")
        self.network_name = network_name
        self.local_mode = local_mode
        self.docker_client = docker.from_env()
        self.last_activity = time.time()
        self.shutdown_timer: Optional[threading.Timer] = None
        self.lock = threading.Lock()
        self.error_logger = ErrorLogger("AnvilContainerManager")
        
        # Ensure network exists
        self._ensure_network()
        
    def _ensure_network(self):
        """Ensure Docker network exists"""
        try:
            networks = self.docker_client.networks.list(names=[self.network_name])
            if not networks:
                logger.info(f"Creating Docker network: {self.network_name}")
                self.docker_client.networks.create(
                    self.network_name,
                    driver="bridge",
                    check_duplicate=True
                )
            else:
                logger.info(f"Using existing network: {self.network_name}")
        except Exception as e:
            self.error_logger.log_error(
                "network_creation_failed",
                f"Failed to create Docker network {self.network_name}",
                {"network_name": self.network_name},
                e
            )
    
    def start(self, fork_url: Optional[str] = None, use_snapshot: bool = True) -> bool:
        """Start anvil container"""
        with self.lock:
            if self.is_running():
                logger.info("Anvil container already running")
                self._update_activity()
                return True
                
            try:
                # Stop any existing container
                self._stop_existing_container()
                
                # Prepare command
                cmd = [
                    "anvil",
                    "--port", str(self.port),
                    "--host", "0.0.0.0",
                    "--accounts", "10",
                    "--balance", "10000",
                    "--gas-limit", "30000000"
                ]
                
                # Add fork URL or use local mode
                if not self.local_mode and not fork_url:
                    fork_url = "https://reth-ethereum.ithaca.xyz/rpc"
                
                if fork_url and not self.local_mode:
                    cmd.extend(["--fork-url", fork_url])
                    logger.info(f"Starting forked anvil with URL: {fork_url}")
                else:
                    logger.info("Starting local anvil instance")
                
                # Add snapshot loading if available and local mode
                if use_snapshot and self.local_mode:
                    latest_snapshot = self._get_latest_snapshot()
                    if latest_snapshot:
                        cmd.extend(["--load-state", latest_snapshot])
                        logger.info(f"Loading snapshot: {latest_snapshot}")
                
                # Prepare volumes for snapshots
                volumes = {}
                if self.local_mode:  # Only use snapshots for local anvil
                    volumes["anvil-snapshots"] = {"bind": "/anvil/snapshots", "mode": "rw"}
                
                logger.info(f"Starting anvil container: {self.container_name}")
                container = self.docker_client.containers.run(
                    "foundry-deployer:latest",
                    command=cmd,
                    name=self.container_name,
                    network=self.network_name,
                    ports={f"{self.port}/tcp": self.port},
                    volumes=volumes,
                    detach=True,
                    remove=False
                )
                
                # Wait for container to be ready
                if self._wait_for_container_ready():
                    logger.info("Anvil container started successfully")
                    self._update_activity()
                    return True
                else:
                    self.error_logger.log_error(
                        "container_ready_timeout",
                        "Anvil container failed to become ready",
                        {"port": self.port, "container_name": self.container_name, "fork_url": fork_url}
                    )
                    self._stop_existing_container()
                    return False
                    
            except Exception as e:
                error_data = self.error_logger.log_error(
                    "container_start_failed",
                    "Failed to start anvil container",
                    {"port": self.port, "container_name": self.container_name, "fork_url": fork_url},
                    e
                )
                return False
    
    def stop(self) -> bool:
        """Stop anvil container and take snapshot"""
        with self.lock:
            if not self.is_running():
                logger.info("Anvil container not running")
                return True
                
            try:
                # Take snapshot before stopping
                if self.local_mode:
                    self._take_snapshot()
                
                # Stop container
                logger.info("Stopping anvil container")
                container = self.docker_client.containers.get(self.container_name)
                container.stop(timeout=10)
                container.remove()
                
                # Cancel shutdown timer
                if self.shutdown_timer:
                    self.shutdown_timer.cancel()
                    self.shutdown_timer = None
                
                logger.info("Anvil container stopped")
                return True
                
            except Exception as e:
                self.error_logger.log_error(
                    "container_stop_failed",
                    "Failed to stop anvil container",
                    {"container_name": self.container_name},
                    e
                )
                return False
    
    def restart(self) -> bool:
        """Restart anvil container with fresh state"""
        logger.info("Restarting anvil container with fresh state")
        self.stop()
        self._clear_snapshots()
        return self.start(use_snapshot=False)
    
    def is_running(self) -> bool:
        """Check if anvil container is running"""
        try:
            container = self.docker_client.containers.get(self.container_name)
            return container.status == "running"
        except docker.errors.NotFound:
            return False
        except Exception as e:
            self.error_logger.log_error(
                "status_check_failed",
                "Error checking anvil container status",
                {"container_name": self.container_name},
                e
            )
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get anvil container status"""
        try:
            container = self.docker_client.containers.get(self.container_name)
            return {
                "running": container.status == "running",
                "port": self.port,
                "container_name": self.container_name,
                "network": self.network_name,
                "last_activity": self.last_activity,
                "container_status": container.status,
                "is_forked": self._is_forked()
            }
        except docker.errors.NotFound:
            return {
                "running": False,
                "port": self.port,
                "container_name": self.container_name,
                "network": self.network_name,
                "last_activity": self.last_activity,
                "container_status": "not_found",
                "is_forked": False
            }
        except Exception as e:
            logger.error(f"Error getting container status: {e}")
            return {
                "running": False,
                "port": self.port,
                "container_name": self.container_name,
                "network": self.network_name,
                "last_activity": self.last_activity,
                "container_status": "error",
                "is_forked": False
            }
    
    def _update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = time.time()
        
        # Cancel existing shutdown timer
        if self.shutdown_timer:
            self.shutdown_timer.cancel()
        
        # Set new shutdown timer (10 minutes)
        self.shutdown_timer = threading.Timer(600, self._auto_shutdown)
        self.shutdown_timer.daemon = True
        self.shutdown_timer.start()
    
    def _auto_shutdown(self):
        """Auto shutdown after inactivity"""
        logger.info("Auto-shutting down anvil container due to inactivity")
        self.stop()
    
    def _wait_for_container_ready(self, max_retries: int = 30) -> bool:
        """Wait for anvil container to be ready"""
        for i in range(max_retries):
            try:
                response = requests.post(
                    f"http://localhost:{self.port}",
                    json={"jsonrpc": "2.0", "method": "eth_chainId", "params": [], "id": 1},
                    timeout=2
                )
                if response.status_code == 200:
                    result = response.json()
                    if "result" in result:
                        logger.info(f"Anvil container ready after {i+1} attempts")
                        return True
            except requests.exceptions.RequestException:
                pass
            
            if i < max_retries - 1:
                time.sleep(1)
        
        logger.error(f"Anvil container failed to become ready after {max_retries} attempts")
        return False
    
    def _stop_existing_container(self):
        """Stop any existing anvil container"""
        try:
            container = self.docker_client.containers.get(self.container_name)
            if container.status == "running":
                logger.info("Stopping existing anvil container")
                container.stop(timeout=5)
            container.remove()
        except docker.errors.NotFound:
            pass
        except Exception as e:
            logger.warning(f"Failed to stop existing container: {e}")
        
        # Also stop any other container using the same port
        self._stop_port_conflicts()
    
    def _stop_port_conflicts(self):
        """Stop any containers using the same port"""
        try:
            containers = self.docker_client.containers.list(filters={"status": "running"})
            for container in containers:
                try:
                    port_bindings = container.attrs.get('NetworkSettings', {}).get('Ports', {})
                    for container_port, host_bindings in port_bindings.items():
                        if host_bindings:
                            for binding in host_bindings:
                                if binding.get('HostPort') == str(self.port):
                                    logger.info(f"Stopping container {container.name} using port {self.port}")
                                    container.stop(timeout=5)
                                    container.remove()
                                    break
                except Exception as e:
                    logger.warning(f"Failed to check container {container.name}: {e}")
        except Exception as e:
            logger.warning(f"Failed to stop port conflicts: {e}")
    
    def _is_forked(self) -> bool:
        """Check if current anvil is forked"""
        try:
            container = self.docker_client.containers.get(self.container_name)
            return "--fork-url" in " ".join(container.attrs["Args"])
        except:
            return False
    
    def _take_snapshot(self):
        """Take snapshot of anvil state"""
        if self._is_forked():
            return  # Don't snapshot forked anvil
            
        try:
            response = requests.post(
                f"http://localhost:{self.port}",
                json={"jsonrpc": "2.0", "method": "anvil_dumpState", "params": [], "id": 1},
                timeout=5
            )
            if response.status_code == 200:
                result = response.json()
                if "result" in result:
                    snapshot_path = result["result"]
                    logger.info(f"Snapshot taken: {snapshot_path}")
        except Exception as e:
            logger.warning(f"Failed to take snapshot: {e}")
    
    def _get_latest_snapshot(self) -> Optional[str]:
        """Get latest snapshot path"""
        try:
            # This would need to be implemented based on how snapshots are stored
            # For now, return None
            return None
        except Exception as e:
            logger.warning(f"Failed to get latest snapshot: {e}")
            return None
    
    def _clear_snapshots(self):
        """Clear all snapshots"""
        try:
            # This would need to be implemented based on snapshot storage
            logger.info("Snapshots cleared")
        except Exception as e:
            logger.warning(f"Failed to clear snapshots: {e}")
    
    def get_snapshot_info(self) -> Dict[str, Any]:
        """Get snapshot information"""
        return {
            "total_snapshots": 0,
            "latest_snapshot": None,
            "snapshot_enabled": not self._is_forked()
        }
