import logging
import time
import docker
import redis
import json
import tarfile
import io
from docker.errors import DockerException, ImageNotFound, APIError
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
import threading
import shutil

logger = logging.getLogger(__name__)

class PersistentContainerManager:
    def __init__(self, redis_client: Optional[redis.Redis] = None, inactivity_timeout: int = 600):  # 10 minutes
        self.client = docker.from_env()
        self.redis_client = redis_client
        self.inactivity_timeout = inactivity_timeout
        self.containers = {}  # framework -> container info
        self.lock = threading.Lock()
        self.shutdown_timers = {}
        self.redis_prefix = "persistent-containers:"
        
    def get_or_start_container(self, framework: str, network_config: Optional[Dict] = None, anvil_container_name: Optional[str] = None) -> str:
        """Get existing container or start new one with pre-installed dependencies"""
        with self.lock:
            # Check if container already exists and is running
            if framework in self.containers:
                container_info = self.containers[framework]
                try:
                    container = self.client.containers.get(container_info['id'])
                    if container.status == 'running':
                        logger.info(f"Reusing existing {framework} container: {container.id[:12]}")
                        self._update_activity(framework)
                        return container.id
                except:
                    pass  # Container doesn't exist, will create new one
            
            # Start new container with pre-installed dependencies
            logger.info(f"Starting new {framework} container with pre-installed dependencies...")
            container_id = self._start_container(framework, network_config, anvil_container_name)
            self._update_activity(framework)
            return container_id
    
    def execute_command(self, framework: str, command: str, project_path: str, network_config: Optional[Dict] = None, anvil_container_name: Optional[str] = None) -> Dict[str, Any]:
        """Execute command in container with project copied and network awareness"""
        container_id = self.get_or_start_container(framework, network_config, anvil_container_name)
        
        try:
            start_time = time.time()
            container = self.client.containers.get(container_id)
            
            # Create project directory in container
            project_name = Path(project_path).name
            project_dir = f"/workspace/{project_name}"
            
            # Clean and create project directory
            container.exec_run(cmd=["rm", "-rf", project_dir], detach=False)
            container.exec_run(cmd=["mkdir", "-p", project_dir], detach=False)
            
            # Copy entire project to container using tar
            self._copy_project_to_container(container, project_path, project_dir)
            
            # Execute command in project directory
            logger.info(f"Executing in persistent container: {command}")
            result = container.exec_run(
                cmd=["sh", "-c", f"cd {project_dir} && {command}"],
                workdir=project_dir,
                detach=False
            )
            
            duration = time.time() - start_time
            
            # Update activity and save state to Redis
            self._update_activity(framework)
            self._save_container_state(framework, {
                'last_project': project_path,
                'last_command': command,
                'last_execution_time': duration
            })
            
            return {
                'status_code': result.exit_code,
                'stdout': result.output.decode('utf-8')[-2000:] if len(result.output) > 2000 else result.output.decode('utf-8'),
                'stderr': '',  # exec_run combines stdout/stderr
                'duration_seconds': duration,
                'container_reused': True
            }
            
        except Exception as e:
            logger.error(f"Failed to execute command in {framework} container: {e}")
            raise
    
    def _start_container(self, framework: str, network_config: Optional[Dict] = None, anvil_container_name: Optional[str] = None) -> str:
        """Start a new container with pre-installed dependencies and proper networking"""
        if framework == 'foundry':
            image_tag = "foundry-deployer:latest"
        elif framework == 'hardhat':
            image_tag = "hardhat-deployer:latest"
        else:
            raise ValueError(f"Unsupported framework: {framework}")
        
        # Determine network mode based on deployment type
        container_kwargs = {
            "image": image_tag,
            "command": ["tail", "-f", "/dev/null"],  # Keep container running
            "detach": True,
            "auto_remove": False,
            "working_dir": "/workspace"
        }
        
        # Add network configuration
        logger.info(f"Network config: {network_config}, Anvil container: {anvil_container_name}")
        if network_config and network_config.get("deployment_type") == "local" and anvil_container_name:
            # For local deployments with anvil, share network namespace
            container_kwargs["network_mode"] = f"container:{anvil_container_name}"
            logger.info(f"Using shared network namespace: container:{anvil_container_name}")
        elif network_config and network_config.get("deployment_type") == "local":
            # For local deployments without anvil, use deployer network
            container_kwargs["network"] = "deployer-network"
            logger.info("Using deployer-network for local deployment without anvil")
        else:
            logger.info("Using default network for remote deployment")
        # For remote deployments, use default network
        
        container = self.client.containers.run(**container_kwargs)
        
        # Store container info
        self.containers[framework] = {
            'id': container.id,
            'started_at': time.time(),
            'last_activity': time.time(),
            'network_config': network_config
        }
        
        # Save to Redis
        self._save_container_state(framework, self.containers[framework])
        
        logger.info(f"Started persistent {framework} container: {container.id[:12]}")
        return container.id
    
    def _update_activity(self, framework: str):
        """Update activity timestamp and reset shutdown timer"""
        if framework in self.containers:
            self.containers[framework]['last_activity'] = time.time()
        
        # Cancel existing shutdown timer
        if framework in self.shutdown_timers:
            self.shutdown_timers[framework].cancel()
        
        # Set new shutdown timer
        timer = threading.Timer(self.inactivity_timeout, self._auto_shutdown, args=[framework])
        timer.daemon = True
        timer.start()
        self.shutdown_timers[framework] = timer
    
    def _auto_shutdown(self, framework: str):
        """Auto-shutdown container after inactivity with state snapshot"""
        with self.lock:
            if framework in self.containers:
                container_info = self.containers[framework]
                if time.time() - container_info['last_activity'] >= self.inactivity_timeout:
                    logger.info(f"Auto-shutting down {framework} container after {self.inactivity_timeout}s of inactivity")
                    
                    # Take snapshot before shutdown
                    self._take_container_snapshot(framework)
                    self.stop_container(framework)
    
    def stop_container(self, framework: str) -> bool:
        """Stop and remove container"""
        with self.lock:
            if framework not in self.containers:
                return True
            
            try:
                container_id = self.containers[framework]['id']
                container = self.client.containers.get(container_id)
                
                logger.info(f"Stopping {framework} container: {container_id[:12]}")
                container.stop(timeout=10)
                container.remove()
                
                del self.containers[framework]
                
                # Cancel shutdown timer
                if framework in self.shutdown_timers:
                    self.shutdown_timers[framework].cancel()
                    del self.shutdown_timers[framework]
                
                logger.info(f"Stopped {framework} container")
                return True
                
            except Exception as e:
                logger.error(f"Failed to stop {framework} container: {e}")
                return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of all containers"""
        status = {}
        for framework, info in self.containers.items():
            try:
                container = self.client.containers.get(info['id'])
                status[framework] = {
                    'running': container.status == 'running',
                    'container_id': info['id'][:12],
                    'started_at': info['started_at'],
                    'last_activity': info['last_activity'],
                    'time_since_activity': time.time() - info['last_activity']
                }
            except:
                status[framework] = {'running': False, 'error': 'Container not found'}
        
        return status
    
    def cleanup_all(self):
        """Stop all containers"""
        for framework in list(self.containers.keys()):
            self.stop_container(framework)
    
    def _copy_project_to_container(self, container, project_path: str, container_path: str):
        """Copy entire project directory to container using tar"""
        try:
            # Create tar archive of project
            tar_stream = io.BytesIO()
            with tarfile.open(fileobj=tar_stream, mode='w') as tar:
                project_dir = Path(project_path)
                for file_path in project_dir.rglob('*'):
                    if file_path.is_file():
                        # Skip common ignore patterns but keep .git for foundry
                        if any(ignore in str(file_path) for ignore in ['node_modules', '.artifacts', 'cache']):
                            continue
                        arcname = file_path.relative_to(project_dir)
                        tar.add(file_path, arcname=arcname)
            
            tar_stream.seek(0)
            
            # Extract tar to container
            container.put_archive(container_path, tar_stream.getvalue())
            logger.info(f"Copied project {project_path} to container at {container_path}")
            
        except Exception as e:
            logger.error(f"Failed to copy project to container: {e}")
            raise
    
    def _save_container_state(self, framework: str, state: Dict[str, Any]):
        """Save container state to Redis"""
        if not self.redis_client:
            return
        
        try:
            key = f"{self.redis_prefix}{framework}"
            self.redis_client.setex(key, 7200, json.dumps(state, default=str))  # 2 hour TTL
        except Exception as e:
            logger.warning(f"Failed to save container state to Redis: {e}")
    
    def _load_container_state(self, framework: str) -> Optional[Dict[str, Any]]:
        """Load container state from Redis"""
        if not self.redis_client:
            return None
        
        try:
            key = f"{self.redis_prefix}{framework}"
            state_data = self.redis_client.get(key)
            if state_data:
                return json.loads(state_data)
        except Exception as e:
            logger.warning(f"Failed to load container state from Redis: {e}")
        return None
    
    def _take_container_snapshot(self, framework: str):
        """Take snapshot of container state before shutdown"""
        try:
            if framework in self.containers:
                container_info = self.containers[framework]
                container = self.client.containers.get(container_info['id'])
                
                # Commit container state as new image for faster restart
                snapshot_tag = f"{framework}-snapshot:{int(time.time())}"
                container.commit(repository=snapshot_tag.split(':')[0], tag=snapshot_tag.split(':')[1])
                
                # Save snapshot info to Redis
                snapshot_info = {
                    'snapshot_tag': snapshot_tag,
                    'created_at': time.time(),
                    'last_project': container_info.get('last_project', ''),
                    'framework': framework
                }
                
                if self.redis_client:
                    key = f"{self.redis_prefix}snapshot:{framework}"
                    self.redis_client.setex(key, 86400, json.dumps(snapshot_info, default=str))  # 24 hour TTL
                
                logger.info(f"Took snapshot of {framework} container: {snapshot_tag}")
                
        except Exception as e:
            logger.warning(f"Failed to take container snapshot: {e}")
    
    def get_persistent_stats(self) -> Dict[str, Any]:
        """Get statistics about persistent containers"""
        stats = {
            'active_containers': len(self.containers),
            'frameworks': list(self.containers.keys()),
            'redis_enabled': self.redis_client is not None,
            'containers': {}
        }
        
        for framework, info in self.containers.items():
            try:
                container = self.client.containers.get(info['id'])
                stats['containers'][framework] = {
                    'status': container.status,
                    'uptime_seconds': time.time() - info['started_at'],
                    'last_activity': info['last_activity'],
                    'inactivity_seconds': time.time() - info['last_activity']
                }
            except:
                stats['containers'][framework] = {'status': 'not_found'}
        
        return stats

# Global persistent container manager instance  
persistent_container_manager = PersistentContainerManager()
