import logging
import shutil
import time
import json
import re
from pathlib import Path
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)
deployment_bp = Blueprint('deployment', __name__)

def _parse_stdout_fallback(stdout: str, deployed_contracts: dict):
    """Parse deployment data from stdout as fallback"""
    # Common deployment patterns
    patterns = [
        r'Deployed (\w+).*?:\s+(0x[a-fA-F0-9]{40})',  # Deployed ContractName: or Deployed ContractName ABC:
        r'(\w+) deployed to:\s+(0x[a-fA-F0-9]{40})',   # ContractName deployed to:
    ]
    
    seen_addresses = set()
    for pattern in patterns:
        matches = re.findall(pattern, stdout)
        for contract_name, address in matches:
            # Skip duplicates and invalid names
            if address not in seen_addresses and len(contract_name) > 1:
                seen_addresses.add(address)
                deployed_contracts[address] = {
                    "contractName": contract_name,
                    "address": address
                }

@deployment_bp.route('/deploy', methods=['POST'])
def deploy():
    from app import image_cache, persistent_container_manager
    
    try:
        data = request.get_json()
        if not data or 'path_url' not in data:
            return jsonify({'error': 'Missing path_url in request body'}), 400
        
        if 'framework' not in data:
            return jsonify({'error': 'Missing framework in request body'}), 400
        
        path_url = data['path_url']
        framework = data['framework'].lower()
        
        if framework not in ['hardhat', 'foundry']:
            return jsonify({'error': 'Framework must be either "hardhat" or "foundry"'}), 400
        
        local_path = Path(path_url).resolve()
        
        if not local_path.exists():
            return jsonify({'error': f'Path does not exist: {path_url}'}), 404
        
        if not local_path.is_dir():
            return jsonify({'error': f'Path is not a directory: {path_url}'}), 400
        
        logger.info(f"Starting {framework} deployment for path: {local_path}")
        
        try:
            
            if framework == 'hardhat':
                dockerfile = "Dockerfile"
                image_tag = "hardhat-deployer:latest"
                has_lockfile = (local_path / "package-lock.json").exists()
                install_cmd = "npm ci" if has_lockfile else "npm install"
                full_command = f"{install_cmd} && npx hardhat compile"
                artifacts_source_dir = "artifacts"
            else:  # foundry
                dockerfile = "Dockerfile.foundry"
                image_tag = "foundry-deployer:latest"
                full_command = "git config --global --add safe.directory '*' && forge install && forge build"
                artifacts_source_dir = "out"
            
            logger.info(f"Getting or building {framework} Docker image...")
            was_cached, image_id = image_cache.get_or_build_image(
                dockerfile_path=f"containers/images/{dockerfile}",
                image_tag=image_tag,
                build_context="."
            )
            
            if was_cached:
                logger.info(f"Using cached image {image_tag}")
            else:
                logger.info(f"Built new image {image_tag}")
            
            artifacts_dir = local_path / ".artifacts"
            artifacts_dir.mkdir(exist_ok=True)
            
            logger.info(f"Executing {framework} compilation using persistent container...")
            
            # Use persistent container manager for compilation
            result = persistent_container_manager.execute_command(
                framework=framework,
                command=full_command,
                project_path=str(local_path)
            )
            
            stdout = result['stdout']
            stderr = result.get('stderr', '')
            duration_seconds = result['duration_seconds']
            
            if result['status_code'] != 0:
                return jsonify({
                    'success': False,
                    'artifact_path': '',
                    'stdout': stdout,
                    'stderr': stderr,
                    'duration_seconds': duration_seconds,
                    'container_reused': result.get('container_reused', False)
                }), 500
            
            artifacts_source = local_path / artifacts_source_dir
            if artifacts_source.exists():
                if artifacts_dir.exists():
                    shutil.rmtree(artifacts_dir)
                shutil.copytree(artifacts_source, artifacts_dir)
            
            return jsonify({
                'success': True,
                'artifact_path': str(artifacts_dir),
                'stdout': stdout,
                'stderr': stderr,
                'duration_seconds': duration_seconds,
                'container_reused': result.get('container_reused', False)
            }), 200
            
        except Exception as e:
            return jsonify({'error': f'Deployment failed: {str(e)}'}), 500
        
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@deployment_bp.route('/publish', methods=['POST'])
def publish():
    import docker
    from app import anvil_manager_fork, anvil_manager_local, network_manager, image_cache, persistent_container_manager, foundry_cache
    
    try:
        data = request.get_json()
        if not data or 'path_url' not in data or 'framework' not in data:
            return jsonify({'error': 'Missing path_url or framework in request body'}), 400
        
        path_url = data['path_url']
        framework = data['framework'].lower()
        network = data.get('network', 'local')
        script_path = data.get('script_path', 'script/Deploy.s.sol')
        fork = data.get('fork', False)
        
        if framework not in ['foundry', 'hardhat']:
            return jsonify({'error': 'Only foundry and hardhat frameworks supported for publishing'}), 400
        
        # Validate network
        if not network_manager.validate_network(network):
            return jsonify({'error': f'Invalid network: {network}. Available networks: {list(network_manager.get_all_networks().keys())}'}), 400
        
        local_path = Path(path_url).resolve()
        
        if not local_path.exists():
            return jsonify({'error': f'Path does not exist: {path_url}'}), 404
        
        client = docker.from_env()
        
        try:
            start_time = time.time()
            
            # Get network configuration
            network_config = network_manager.get_network(network)
            logger.info(f"Deploying to network: {network_config['network_name']} ({network_config['chainID']})")
            
            # Get appropriate image for framework
            if framework == 'foundry':
                dockerfile_path = "containers/images/Dockerfile.foundry"
                image_tag = "foundry-deployer:latest"
            else:  # hardhat
                dockerfile_path = "containers/images/Dockerfile"
                image_tag = "hardhat-deployer:latest"
            
            logger.info(f"Getting or building {framework} Docker image...")
            was_cached, image_id = image_cache.get_or_build_image(
                dockerfile_path=dockerfile_path,
                image_tag=image_tag,
                build_context="."
            )
            
            if was_cached:
                logger.info(f"Using cached {framework} image")
            else:
                logger.info(f"Built new {framework} image")
            
            # Start appropriate anvil container based on network type and fork parameter
            if network_config["deployment_type"] == "local":
                if fork:
                    # Stop local anvil before starting fork anvil
                    anvil_manager_local.stop()
                    logger.info("Starting forked anvil container for local deployment")
                    if not anvil_manager_fork.start(fork_url="https://reth-ethereum.ithaca.xyz/rpc"):
                        return jsonify({'error': 'Failed to start forked anvil container'}), 500
                    current_anvil = anvil_manager_fork
                else:
                    # Stop fork anvil before starting local anvil
                    anvil_manager_fork.stop()
                    logger.info("Starting local anvil container (no fork)")
                    if not anvil_manager_local.start():
                        return jsonify({'error': 'Failed to start local anvil container'}), 500
                    current_anvil = anvil_manager_local
                
                # Ensure anvil is fully ready for container-to-container communication
                logger.info(f"Anvil container started: {current_anvil.container_name} on network {current_anvil.network_name}")
                time.sleep(2)  # Give anvil time to be fully ready
            else:
                # Remote network: no anvil needed
                logger.info("Remote network - no anvil container needed")
                current_anvil = None
            
            # Generate deployment command based on network type
            if framework == 'foundry':
                full_command = network_manager.get_deployment_command(network, script_path, fork)
            else:  # hardhat
                full_command = f"npx hardhat run scripts/deploy.js --network localhost"
            
            logger.info(f"Starting container with command: {full_command}")
            
            # Use persistent container manager for deployment execution
            logger.info(f"Executing {framework} deployment using persistent container...")
            
            anvil_container = current_anvil.container_name if current_anvil else None
            logger.info(f"Anvil container name for networking: {anvil_container}")
            result = persistent_container_manager.execute_command(
                framework=framework,
                command=full_command,
                project_path=str(local_path),
                network_config=network_config,
                anvil_container_name=anvil_container
            )
            
            stdout = result['stdout']
            stderr = result.get('stderr', '')
            duration_seconds = result['duration_seconds']
            
            
            # Parse deployed contract addresses based on framework
            deployed_contracts = {}
            
            if framework == 'foundry':
                broadcast_dir = local_path / "broadcast" / "Deploy.s.sol" / "31337"
                
                if broadcast_dir.exists():
                    # Find the latest broadcast run file
                    run_files = list(broadcast_dir.glob("run-*.json"))
                    if run_files:
                        latest_run_file = max(run_files, key=lambda p: p.stat().st_mtime)
                        logger.info(f"Reading deployment data from: {latest_run_file}")
                        
                        try:
                            with open(latest_run_file, 'r') as f:
                                broadcast_data = json.load(f)
                            
                            # Extract contract data from transactions
                            if "transactions" in broadcast_data:
                                for tx in broadcast_data["transactions"]:
                                    if tx.get("transactionType") == "CREATE" and "contractName" in tx:
                                        contract_name = tx["contractName"]
                                        contract_address = tx.get("contractAddress")
                                        tx_hash = tx.get("hash")
                                        if contract_name and contract_address and tx_hash:
                                            deployed_contracts[tx_hash] = {
                                                "contractName": contract_name,
                                                "address": contract_address
                                            }
                                            
                        except Exception as e:
                            logger.warning(f"Failed to parse broadcast file {latest_run_file}: {e}")
                            # Fallback to stdout parsing
                            _parse_stdout_fallback(stdout, deployed_contracts)
                    else:
                        logger.warning("No broadcast run files found, falling back to stdout parsing")
                        _parse_stdout_fallback(stdout, deployed_contracts)
                else:
                    logger.warning("Broadcast directory not found, falling back to stdout parsing")
                    _parse_stdout_fallback(stdout, deployed_contracts)
            
            else:  # hardhat
                # Parse Hardhat deployment output
                deploy_pattern = r'(\w+) deployed to:\s+(0x[a-fA-F0-9]{40})'
                matches = re.findall(deploy_pattern, stdout)
                for i, (contract_name, address) in enumerate(matches):
                    placeholder_hash = f"hardhat_deploy_{int(time.time())}_{i}"
                    deployed_contracts[placeholder_hash] = {
                        "contractName": contract_name,
                        "address": address
                    }
            
            # Save to kv-deploy.json with version separation
            kv_file = Path("kv-deploy.json")
            kv_data = {"metadata": {"current_version": 1}, "versions": {}}
            
            if kv_file.exists():
                with open(kv_file, 'r') as f:
                    existing_data = json.load(f)
                    # Convert old format if needed
                    if "versions" in existing_data:
                        kv_data = existing_data
                    else:
                        # Old format migration
                        kv_data = {"metadata": {"current_version": 1}, "versions": {}}
            
            # Increment version for new deployment
            current_version = kv_data["metadata"]["current_version"]
            new_version = current_version + 1
            kv_data["metadata"]["current_version"] = new_version
            
            # Create new version entry
            kv_data["versions"][str(new_version)] = {
                "timestamp": time.time(),
                "network": network,
                "framework": framework,
                "fork": fork if network_config["deployment_type"] == "local" else None,
                "script_path": script_path,
                "deployments": []
            }
            
            # Add deployments to this version as array
            for tx_hash, contract_data in deployed_contracts.items():
                # Use empty string for hash if it's not a real transaction hash
                actual_hash = tx_hash if tx_hash.startswith('0x') and len(tx_hash) == 66 else ""
                kv_data["versions"][str(new_version)]["deployments"].append({
                    'contractName': contract_data['contractName'],
                    'address': contract_data['address'],
                    'hash': actual_hash
                })
            
            with open(kv_file, 'w') as f:
                json.dump(kv_data, f, indent=2)
            
            if result['status_code'] != 0:
                return jsonify({
                    'success': False,
                    'deployed_contracts': {},
                    'stdout': stdout,
                    'stderr': stderr,
                    'duration_seconds': duration_seconds,
                    'container_reused': result.get('container_reused', False)
                }), 500
            
            # Prepare successful response
            response_data = {
                'success': True,
                'deployed_contracts': deployed_contracts,
                'stdout': stdout,
                'stderr': stderr,
                'duration_seconds': duration_seconds,
                'container_reused': result.get('container_reused', False)
            }
            
            # Cache successful execution
            foundry_image_sha = image_id if framework == 'foundry' else ""
            hardhat_image_sha = image_id if framework == 'hardhat' else ""
            cache_fork_url = network_config['rpc_url'] if network_config["deployment_type"] == "local" else network_config['rpc_url']
            foundry_cache.cache_result(str(local_path), script_path, cache_fork_url, response_data, foundry_image_sha, hardhat_image_sha)
            
            return jsonify(response_data), 200
            
        except Exception as e:
            return jsonify({'error': f'Deployment failed: {str(e)}'}), 500
        
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500