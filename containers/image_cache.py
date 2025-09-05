#!/usr/bin/env python3
"""
Docker image caching using Redis
"""
import docker
import redis
import os
import logging
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

class ImageCache:
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.docker_client = docker.from_env()
        self.redis_client = redis_client
        self.cache_prefix = "kv34-images:"
        
    def get_or_build_image(self, dockerfile_path: str, image_tag: str, build_context: str = ".") -> Tuple[bool, str]:
        """
        Get existing image or build new one, using Redis for caching
        
        Returns:
            Tuple[bool, str]: (was_cached, image_id)
        """
        try:
            # Check if image exists in Docker
            existing_images = self.docker_client.images.list(name=image_tag)
            if existing_images:
                logger.info(f"Image {image_tag} already exists in Docker")
                if self.redis_client:
                    self._cache_image_info(image_tag, existing_images[0].id)
                return True, existing_images[0].id
            
            # Check Redis cache
            if self.redis_client and self._is_cached(image_tag):
                logger.info(f"Image {image_tag} found in Redis cache")
                return True, self._get_cached_image_id(image_tag)
            
            # Build new image
            logger.info(f"Building new image {image_tag} from {dockerfile_path}")
            image, logs = self.docker_client.images.build(
                path=build_context,
                dockerfile=dockerfile_path,
                tag=image_tag,
                rm=True
            )
            
            # Cache the new image
            if self.redis_client:
                self._cache_image_info(image_tag, image.id)
            
            logger.info(f"Successfully built and cached image {image_tag}")
            return False, image.id
            
        except Exception as e:
            logger.error(f"Failed to get or build image {image_tag}: {e}")
            raise
    
    def _is_cached(self, image_tag: str) -> bool:
        """Check if image is cached in Redis"""
        if not self.redis_client:
            return False
        return self.redis_client.exists(f"{self.cache_prefix}{image_tag}")
    
    def _get_cached_image_id(self, image_tag: str) -> str:
        """Get cached image ID from Redis"""
        if not self.redis_client:
            return ""
        return self.redis_client.get(f"{self.cache_prefix}{image_tag}").decode('utf-8')
    
    def _cache_image_info(self, image_tag: str, image_id: str):
        """Cache image info in Redis"""
        if not self.redis_client:
            return
        key = f"{self.cache_prefix}{image_tag}"
        self.redis_client.set(key, image_id, ex=3600)  # Cache for 1 hour
    
    def clear_cache(self, image_tag: Optional[str] = None):
        """Clear image cache from Redis"""
        if not self.redis_client:
            return
            
        if image_tag:
            key = f"{self.cache_prefix}{image_tag}"
            self.redis_client.delete(key)
            logger.info(f"Cleared cache for image {image_tag}")
        else:
            # Clear all image cache
            pattern = f"{self.cache_prefix}*"
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
                logger.info(f"Cleared all image cache ({len(keys)} entries)")
    
    def get_cache_stats(self) -> dict:
        """Get cache statistics"""
        if not self.redis_client:
            return {"cached_images": 0, "cache_enabled": False}
        
        pattern = f"{self.cache_prefix}*"
        keys = self.redis_client.keys(pattern)
        
        return {
            "cached_images": len(keys),
            "cache_enabled": True,
            "cached_image_tags": [key.decode('utf-8').replace(self.cache_prefix, '') for key in keys]
        }
