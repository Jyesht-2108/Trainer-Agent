"""
Integration tests for FastAPI endpoints.

Tests the API layer including request validation, response formatting,
and error handling for all endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from agent.main import app


@pytest.fixture
def client():
    """Create FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_execute_training():
    """Mock the execute_training function."""
    with patch('agent.main.execute_training') as mock:
        yield mock


@pytest.fixture
def mock_db_service():
    """Mock the database service."""
    with patch('agent.main.db_service') as mock:
        yield mock


class TestStartTrainingEndpoint:
    """Tests for POST /agents/training/start endpoint."""
    
    def test_start_training_success(self, client, mock_execute_training):
        """Test successful training start."""
        # Mock successful training
        mock_execute_training.return_value = {
            "success": True,
            "model_url": "gs://test-bucket/models/test_model.pth"
        }
        
        # Make request
        response = client.post(
            "/agents/training/start",
            json={"project_id": "test-project-123"}
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["model_url"] == "gs://test-bucket/models/test_model.pth"
        assert data["error"] is None
        
        # Verify execute_training was called
        mock_execute_training.assert_called_once_with("test-project-123")
    
    def test_start_training_invalid_status(self, client, mock_execute_training):
        """Test training start with invalid project status."""
        # Mock training failure due to invalid status
        mock_execute_training.return_value = {
            "success": False,
            "error": "Project status is 'completed', expected 'pending_training'"
        }
        
        # Make request
        response = client.post(
            "/agents/training/start",
            json={"project_id": "test-project-123"}
        )
        
        # Verify response
        assert response.status_code == 400
        data = response.json()
        assert "status" in data["detail"].lower()
        assert "pending_training" in data["detail"].lower()
    
    def test_start_training_project_not_found(self, client, mock_execute_training):
        """Test training start with non-existent project."""
        # Mock training failure due to missing project
        mock_execute_training.return_value = {
            "success": False,
            "error": "Project test-project-999 not found"
        }
        
        # Make request
        response = client.post(
            "/agents/training/start",
            json={"project_id": "test-project-999"}
        )
        
        # Verify response
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    
    def test_start_training_internal_error(self, client, mock_execute_training):
        """Test training start with internal server error."""
        # Mock training failure with generic error
        mock_execute_training.return_value = {
            "success": False,
            "error": "Failed to download dataset"
        }
        
        # Make request
        response = client.post(
            "/agents/training/start",
            json={"project_id": "test-project-123"}
        )
        
        # Verify response
        assert response.status_code == 500
        data = response.json()
        assert "error" in data["detail"].lower()
    
    def test_start_training_missing_project_id(self, client):
        """Test training start without project_id."""
        # Make request without project_id
        response = client.post(
            "/agents/training/start",
            json={}
        )
        
        # Verify validation error
        assert response.status_code == 422
        data = response.json()
        assert "success" in data
        assert data["success"] is False
    
    def test_start_training_exception(self, client, mock_execute_training):
        """Test training start with unexpected exception."""
        # Mock unexpected exception
        mock_execute_training.side_effect = Exception("Unexpected error")
        
        # Make request
        response = client.post(
            "/agents/training/start",
            json={"project_id": "test-project-123"}
        )
        
        # Verify response
        assert response.status_code == 500
        data = response.json()
        assert "failed to start training" in data["detail"].lower()


class TestStatusEndpoint:
    """Tests for GET /agents/training/status/{project_id} endpoint."""
    
    def test_get_status_success(self, client, mock_db_service):
        """Test successful status retrieval."""
        # Mock database responses
        mock_db_service.get_project.return_value = {
            "id": "test-project-123",
            "name": "test_project",
            "task_type": "image_classification",
            "framework": "pytorch",
            "status": "training",
            "metadata": {"epochs": 10},
            "updated_at": "2024-01-01T12:00:00"
        }
        
        mock_db_service.get_recent_logs.return_value = [
            {
                "id": "log-1",
                "message": "Training started",
                "log_level": "info",
                "created_at": "2024-01-01T12:00:00"
            }
        ]
        
        # Make request
        response = client.get("/agents/training/status/test-project-123")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "training"
        assert "progress" in data
        assert data["progress"]["project_name"] == "test_project"
        assert len(data["logs"]) == 1
        
        # Verify database calls
        mock_db_service.get_project.assert_called_once_with("test-project-123")
        mock_db_service.get_recent_logs.assert_called_once_with("test-project-123", limit=50)
    
    def test_get_status_project_not_found(self, client, mock_db_service):
        """Test status retrieval for non-existent project."""
        # Mock project not found
        mock_db_service.get_project.return_value = None
        
        # Make request
        response = client.get("/agents/training/status/test-project-999")
        
        # Verify response
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    
    def test_get_status_database_error(self, client, mock_db_service):
        """Test status retrieval with database error."""
        # Mock database error
        mock_db_service.get_project.side_effect = Exception("Database connection failed")
        
        # Make request
        response = client.get("/agents/training/status/test-project-123")
        
        # Verify response
        assert response.status_code == 500
        data = response.json()
        assert "failed to retrieve status" in data["detail"].lower()


class TestHealthEndpoint:
    """Tests for GET /health endpoint."""
    
    def test_health_check(self, client):
        """Test health check endpoint."""
        # Make request
        response = client.get("/health")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
    
    def test_health_check_multiple_calls(self, client):
        """Test health check can be called multiple times."""
        # Make multiple requests
        for _ in range(3):
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"
