#!/usr/bin/env python3
"""
Reusable error message utility with structured logging
"""
import logging
import json
import time
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class ErrorLogger:
    def __init__(self, component_name: str):
        self.component_name = component_name
        
    def log_error(self, error_type: str, message: str, details: Optional[Dict[str, Any]] = None, exception: Optional[Exception] = None) -> Dict[str, Any]:
        """
        Log structured error with details
        
        Args:
            error_type: Type of error (e.g., 'container_failed', 'network_error')
            message: Human readable error message
            details: Additional context data
            exception: Original exception if available
            
        Returns:
            Structured error dict for API responses
        """
        timestamp = time.time()
        
        error_data = {
            "timestamp": timestamp,
            "component": self.component_name,
            "error_type": error_type,
            "message": message,
            "details": details or {}
        }
        
        if exception:
            error_data["exception"] = {
                "type": type(exception).__name__,
                "message": str(exception)
            }
        
        # Log to console with structured format
        logger.error(f"[{self.component_name}] {error_type}: {message}")
        if details:
            logger.error(f"Details: {json.dumps(details, indent=2)}")
        if exception:
            logger.error(f"Exception: {type(exception).__name__}: {exception}")
            
        return error_data
    
    def log_warning(self, message: str, details: Optional[Dict[str, Any]] = None):
        """Log warning with component context"""
        logger.warning(f"[{self.component_name}] {message}")
        if details:
            logger.warning(f"Details: {json.dumps(details, indent=2)}")
    
    def log_info(self, message: str, details: Optional[Dict[str, Any]] = None):
        """Log info with component context"""
        logger.info(f"[{self.component_name}] {message}")
        if details:
            logger.info(f"Details: {json.dumps(details, indent=2)}")