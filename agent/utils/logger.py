"""Logging configuration and utilities for the Training Agent."""
import logging
import sys
from typing import Optional
from datetime import datetime
from agent.config import settings


# Configure logging format with timestamps and log levels
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> logging.Logger:
    """
    Set up structured logging configuration.
    
    Configures the root logger with:
    - Log level from LOG_LEVEL environment variable (Requirement 10.5)
    - Structured format with timestamps and log levels
    - Output to stdout
    
    Returns:
        Configured logger instance for the training agent
    """
    # Get log level from environment variable
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        stream=sys.stdout,
        force=True  # Override any existing configuration
    )
    
    # Create and return logger for training agent
    logger = logging.getLogger("training_agent")
    logger.setLevel(log_level)
    
    return logger


# Global logger instance
logger = setup_logging()


class AgentLogger:
    """
    Helper class for logging to both stdout and agent_logs table.
    
    Provides methods that log messages to stdout via Python logging
    and optionally write to the Supabase agent_logs table for persistence.
    """
    
    def __init__(self, project_id: Optional[str] = None):
        """
        Initialize AgentLogger.
        
        Args:
            project_id: Optional project ID for database logging
        """
        self.project_id = project_id
        self.logger = logger
        self._db_service = None
    
    @property
    def db_service(self):
        """Lazy load database service to avoid circular imports."""
        if self._db_service is None:
            from agent.services.database_service import db_service
            self._db_service = db_service
        return self._db_service
    
    def set_project_id(self, project_id: str) -> None:
        """
        Set the project ID for database logging.
        
        Args:
            project_id: UUID of the project to associate logs with
        """
        self.project_id = project_id
    
    def info(self, message: str, log_to_db: bool = True) -> None:
        """
        Log an info-level message.
        
        Args:
            message: Log message content
            log_to_db: Whether to also write to agent_logs table (default: True)
        """
        self.logger.info(message)
        
        if log_to_db and self.project_id:
            try:
                self.db_service.log_agent_activity(
                    project_id=self.project_id,
                    message=message,
                    level="info"
                )
            except Exception as e:
                self.logger.warning(f"Failed to write log to database: {str(e)}")
    
    def warning(self, message: str, log_to_db: bool = True) -> None:
        """
        Log a warning-level message.
        
        Args:
            message: Log message content
            log_to_db: Whether to also write to agent_logs table (default: True)
        """
        self.logger.warning(message)
        
        if log_to_db and self.project_id:
            try:
                self.db_service.log_agent_activity(
                    project_id=self.project_id,
                    message=message,
                    level="warning"
                )
            except Exception as e:
                self.logger.warning(f"Failed to write log to database: {str(e)}")
    
    def error(self, message: str, log_to_db: bool = True) -> None:
        """
        Log an error-level message.
        
        Args:
            message: Log message content
            log_to_db: Whether to also write to agent_logs table (default: True)
        """
        self.logger.error(message)
        
        if log_to_db and self.project_id:
            try:
                self.db_service.log_agent_activity(
                    project_id=self.project_id,
                    message=message,
                    level="error"
                )
            except Exception as e:
                self.logger.warning(f"Failed to write log to database: {str(e)}")
    
    def debug(self, message: str, log_to_db: bool = False) -> None:
        """
        Log a debug-level message.
        
        Args:
            message: Log message content
            log_to_db: Whether to also write to agent_logs table (default: False)
        """
        self.logger.debug(message)
        
        if log_to_db and self.project_id:
            try:
                self.db_service.log_agent_activity(
                    project_id=self.project_id,
                    message=message,
                    level="debug"
                )
            except Exception as e:
                self.logger.warning(f"Failed to write log to database: {str(e)}")


def get_agent_logger(project_id: Optional[str] = None) -> AgentLogger:
    """
    Factory function to create an AgentLogger instance.
    
    Args:
        project_id: Optional project ID for database logging
        
    Returns:
        Configured AgentLogger instance
    """
    return AgentLogger(project_id=project_id)
