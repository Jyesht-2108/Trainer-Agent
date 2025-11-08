"""
FastAPI application for the Training Agent.

This module provides REST API endpoints for triggering training jobs,
querying training status, and health checks.

Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 8.5
"""

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import traceback
from datetime import datetime

from agent.models.schemas import (
    TrainingRequest,
    TrainingResponse,
    StatusResponse,
    HealthResponse
)
from agent.services.training_service import execute_training
from agent.services.database_service import db_service
from agent.services.polling_service import polling_service
from agent.config import settings
import asyncio


# Initialize FastAPI app
app = FastAPI(
    title="Training Agent API",
    description="AutoML Multi-Agent System - Training Agent",
    version="1.0.0"
)


# Exception handlers for error formatting (Requirement 8.5)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors with formatted response."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": "Invalid request data",
            "details": exc.errors()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions with formatted response."""
    error_trace = traceback.format_exc()
    print(f"Unhandled exception: {error_trace}")
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": f"Internal server error: {str(exc)}"
        }
    )


# API Endpoints

@app.post(
    "/agents/training/start",
    response_model=TrainingResponse,
    status_code=status.HTTP_200_OK,
    summary="Start training job",
    description="Trigger the training workflow for a project"
)
async def start_training(request: TrainingRequest) -> TrainingResponse:
    """
    Start a training job for the specified project.
    
    This endpoint triggers the complete training workflow including:
    - Dataset download from GCP
    - Model training with PyTorch
    - Model upload to GCP
    - Database metadata updates
    
    Args:
        request: TrainingRequest containing project_id
        
    Returns:
        TrainingResponse with success status and model_url or error
        
    Raises:
        HTTPException: For validation errors or resource not found
        
    Requirements: 9.1, 9.2
    """
    try:
        # Call training service to execute the workflow
        result = await execute_training(request.project_id)
        
        # Check if training was successful
        if result.get("success"):
            return TrainingResponse(
                success=True,
                model_url=result.get("model_url")
            )
        else:
            # Training failed, return error with 400 status
            error_message = result.get("error", "Training failed")
            
            # Determine appropriate status code
            if "not found" in error_message.lower():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=error_message
                )
            elif "status" in error_message.lower() and "pending_training" in error_message.lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_message
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=error_message
                )
                
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Catch unexpected errors
        error_msg = f"Failed to start training: {str(e)}"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@app.get(
    "/agents/training/status/{project_id}",
    response_model=StatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get training status",
    description="Retrieve current training status and recent logs for a project"
)
async def get_training_status(project_id: str) -> StatusResponse:
    """
    Get the current training status and recent logs for a project.
    
    This endpoint queries the database for:
    - Current project status
    - Recent agent logs for the training agent
    
    Args:
        project_id: UUID of the project to query
        
    Returns:
        StatusResponse with status, progress info, and recent logs
        
    Raises:
        HTTPException: If project not found or database error
        
    Requirements: 9.2, 9.3
    """
    try:
        # Get project to check status
        project = db_service.get_project(project_id)
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project {project_id} not found"
            )
        
        # Get recent logs for this project
        logs = db_service.get_recent_logs(project_id, limit=50)
        
        # Build progress information
        progress = {
            "project_name": project.get("name"),
            "task_type": project.get("task_type"),
            "framework": project.get("framework"),
            "metadata": project.get("metadata", {}),
            "updated_at": project.get("updated_at")
        }
        
        return StatusResponse(
            status=project.get("status", "unknown"),
            progress=progress,
            logs=logs
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Catch unexpected errors
        error_msg = f"Failed to retrieve status: {str(e)}"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@app.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check",
    description="Check if the Training Agent service is healthy"
)
async def health_check() -> HealthResponse:
    """
    Health check endpoint for monitoring and uptime checks.
    
    Returns:
        HealthResponse with service status and current timestamp
        
    Requirements: 9.3
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow()
    )


@app.get(
    "/agents/training/polling/status",
    status_code=status.HTTP_200_OK,
    summary="Get polling service status",
    description="Check if automatic polling is running"
)
async def get_polling_status():
    """
    Get the status of the automatic polling service.
    
    Returns:
        Dictionary with polling service status
    """
    return {
        "is_running": polling_service.is_running,
        "poll_interval": polling_service.poll_interval,
        "processed_projects_count": len(polling_service.processed_projects)
    }


# Application startup event
@app.on_event("startup")
async def startup_event():
    """Log application startup and start polling service."""
    print(f"Training Agent starting up...")
    print(f"Log level: {settings.log_level}")
    print(f"GCP Bucket: {settings.gcp_bucket_name}")
    print(f"Supabase URL: {settings.supabase_url}")
    
    # Start the polling service in the background
    asyncio.create_task(polling_service.start())
    print("Automatic polling service started")


# Application shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Log application shutdown and stop polling service."""
    print("Training Agent shutting down...")
    polling_service.stop()


if __name__ == "__main__":
    import uvicorn
    
    # Run the application
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=settings.log_level.lower()
    )
