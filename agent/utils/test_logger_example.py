"""
Example usage of the logging utilities.

This file demonstrates how to use the logger module in the Training Agent.
"""

# Example 1: Using the global logger for simple stdout logging
from agent.utils.logger import logger

logger.info("This is an info message")
logger.warning("This is a warning message")
logger.error("This is an error message")
logger.debug("This is a debug message (only visible if LOG_LEVEL=DEBUG)")


# Example 2: Using AgentLogger for dual logging (stdout + database)
from agent.utils.logger import get_agent_logger

# Create logger with project_id
agent_logger = get_agent_logger(project_id="123e4567-e89b-12d3-a456-426614174000")

# These will log to both stdout and agent_logs table
agent_logger.info("Training started")
agent_logger.warning("Low memory warning")
agent_logger.error("Training failed")

# Debug messages don't log to database by default
agent_logger.debug("Debug information")


# Example 3: Logging without database (stdout only)
agent_logger.info("This goes to stdout only", log_to_db=False)


# Example 4: Setting project_id later
from agent.utils.logger import AgentLogger

agent_logger = AgentLogger()
# ... later in the code when project_id is available
agent_logger.set_project_id("123e4567-e89b-12d3-a456-426614174000")
agent_logger.info("Now logging with project context")


# Example 5: Using in training service
"""
In training_service.py, you could refactor to use:

from agent.utils.logger import get_agent_logger

async def execute_training(project_id: str):
    agent_logger = get_agent_logger(project_id)
    
    agent_logger.info("Training workflow initiated")
    
    try:
        # ... training logic ...
        agent_logger.info("Training completed successfully")
    except Exception as e:
        agent_logger.error(f"Training failed: {str(e)}")
"""
