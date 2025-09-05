#!/usr/bin/env python3
"""
Redis-based cache for Foundry container execution data
"""
import redis
import json
import hashlib
import logging
import time
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class FoundryCache:
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        self.cache_prefix = "kv-compiled:"
        self.cache_ttl = 3600  # 1 hour
        
    def get_cache_key(self, project_path: str, script_name: str, fork_url: str) -> str:
        """Generate cache key for foundry execution"""
        # Create hash from project files and parameters
        project_content = self._get_project_hash(project_path)
        params = f"{script_name}:{fork_url}"
        cache_input = f"{project_content}:{params}"
        return f"{self.cache_prefix}{hashlib.md5(cache_input.encode()).hexdigest()}"
    
    def get_cached_result(self, project_path: str, script_name: str, fork_url: str) -> Optional[Dict[str, Any]]:
        """Get cached execution result"""
        if not self.redis_client:
            return None
            
        try:
            cache_key = self.get_cache_key(project_path, script_name, fork_url)
            cached_data = self.redis_client.get(cache_key)
            
            if cached_data:
                logger.info(f"Found cached compiled result for {project_path}")
                cache_obj = json.loads(cached_data)
                return cache_obj.get("result")  # Return just the result data
            return None
            
        except Exception as e:
            logger.warning(f"Failed to get cached result: {e}")
            return None
    
    def cache_result(self, project_path: str, script_name: str, fork_url: str, result_data: Dict[str, Any], foundry_image_sha: str, hardhat_image_sha: str = ""):
        """Cache execution result with image SHAs"""
        if not self.redis_client:
            return
            
        try:
            cache_key = self.get_cache_key(project_path, script_name, fork_url)
            
            # Store with image SHA structure
            cache_data = {
                "foundry-image-sha": foundry_image_sha,
                "hardhat-image-sha": hardhat_image_sha,
                "result": result_data
            }
            
            self.redis_client.setex(cache_key, self.cache_ttl, json.dumps(cache_data))
            logger.info(f"Cached compiled result for {project_path}")
            
        except Exception as e:
            logger.warning(f"Failed to cache result: {e}")
    
    def _get_project_hash(self, project_path: str) -> str:
        """Generate hash of relevant project files"""
        try:
            project_dir = Path(project_path)
            hash_content = []
            
            # Hash foundry.toml if it exists
            foundry_toml = project_dir / "foundry.toml"
            if foundry_toml.exists():
                hash_content.append(foundry_toml.read_text())
            
            # Hash all .sol files in src/ and script/
            for pattern in ["src/**/*.sol", "script/**/*.sol"]:
                for sol_file in project_dir.glob(pattern):
                    if sol_file.is_file():
                        hash_content.append(f"{sol_file.relative_to(project_dir)}:{sol_file.read_text()}")
            
            combined_content = "\n".join(sorted(hash_content))
            return hashlib.md5(combined_content.encode()).hexdigest()
            
        except Exception as e:
            logger.warning(f"Failed to generate project hash: {e}")
            # Fallback to path + timestamp
            return f"{project_path}_{int(time.time())}"
    
    def clear_cache(self, pattern: Optional[str] = None):
        """Clear foundry cache entries"""
        if not self.redis_client:
            return
            
        try:
            search_pattern = f"{self.cache_prefix}*" if not pattern else f"{self.cache_prefix}{pattern}*"
            keys = self.redis_client.keys(search_pattern)
            
            if keys:
                self.redis_client.delete(*keys)
                logger.info(f"Cleared {len(keys)} foundry cache entries")
            else:
                logger.info("No foundry cache entries to clear")
                
        except Exception as e:
            logger.warning(f"Failed to clear foundry cache: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get foundry cache statistics"""
        if not self.redis_client:
            return {"cached_compilations": 0, "cache_enabled": False}
        
        try:
            pattern = f"{self.cache_prefix}*"
            keys = self.redis_client.keys(pattern)
            
            return {
                "cached_compilations": len(keys),
                "cache_enabled": True,
                "cache_ttl_seconds": self.cache_ttl
            }
            
        except Exception as e:
            logger.warning(f"Failed to get cache stats: {e}")
            return {"cached_compilations": 0, "cache_enabled": False, "error": str(e)}