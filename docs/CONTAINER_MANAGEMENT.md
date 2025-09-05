# Container Management System

## Overview

The deployer includes an intelligent container management system with multi-network support that efficiently reuses Docker images and containers for both local and remote blockchain deployments.

## Problem Solved

### ❌ **Previous Behavior (Inefficient)**
```
Every Request → Build Image (30-60s) → Create Container → Run → Destroy Container
```

### ✅ **New Behavior (Efficient)**
```
First Request → Build Image (30-60s) → Create Container → Run → Keep for Reuse
Subsequent Requests → Reuse Image (0-1s) → Reuse Container → Run → Keep for Reuse
```

## Key Features

### 🚀 **Image Caching**
- **Redis-backed caching**: Uses Redis for distributed image cache management
- **Smart detection**: Checks if image already exists before building
- **Cache tracking**: Maintains cache of recently built images with metadata
- **Auto-cleanup**: Removes old cached images after 24 hours

### 🌐 **Network Management**
- **Multi-network support**: Local (anvil) and remote (testnet/mainnet) deployments
- **Container networking**: Proper Docker network isolation and communication
- **Fork support**: Local anvil with/without mainnet forking
- **RPC configuration**: Dynamic RPC URL selection from network.json

### 🔄 **Container Orchestration**
- **Anvil containers**: Separate containers for local and forked anvil instances
- **Network isolation**: Uses `deployer-network` for container communication
- **Shared namespaces**: Container-to-container communication via shared network
- **Resource optimization**: Reduces container creation/destruction overhead

### 📊 **Performance Monitoring**
- **Cache statistics**: Redis-based image and execution caching
- **Network metrics**: Track deployments by network type
- **Resource tracking**: Monitor running containers and cached images

## Performance Improvements

### **Build Time Reduction**
- **First build**: 30-60 seconds (normal)
- **Subsequent builds**: 0-1 seconds (cached)
- **Improvement**: 95-98% faster subsequent builds

### **Resource Efficiency**
- **Reduced CPU usage**: No repeated image building
- **Reduced disk I/O**: Reuse existing layers
- **Reduced memory**: Fewer container creation/destruction cycles

## API Endpoints

### GET `/admin/server/cache/status`
Get Docker image cache statistics:
```json
{
  "cached_images": 2,
  "cache_enabled": true,
  "cached_image_tags": [
    "foundry-deployer:latest",
    "hardhat-deployer:latest"
  ]
}
```

### POST `/admin/server/cache/clear`
Clear Docker image cache:
```json
{
  "success": true,
  "message": "Cleared all image cache"
}
```

### GET `/admin/server/foundry-cache/status`
Get Foundry execution cache statistics:
```json
{
  "cached_compilations": 5,
  "cache_enabled": true,
  "cache_ttl_seconds": 3600
}
```

### POST `/admin/server/foundry-cache/clear`
Clear Foundry execution cache:
```json
{
  "success": true,
  "message": "Cleared all foundry cache"
}
```

## How It Works

### 1. **Network-Aware Deployment**
```
Request → Validate Network → Start Anvil (if local) → Deploy in Container → Cache Results
```

### 2. **Container Orchestration**
```
Local Networks: Anvil Container + Forge Container (shared network namespace)
Remote Networks: Forge Container (direct RPC)
```

### 3. **Container Communication**
- **Local deployments**: Containers share network namespace, use `localhost:8545`
- **Remote deployments**: Direct RPC communication to external networks
- **Network isolation**: All containers use `deployer-network` for isolation

## Configuration

### Environment Variables
- `CONTAINER_CACHE_MAX_AGE`: Maximum age for cached images (default: 24 hours)
- `CONTAINER_REUSE_ENABLED`: Enable/disable container reuse (default: true)

### Cache Management
- **Image cache**: Tracks recently built images with timestamps
- **Auto-cleanup**: Removes images older than 24 hours
- **Manual cleanup**: Available via API endpoint

## Usage Examples

### Check Container Stats
```bash
curl http://localhost:5001/containers/stats
```

### Clean Up Old Containers
```bash
curl -X POST http://localhost:5001/containers/cleanup
```

### Monitor Performance
```bash
# First deployment (slow)
time curl -X POST http://localhost:5001/deploy \
  -H "Content-Type: application/json" \
  -d '{"path_url": "./project", "framework": "foundry"}'

# Second deployment (fast - reuses image)
time curl -X POST http://localhost:5001/deploy \
  -H "Content-Type: application/json" \
  -d '{"path_url": "./project2", "framework": "foundry"}'
```

## Benefits

### ✅ **Performance**
- **95-98% faster** subsequent builds
- **Reduced wait times** for developers
- **Better user experience** with faster responses

### ✅ **Resource Efficiency**
- **Less CPU usage** from repeated builds
- **Reduced disk space** from image reuse
- **Lower memory footprint** from container reuse

### ✅ **Developer Experience**
- **Transparent operation** - no configuration needed
- **Automatic optimization** - works out of the box
- **Monitoring tools** - track performance improvements

## Troubleshooting

### Images Not Being Reused
1. Check if Docker images exist: `docker images`
2. Verify cache is working: `GET /containers/stats`
3. Check for image conflicts or naming issues

### Containers Not Being Reused
1. Verify container reuse is enabled
2. Check if containers are running: `docker ps`
3. Ensure same image and command are being used

### Performance Issues
1. Monitor build times in logs
2. Check container stats for cache hit rates
3. Run cleanup if cache is too large

## Testing

Run the test script to verify functionality:
```bash
python test_container_reuse.py
```

This will test:
- Image caching behavior
- Container reuse logic
- Performance improvements
- API endpoints

## Migration from Old System

The new system is **backward compatible**:
- ✅ Existing deployments continue to work
- ✅ No configuration changes required
- ✅ Automatic performance improvements
- ✅ Gradual migration as images are built

**No action required** - the system automatically optimizes performance!
