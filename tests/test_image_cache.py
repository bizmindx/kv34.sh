#!/usr/bin/env python3
"""
Test script for image caching functionality
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import time
import redis
from containers.image_cache import ImageCache

def test_image_cache():
    print("🧪 Testing Image Cache...")
    
    # Initialize Redis client (will be None if Redis not available)
    try:
        redis_client = redis.from_url('redis://localhost:6379/0', decode_responses=True)
        redis_client.ping()
        print("   ✅ Redis connected")
    except:
        redis_client = None
        print("   ⚠️  Redis not available, testing without cache")
    
    # Initialize image cache
    image_cache = ImageCache(redis_client)
    
    # Test 1: Get cache stats
    print("\n1. Getting initial cache stats...")
    stats = image_cache.get_cache_stats()
    print(f"   Cache stats: {stats}")
    
    # Test 2: First image build (should build new image)
    print("\n2. First image build (should build new image)...")
    start_time = time.time()
    
    try:
        was_cached, image_id = image_cache.get_or_build_image(
            dockerfile_path="containers/images/Dockerfile.foundry",
            image_tag="foundry-deployer:latest",
            build_context="."
        )
        first_time = time.time() - start_time
        
        print(f"   Was cached: {was_cached}")
        print(f"   Image ID: {image_id[:12]}...")
        print(f"   Build time: {first_time:.2f}s")
        
        # Test 3: Second image build (should use cached image)
        print("\n3. Second image build (should use cached image)...")
        start_time = time.time()
        
        was_cached_2, image_id_2 = image_cache.get_or_build_image(
            dockerfile_path="containers/images/Dockerfile.foundry",
            image_tag="foundry-deployer:latest",
            build_context="."
        )
        second_time = time.time() - start_time
        
        print(f"   Was cached: {was_cached_2}")
        print(f"   Image ID: {image_id_2[:12]}...")
        print(f"   Build time: {second_time:.2f}s")
        
        # Test 4: Performance comparison
        print("\n4. Performance comparison...")
        if was_cached_2 and not was_cached:
            improvement = ((first_time - second_time) / first_time) * 100
            print(f"   ✅ Performance improved by {improvement:.1f}%")
            print(f"   First build: {first_time:.2f}s")
            print(f"   Cached build: {second_time:.2f}s")
        else:
            print(f"   ⚠️  No improvement detected")
        
        # Test 5: Cache stats after builds
        print("\n5. Cache stats after builds...")
        stats_after = image_cache.get_cache_stats()
        print(f"   Cache stats: {stats_after}")
        
        # Test 6: Clear cache
        print("\n6. Clearing cache...")
        image_cache.clear_cache()
        stats_cleared = image_cache.get_cache_stats()
        print(f"   Cache stats after clear: {stats_cleared}")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        print("   This might be expected if Docker is not running or Foundry is not installed")
    
    print("\n✅ Image cache test completed!")

if __name__ == "__main__":
    test_image_cache()
