"""Database service for Supabase interactions."""
from typing import Optional, Dict, Any
from datetime import datetime
from supabase import create_client, Client
from agent.config import settings
from agent.models.schemas import ProjectData, DatasetData, ModelData


class DatabaseService:
    """Service for managing Supabase database operations."""
    
    def __init__(self):
        """Initialize Supabase client with credentials from settings."""
        self.client: Client = create_client(
            supabase_url=settings.supabase_url,
            supabase_key=settings.supabase_key
        )
    
    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve project metadata by ID.
        
        Args:
            project_id: UUID of the project to retrieve
            
        Returns:
            Project data dictionary or None if not found
            
        Raises:
            Exception: If database query fails
        """
        try:
            response = self.client.table("projects").select("*").eq("id", project_id).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            raise Exception(f"Failed to retrieve project {project_id}: {str(e)}")
    
    def get_dataset(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve dataset metadata by project_id.
        
        Args:
            project_id: UUID of the project whose dataset to retrieve
            
        Returns:
            Dataset data dictionary or None if not found
            
        Raises:
            Exception: If database query fails
        """
        try:
            response = self.client.table("datasets").select("*").eq("project_id", project_id).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            raise Exception(f"Failed to retrieve dataset for project {project_id}: {str(e)}")

    def insert_model(self, model_data: ModelData) -> Dict[str, Any]:
        """
        Insert a new model record into the models table.
        
        Args:
            model_data: ModelData object containing model information
            
        Returns:
            Inserted model record dictionary
            
        Raises:
            Exception: If database insertion fails
        """
        try:
            data = {
                "project_id": model_data.project_id,
                "name": model_data.name,
                "framework": model_data.framework,
                "gcs_url": model_data.gcs_url,
                "metadata": model_data.metadata
            }
            
            response = self.client.table("models").insert(data).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            raise Exception("No data returned from insert operation")
        except Exception as e:
            raise Exception(f"Failed to insert model record: {str(e)}")
    
    def update_project_status(self, project_id: str, status: str) -> None:
        """
        Update the status of a project and set updated_at timestamp.
        
        Args:
            project_id: UUID of the project to update
            status: New status value (e.g., "pending_evaluation", "failed")
            
        Raises:
            Exception: If database update fails
        """
        try:
            data = {
                "status": status,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            response = self.client.table("projects").update(data).eq("id", project_id).execute()
            
            if not response.data:
                raise Exception(f"Project {project_id} not found or update failed")
        except Exception as e:
            raise Exception(f"Failed to update project status: {str(e)}")
    
    def log_agent_activity(
        self, 
        project_id: str, 
        message: str, 
        level: str = "info"
    ) -> None:
        """
        Write a log entry to the agent_logs table.
        
        Args:
            project_id: UUID of the project this log relates to
            message: Log message content
            level: Log level (info, warning, error)
            
        Raises:
            Exception: If database insertion fails
        """
        try:
            data = {
                "project_id": project_id,
                "agent_name": "training",
                "message": message,
                "log_level": level,
                "created_at": datetime.utcnow().isoformat()
            }
            
            self.client.table("agent_logs").insert(data).execute()
        except Exception as e:
            # Log errors should not break the main workflow
            print(f"Warning: Failed to write agent log: {str(e)}")
    
    def get_recent_logs(self, project_id: str, limit: int = 50) -> list[Dict[str, Any]]:
        """
        Retrieve recent agent logs for a project.
        
        Args:
            project_id: UUID of the project to get logs for
            limit: Maximum number of logs to retrieve (default: 50)
            
        Returns:
            List of log entries ordered by created_at descending
            
        Raises:
            Exception: If database query fails
        """
        try:
            response = (
                self.client.table("agent_logs")
                .select("*")
                .eq("project_id", project_id)
                .eq("agent_name", "training")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            
            return response.data if response.data else []
        except Exception as e:
            raise Exception(f"Failed to retrieve logs for project {project_id}: {str(e)}")
    
    def get_projects_by_status(self, status: str) -> list[Dict[str, Any]]:
        """
        Retrieve all projects with a specific status.
        
        Args:
            status: Status to filter by (e.g., "pending_training")
            
        Returns:
            List of project dictionaries matching the status
            
        Raises:
            Exception: If database query fails
        """
        try:
            response = (
                self.client.table("projects")
                .select("*")
                .eq("status", status)
                .execute()
            )
            
            return response.data if response.data else []
        except Exception as e:
            raise Exception(f"Failed to retrieve projects with status {status}: {str(e)}")


# Global database service instance
db_service = DatabaseService()
