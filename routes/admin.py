import logging
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)
admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin/server/health', methods=['GET'])
def admin_health():
    return jsonify({'status': 'healthy'}), 200

@admin_bp.route('/admin/server/anvil/start', methods=['POST'])
def admin_anvil_start():
    from app import anvil_manager_local
    
    try:
        success = anvil_manager_local.start()
        if success:
            return jsonify({'success': True, 'message': 'Anvil started successfully'}), 200
        else:
            return jsonify({'success': False, 'error': 'Failed to start anvil'}), 500
    except Exception as e:
        logger.error(f"Failed to start anvil: {e}")
        return jsonify({'error': f'Failed to start anvil: {str(e)}'}), 500

@admin_bp.route('/admin/server/anvil/stop', methods=['POST'])
def admin_anvil_stop():
    from app import anvil_manager_local
    
    try:
        success = anvil_manager_local.stop()
        if success:
            return jsonify({'success': True, 'message': 'Anvil stopped successfully'}), 200
        else:
            return jsonify({'success': False, 'error': 'Failed to stop anvil'}), 500
    except Exception as e:
        logger.error(f"Failed to stop anvil: {e}")
        return jsonify({'error': f'Failed to stop anvil: {str(e)}'}), 500

@admin_bp.route('/admin/server/anvil/restart', methods=['POST'])
def admin_anvil_restart():
    from app import anvil_manager_local
    
    try:
        success = anvil_manager_local.restart()
        if success:
            return jsonify({'success': True, 'message': 'Anvil restarted with fresh state'}), 200
        else:
            return jsonify({'success': False, 'error': 'Failed to restart anvil'}), 500
    except Exception as e:
        logger.error(f"Failed to restart anvil: {e}")
        return jsonify({'error': f'Failed to restart anvil: {str(e)}'}), 500

@admin_bp.route('/admin/server/anvil/status', methods=['POST'])
def admin_anvil_status():
    from app import anvil_manager_local
    
    try:
        status = anvil_manager_local.get_status()
        snapshot_info = anvil_manager_local.get_snapshot_info()
        status.update({"snapshots": snapshot_info})
        return jsonify(status), 200
    except Exception as e:
        logger.error(f"Failed to get anvil status: {e}")
        return jsonify({'error': f'Failed to get anvil status: {str(e)}'}), 500

@admin_bp.route('/admin/server/cache/status', methods=['GET'])
def admin_cache_status():
    from app import image_cache
    
    try:
        cache_stats = image_cache.get_cache_stats()
        return jsonify(cache_stats), 200
    except Exception as e:
        logger.error(f"Failed to get cache status: {e}")
        return jsonify({'error': f'Failed to get cache status: {str(e)}'}), 500

@admin_bp.route('/admin/server/cache/clear', methods=['POST'])
def admin_cache_clear():
    from app import image_cache
    
    try:
        data = request.get_json() or {}
        image_tag = data.get('image_tag')  # Optional: clear specific image
        
        if image_tag:
            image_cache.clear_cache(image_tag)
            return jsonify({'success': True, 'message': f'Cleared cache for {image_tag}'}), 200
        else:
            image_cache.clear_cache()
            return jsonify({'success': True, 'message': 'Cleared all image cache'}), 200
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        return jsonify({'error': f'Failed to clear cache: {str(e)}'}), 500

@admin_bp.route('/admin/server/foundry-cache/status', methods=['GET'])
def admin_foundry_cache_status():
    from app import foundry_cache, error_logger
    
    try:
        cache_stats = foundry_cache.get_cache_stats()
        return jsonify(cache_stats), 200
    except Exception as e:
        error_logger.log_error("foundry_cache_status_failed", "Failed to get foundry cache status", {}, e)
        return jsonify({'error': f'Failed to get foundry cache status: {str(e)}'}), 500

@admin_bp.route('/admin/server/foundry-cache/clear', methods=['POST'])
def admin_foundry_cache_clear():
    from app import foundry_cache, error_logger
    
    try:
        data = request.get_json() or {}
        pattern = data.get('pattern')  # Optional: clear specific pattern
        
        foundry_cache.clear_cache(pattern)
        message = f'Cleared foundry cache for pattern: {pattern}' if pattern else 'Cleared all foundry cache'
        return jsonify({'success': True, 'message': message}), 200
    except Exception as e:
        error_logger.log_error("foundry_cache_clear_failed", "Failed to clear foundry cache", {"pattern": pattern}, e)
        return jsonify({'error': f'Failed to clear foundry cache: {str(e)}'}), 500

@admin_bp.route('/admin/server/containers/status', methods=['GET'])
def admin_persistent_containers_status():
    """Get persistent container status"""
    from app import persistent_container_manager
    
    try:
        stats = persistent_container_manager.get_persistent_stats()
        return jsonify(stats), 200
    except Exception as e:
        logger.error(f"Failed to get persistent container status: {e}")
        return jsonify({'error': f'Failed to get persistent container status: {str(e)}'}), 500

@admin_bp.route('/admin/server/containers/cleanup', methods=['POST'])
def admin_persistent_containers_cleanup():
    """Clean up all persistent containers"""
    from app import persistent_container_manager
    
    try:
        persistent_container_manager.cleanup_all()
        return jsonify({'success': True, 'message': 'All persistent containers cleaned up'}), 200
    except Exception as e:
        logger.error(f"Failed to cleanup persistent containers: {e}")
        return jsonify({'error': f'Failed to cleanup persistent containers: {str(e)}'}), 500