# ZERO CONFIG EPHEMERAL DEPLOYMENT SANDBOX

he ultimate sandbox for developers. Deploy anything, anywhere, without configuration.  Isolate from hacks, scripts, compromised codebase. no more git clone and installs to test or contribute to anything spin up anything in 10s

## Setup

1. Install dependencies with Poetry:
```bash
poetry install --no-root
```

2. Ensure Docker is running on your system.

3. Start the API server:
```bash
poetry run python app.py
```



**Request Body:**
```json
{
  "path_url": "./cloned/eurodollar-protocol",
  "framework": "foundry"
}
```

**Response:**
```json
{
  "success": true,
  "artifact_path": "/path/to/.artifacts",
  "stdout": "compilation output...",
  "stderr": "error output...",
  "duration_seconds": 45.2
}
```

#### POST /publish
Deploys Foundry contracts on-chain and saves addresses to `kv-deploy.json`.

**Request Body:**
```json
{
  "path_url": "./cloned/eurodollar-protocol",
  "framework": "foundry"
}
```

**Response:**
```json
{
  "success": true,
  "deployed_contracts": {
    "Validator": "0x5FbDB2315678afecb367f032d93F642f64180aa3",
    "USDE": "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0"
  },
  "deployment_key": "./cloned/eurodollar-protocol:1692547200",
  "stdout": "deployment logs...",
  "stderr": "",
  "duration_seconds": 67.3
}
```

### Admin/Server Management Endpoints

#### GET /admin/server/health
Server health check.

#### POST /admin/server/anvil/start
Start anvil instance for local blockchain.

#### POST /admin/server/anvil/stop
Stop anvil instance.

#### GET /admin/server/anvil/status
Get anvil instance status.

## Interactive Testing

Visit `http://localhost:5001/swagger` for interactive API documentation and testing.

## Supported Frameworks

- **Hardhat**: Uses `npm ci/install && npx hardhat compile`, artifacts from `artifacts/`
- **Foundry**: Uses `forge install && forge build`, artifacts from `out/`

## Storage

- **kv-deploy.json**: Local storage of deployment records
- **Redis**: Optional caching layer (auto-detects availability)
