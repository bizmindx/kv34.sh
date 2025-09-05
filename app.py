import logging
import time
import json
import re
import os
import time
import shutil
from pathlib import Path
from flask import Flask, request, jsonify
from flask_swagger_ui import get_swaggerui_blueprint
import docker
from docker.errors import DockerException, ImageNotFound, APIError
import redis
from dotenv import load_dotenv
from containers.node.anvil_container_manager import AnvilContainerManager
from containers.image_cache import ImageCache
from containers.network_manager import NetworkManager
from containers.foundry_cache import FoundryCache
from containers.persistent_container_manager import PersistentContainerManager
from utils.error_logger import ErrorLogger
from routes.deployment import deployment_bp
from routes.network import network_bp
from routes.admin import admin_bp

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Redis setup
try:
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    redis_client = redis.from_url(redis_url, decode_responses=True)
    redis_client.ping()
    logger.info(f"Connected to Redis at {redis_url}")
except redis.ConnectionError:
    logger.warning("Redis not available - caching disabled")
    redis_client = None

# Initialize caches and managers
image_cache = ImageCache(redis_client)
foundry_cache = FoundryCache(redis_client)
anvil_manager_fork = AnvilContainerManager(port=8545, container_name="anvil-local-fork", local_mode=False)  # Forked mode
anvil_manager_local = AnvilContainerManager(port=8545, container_name="anvil-local", local_mode=True)  # Local mode with snapshots
network_manager = NetworkManager()
persistent_container_manager = PersistentContainerManager(redis_client=redis_client, inactivity_timeout=600)  # 10 minutes
error_logger = ErrorLogger("FlaskAPI")

def _parse_stdout_fallback(stdout: str, deployed_contracts: dict):
    """Parse deployment data from stdout as fallback"""
    deploy_pattern = r'Deployed (\w+):\s+(0x[a-fA-F0-9]{40})'
    matches = re.findall(deploy_pattern, stdout)
    for i, (contract_name, address) in enumerate(matches):
        placeholder_hash = f"stdout_fallback_{int(time.time())}_{i}"
        deployed_contracts[placeholder_hash] = {
            "contractName": contract_name,
            "address": address
        }



# Swagger UI setup
SWAGGER_URL = '/swagger'
API_URL = '/swagger.json'
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={
        'app_name': "Smart Contract Deployer API"
    }
)
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

# Register route blueprints
app.register_blueprint(deployment_bp)
app.register_blueprint(network_bp)
app.register_blueprint(admin_bp)

@app.route('/swagger.json')
def swagger_spec():
    with open('swagger.json', 'r') as f:
        return jsonify(json.load(f))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)