"""Pydantic models for API requests and responses."""
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field


class TrainingRequest(BaseModel):
    """Request model for starting a training job."""
    project_id: str = Field(..., description="UUID of the project to train")


class TrainingResponse(BaseModel):
    """Response model for training job results."""
    success: bool = Field(..., description="Whether the training completed successfully")
    model_url: Optional[str] = Field(None, description="GCS URL of the trained model")
    error: Optional[str] = Field(None, description="Error message if training failed")


class StatusResponse(BaseModel):
    """Response model for training status queries."""
    status: str = Field(..., description="Current project status")
    progress: Dict[str, Any] = Field(default_factory=dict, description="Training progress information")
    logs: List[Dict[str, Any]] = Field(default_factory=list, description="Recent agent logs")


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""
    status: str = Field(..., description="Service health status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Current timestamp")


# Database models for internal use
class ProjectData(BaseModel):
    """Model representing project data from Supabase."""
    id: str
    name: str
    task_type: str
    framework: str
    status: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DatasetData(BaseModel):
    """Model representing dataset data from Supabase."""
    id: str
    project_id: str
    name: str
    gcs_url: str
    size: Optional[str] = None
    source: Optional[str] = None
    created_at: Optional[datetime] = None


class ModelData(BaseModel):
    """Model representing model data for Supabase insertion."""
    project_id: str
    name: str
    framework: str
    gcs_url: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
