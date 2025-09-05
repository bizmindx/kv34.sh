import logging
from flask import Blueprint, jsonify

logger = logging.getLogger(__name__)
network_bp = Blueprint('network', __name__)

@network_bp.route('/networks', methods=['GET'])
def list_networks():
    """List all available networks for deployment"""
    from app import network_manager
    
    try:
        networks = network_manager.list_networks()
        return jsonify(networks), 200
    except Exception as e:
        logger.error(f"Failed to list networks: {e}")
        return jsonify({'error': f'Failed to list networks: {str(e)}'}), 500

@network_bp.route('/networks/<network_name>', methods=['GET'])
def get_network_info(network_name):
    """Get specific network information"""
    from app import network_manager
    
    try:
        network_info = network_manager.get_network_info(network_name)
        if not network_info:
            return jsonify({'error': f'Network not found: {network_name}'}), 404
        return jsonify(network_info), 200
    except Exception as e:
        logger.error(f"Failed to get network info: {e}")
        return jsonify({'error': f'Failed to get network info: {str(e)}'}), 500