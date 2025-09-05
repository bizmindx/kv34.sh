# Anvil Management System

## Overview

The deployer includes an intelligent containerized anvil management system that automatically handles local blockchain instances with fork support and multi-network deployment capabilities.

## Features

### 🚀 **Dual Anvil Architecture**
- **Local anvil** (`anvil-local`): State persistence with snapshots for development
- **Forked anvil** (`anvil-local-fork`): Mainnet forking without snapshots for testing
- **Auto-start**: Appropriate anvil type starts automatically based on `fork` parameter
- **Auto-shutdown**: Shuts down after 10 minutes of inactivity with state preservation

### 🌐 **Network Support**
- **Local networks**: Uses containerized anvil with `localhost:8545` communication
- **Remote networks**: Direct RPC to external networks (Sepolia, Base, BSC testnets)
- **Fork parameter**: `fork=false` (default) uses persistent anvil, `fork=true` uses forked anvil
- **Container networking**: Shared network namespace for container-to-container communication

### 🔧 **Smart State Management**
- **Snapshot persistence**: Only for non-forked local anvil (`fork=false`)
- **Activity tracking**: Resets shutdown timer on each deployment
- **Graceful shutdown**: Takes snapshots before stopping (local mode only)
- **Network isolation**: All containers use `deployer-network` for security

## API Endpoints

### GET `/admin/server/anvil/status`
Get current anvil instance status:
```json
{
  "running": true,
  "port": 8545,
  "container_name": "anvil-local",
  "network": "deployer-network",
  "last_activity": 1692547200.123,
  "container_status": "running",
  "is_forked": false,
  "snapshots": {
    "total_snapshots": 2,
    "latest_snapshot": null,
    "snapshot_enabled": true
  }
}
```

### POST `/admin/server/anvil/start`
Manually start local anvil instance (non-forked):
```json
{
  "success": true,
  "message": "Anvil started successfully"
}
```

### POST `/admin/server/anvil/stop`
Manually stop anvil instance and take snapshot:
```json
{
  "success": true,
  "message": "Anvil stopped successfully"
}
```

### POST `/admin/server/anvil/restart`
Restart anvil with fresh state:
```json
{
  "success": true,
  "message": "Anvil restarted with fresh state"
}
```

### GET `/networks`
List all available networks:
```json
{
  "networks": [
    {
      "network": "local",
      "network_name": "Anvil Local",
      "chainID": 31337,
      "description": "Local RPC node powered by Anvil",
      "deployment_type": "local",
      "requires_anvil": true
    },
    {
      "network": "ETH_TESTNET",
      "network_name": "Sepolia Testnet", 
      "chainID": 11155111,
      "description": "Ethereum testnet for development",
      "deployment_type": "remote",
      "requires_anvil": false
    }
  ],
  "default_network": "local",
  "total_networks": 4
}
```

## How It Works

### 1. **Network-Based Deployment Flow**
```
Publish Request → Validate Network → Determine Anvil Type → Start Container → Deploy → Cache Results
```

### 2. **Anvil Container Selection**
```
Local + fork=false → anvil-local (with snapshots)
Local + fork=true  → anvil-local-fork (forked, no snapshots)
Remote networks    → No anvil (direct RPC)
```

### 3. **Container Communication**
```
Anvil Container (localhost:8545) ← Shared Network Namespace → Forge Container
```

### 4. **State Management by Type**

#### **Local Anvil (`fork=false`)**
- **Container**: `anvil-local` on `deployer-network`
- **Snapshots**: Enabled for state persistence
- **Use case**: Development with persistent state

#### **Forked Anvil (`fork=true`)**  
- **Container**: `anvil-local-fork` on `deployer-network`
- **Fork URL**: `https://reth-ethereum.ithaca.xyz/rpc`
- **Snapshots**: Disabled (forked state)
- **Use case**: Testing against mainnet state

#### **Remote Networks**
- **Container**: None (direct RPC)
- **RPC URLs**: From `config/network.json`
- **Use case**: Testnet/mainnet deployments

