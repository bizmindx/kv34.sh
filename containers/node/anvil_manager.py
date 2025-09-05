import subprocess
import time
import threading
import json
import logging
import requests
from pathlib import Path
from typing import Optional, Dict, Any
import docker

logger = logging.getLogger(__name__)

class AnvilManager:
    def __init__(self, port: int = 8545, inactivity_timeout: int = 600):
        self.port = port
        self.inactivity_timeout = inactivity_timeout
        self.process: Optional[subprocess.Popen] = None
        self.last_activity = time.time()
        self.shutdown_timer: Optional[threading.Timer] = None
        self.lock = threading.Lock()
        self.snapshots_dir = Path("anvil_snapshots")
        self.snapshots_dir.mkdir(exist_ok=True)
        
    def start(self, use_snapshot: bool = True) -> bool:
        """Start anvil if not already running"""
        with self.lock:
            if self.process and self.process.poll() is None:
                logger.info("Anvil already running")
                self._update_activity()
                return True
                
            try:
                # Kill any existing anvil process on this port
                self._kill_existing_anvil()
                
                # Check for latest snapshot to restore
                latest_snapshot = self._get_latest_snapshot() if use_snapshot else None
                
                # Start new anvil instance
                cmd = [
                    "anvil",
                    "--fork-url", "https://reth-ethereum.ithaca.xyz/rpc"
                    # "--balance", "10000",
                    # "--gas-limit", "30000000"
                ]
                
                # Add snapshot restoration if available
                if latest_snapshot:
                    cmd.extend(["--load-state", str(latest_snapshot)])
                    logger.info(f"Restoring from snapshot: {latest_snapshot}")
                else:
                    logger.info("Starting fresh anvil instance")
                
                logger.info(f"Starting anvil on port {self.port}")
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                # Wait for anvil to be ready
                if self._wait_for_anvil():
                    logger.info("Anvil started successfully")
                    self._update_activity()
                    return True
                else:
                    logger.error("Anvil failed to start")
                    return False
                    
            except Exception as e:
                logger.error(f"Failed to start anvil: {e}")
                return False
    
    def stop(self) -> bool:
        """Stop anvil and take snapshot"""
        with self.lock:
            if not self.process or self.process.poll() is not None:
                logger.info("Anvil not running")
                return True
                
            try:
                # Take snapshot before stopping
                self._take_snapshot()
                
                # Stop anvil
                logger.info("Stopping anvil")
                # self.process.terminate()
                
                # Wait for graceful shutdown
                try:
                    self.process.wait(timeout=100)
                except subprocess.TimeoutExpired:
                    logger.warning("Anvil didn't stop gracefully, forcing kill")
                    self.process.kill()
                    self.process.wait()
                
                self.process = None
                
                # Cancel shutdown timer
                if self.shutdown_timer:
                    self.shutdown_timer.cancel()
                    self.shutdown_timer = None
                
                logger.info("Anvil stopped")
                return True
                
            except Exception as e:
                logger.error(f"Failed to stop anvil: {e}")
                return False
    
    def restart(self) -> bool:
        """Restart anvil with fresh state (no snapshot)"""
        logger.info("Restarting anvil with fresh state")
        self.stop()
        return self.start(use_snapshot=False)
    
    def is_running(self) -> bool:
        """Check if anvil is running and responding"""
        if not self.process or self.process.poll() is not None:
            return False
            
        try:
            response = requests.post(
                f"http://localhost:{self.port}",
                json={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1},
                timeout=5
            )
            return response.status_code == 200
        except:
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get current anvil status"""
        return {
            "running": self.is_running(),
            "port": self.port,
            "last_activity": self.last_activity,
            "inactivity_timeout": self.inactivity_timeout,
            "time_since_activity": time.time() - self.last_activity
        }
    
    def _update_activity(self):
        """Update last activity time and reset shutdown timer"""
        self.last_activity = time.time()
        
        # Cancel existing shutdown timer
        if self.shutdown_timer:
            self.shutdown_timer.cancel()
        
        # Set new shutdown timer
        self.shutdown_timer = threading.Timer(self.inactivity_timeout, self._auto_shutdown)
        self.shutdown_timer.daemon = True
        self.shutdown_timer.start()
    
    def _auto_shutdown(self):
        """Auto-shutdown after inactivity"""
        with self.lock:
            if time.time() - self.last_activity >= self.inactivity_timeout:
                logger.info(f"Auto-shutting down anvil after {self.inactivity_timeout}s of inactivity")
                self.stop()
    
    def _wait_for_anvil(self, timeout: int = 100) -> bool:
        """Wait for anvil to be ready"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.is_running():
                return True
            time.sleep(1)
        return False
    
    def _kill_existing_anvil(self):
        """Kill any existing anvil process on this port"""
        try:
            subprocess.run(["pkill", "-f", f"anvil.*--port.*{self.port}"], 
                         capture_output=True, timeout=5)
        except:
            pass
    
    def _take_snapshot(self):
        """Take a snapshot of current anvil state"""
        try:
            timestamp = int(time.time())
            snapshot_file = self.snapshots_dir / f"snapshot_{timestamp}.json"
            
            # Get current state via RPC
            response = requests.post(
                f"http://localhost:{self.port}",
                json={"jsonrpc": "2.0", "method": "anvil_dumpState", "params": [], "id": 1},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if "result" in data:
                    with open(snapshot_file, 'w') as f:
                        json.dump(data["result"], f, indent=2)
                    logger.info(f"Snapshot saved: {snapshot_file}")
                    
                    # Keep only last 5 snapshots
                    snapshots = sorted(self.snapshots_dir.glob("snapshot_*.json"))
                    if len(snapshots) > 5:
                        for old_snapshot in snapshots[:-5]:
                            old_snapshot.unlink()
                            logger.info(f"Removed old snapshot: {old_snapshot}")
                            
        except Exception as e:
            logger.warning(f"Failed to take snapshot: {e}")
    
    def _get_latest_snapshot(self) -> Optional[Path]:
        """Get the most recent snapshot file"""
        try:
            snapshots = list(self.snapshots_dir.glob("snapshot_*.json"))
            if snapshots:
                # Sort by timestamp (newest first)
                latest = max(snapshots, key=lambda p: p.stat().st_mtime)
                logger.info(f"Found latest snapshot: {latest}")
                return latest
            else:
                logger.info("No snapshots found, starting fresh")
                return None
        except Exception as e:
            logger.warning(f"Failed to get latest snapshot: {e}")
            return None
    
    def clear_snapshots(self):
        """Delete all snapshots"""
        try:
            snapshots = list(self.snapshots_dir.glob("snapshot_*.json"))
            for snapshot in snapshots:
                snapshot.unlink()
                logger.info(f"Deleted snapshot: {snapshot}")
            logger.info(f"Cleared {len(snapshots)} snapshots")
        except Exception as e:
            logger.error(f"Failed to clear snapshots: {e}")
    
    def get_snapshot_info(self) -> Dict[str, Any]:
        """Get information about available snapshots"""
        try:
            snapshots = list(self.snapshots_dir.glob("snapshot_*.json"))
            snapshot_info = []
            
            for snapshot in sorted(snapshots, key=lambda p: p.stat().st_mtime, reverse=True):
                stat = snapshot.stat()
                snapshot_info.append({
                    "filename": snapshot.name,
                    "size_bytes": stat.st_size,
                    "created_time": stat.st_mtime,
                    "created_date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))
                })
            
            return {
                "total_snapshots": len(snapshots),
                "snapshots": snapshot_info
            }
        except Exception as e:
            logger.warning(f"Failed to get snapshot info: {e}")
            return {"total_snapshots": 0, "snapshots": []}

# Global anvil manager instance
anvil_manager = AnvilManager()