## Configuration

### Environment Variables
- `ANVIL_PORT`: Port for anvil (default: 8545)
- `ANVIL_TIMEOUT`: Inactivity timeout in seconds (default: 600)

### Anvil Settings
- **Accounts**: 10 pre-funded accounts
- **Balance**: 10,000 ETH per account
- **Gas Limit**: 30,000,000
- **Host**: 0.0.0.0 (accessible from containers)

## Usage Examples

### Manual Control
```bash
# Check status
curl http://localhost:5001/anvil/status

# Start anvil
curl -X POST http://localhost:5001/anvil/start

# Stop anvil
curl -X POST http://localhost:5001/anvil/stop
```

### Network-Aware Deployment
The publish endpoint supports different network types and fork modes:

#### Local Development (with persistent state)
```bash
curl -X POST http://localhost:5001/publish \
  -H "Content-Type: application/json" \
  -d '{
    "path_url": "./cloned/eurodollar-protocol", 
    "framework": "foundry",
    "network": "local",
    "fork": false
  }'
```

#### Local Testing (with mainnet fork)
```bash
curl -X POST http://localhost:5001/publish \
  -H "Content-Type: application/json" \
  -d '{
    "path_url": "./cloned/eurodollar-protocol", 
    "framework": "foundry", 
    "network": "local",
    "fork": true
  }'
```

#### Remote Network Deployment
```bash
curl -X POST http://localhost:5001/publish \
  -H "Content-Type: application/json" \
  -d '{
    "path_url": "./cloned/eurodollar-protocol", 
    "framework": "foundry",
    "network": "ETH_TESTNET"
  }'
```

## Benefits

### ✅ **Multi-Network Support**
- Seamless local and remote network deployments
- Automatic network validation and configuration
- Fork mode for mainnet testing without state persistence

### ✅ **Container Architecture**
- Fully containerized anvil instances for isolation
- Shared network namespace for localhost communication
- No raw host dependencies or port conflicts

### ✅ **State Management**
- Persistent state for development (`fork=false`)
- Clean forked state for testing (`fork=true`)
- Automatic snapshot management and restoration

### ✅ **Developer Experience**
- Network-aware deployment with `config/network.json`
- Fork parameter for different testing scenarios
- Zero-config setup with automatic container orchestration

## Troubleshooting

### Container Communication Issues
1. Verify Docker network exists: `docker network ls | grep deployer-network`
2. Check anvil container status: `GET /admin/server/anvil/status`
3. Ensure both containers share network namespace

### Network Configuration
1. Validate network in `config/network.json`
2. Check available networks: `GET /networks`
3. Verify RPC URLs are accessible for remote networks

### Fork Mode Issues
1. For `fork=true`: Check mainnet RPC connectivity
2. For `fork=false`: Verify snapshot volume mounts
3. Container logs: `docker logs anvil-local` or `docker logs anvil-local-fork`

### Performance Issues
1. Monitor containerized anvil startup time
2. Check Docker network performance
3. Verify foundry image cache hit rates

## Testing

### Test Network Feature
```bash
python tests/test_network_feature.py
```

### Test Containerized Anvil
```bash  
python tests/test_anvil_container.py
```

### Manual Network Testing
```bash
# Test local deployment (fork=false)
curl -X POST http://localhost:5001/publish \
  -H "Content-Type: application/json" \
  -d '{"path_url": "./test-project", "framework": "foundry", "network": "local", "fork": false}'

# Test forked deployment (fork=true)
curl -X POST http://localhost:5001/publish \
  -H "Content-Type: application/json" \
  -d '{"path_url": "./test-project", "framework": "foundry", "network": "local", "fork": true}'

# Test remote deployment
curl -X POST http://localhost:5001/publish \
  -H "Content-Type: application/json" \
  -d '{"path_url": "./test-project", "framework": "foundry", "network": "ETH_TESTNET"}'
```
