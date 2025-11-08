"""
Integration tests for error handling scenarios.

Tests various error conditions including missing projects, invalid datasets,
database failures, and storage errors.
"""
import pytest
from unittest.mock import patch, MagicMock
from agent.services.training_service import execute_training
from agent.services.database_service import DatabaseService
from agent.services.storage_service import StorageService


@pytest.mark.asyncio
class TestErrorHandling:
    """Tests for error handling in various scenarios."""
    
    async def test_missing_project_error(self):
        """Test handling of missing project."""
        with patch('agent.services.training_service.db_service') as mock_db:
            mock_db.get_project.return_value = None
            mock_db.log_agent_activity = MagicMock()
            
            result = await execute_training("nonexistent-project")
            
            assert result["success"] is False
            assert "not found" in result["error"].lower()
            mock_db.log_agent_activity.assert_called()
    
    async def test_missing_dataset_error(self, mock_project_data):
        """Test handling of missing dataset."""
        with patch('agent.services.training_service.db_service') as mock_db:
            mock_db.get_project.return_value = mock_project_data
            mock_db.get_dataset.return_value = None
            mock_db.log_agent_activity = MagicMock()
            mock_db.update_project_status = MagicMock()
            
            result = await execute_training("test-project-123")
            
            assert result["success"] is False
            assert "dataset not found" in result["error"].lower()
            mock_db.update_project_status.assert_called_with("test-project-123", "failed")
    
    async def test_invalid_gcs_url_error(self, mock_project_data):
        """Test handling of invalid GCS URL."""
        with patch('agent.services.training_service.db_service') as mock_db:
            # Dataset with missing gcs_url
            invalid_dataset = {
                "id": "test-dataset",
                "project_id": "test-project-123",
                "name": "test_dataset"
                # Missing gcs_url
            }
            
            mock_db.get_project.return_value = mock_project_data
            mock_db.get_dataset.return_value = invalid_dataset
            mock_db.log_agent_activity = MagicMock()
            mock_db.update_project_status = MagicMock()
            
            result = await execute_training("test-project-123")
            
            assert result["success"] is False
            assert "gcs_url is missing" in result["error"].lower()
            mock_db.update_project_status.assert_called_with("test-project-123", "failed")
    
    async def test_database_connection_error(self):
        """Test handling of database connection failure."""
        with patch('agent.services.training_service.db_service') as mock_db:
            mock_db.get_project.side_effect = Exception("Database connection failed")
            mock_db.log_agent_activity = MagicMock()
            mock_db.update_project_status = MagicMock()
            
            result = await execute_training("test-project-123")
            
            assert result["success"] is False
            assert "error" in result["error"].lower()
    
    async def test_storage_download_error(self, mock_project_data, mock_dataset_data):
        """Test handling of storage download failure."""
        with patch('agent.services.training_service.db_service') as mock_db, \
             patch('agent.services.training_service.storage_service') as mock_storage:
            
            mock_db.get_project.return_value = mock_project_data
            mock_db.get_dataset.return_value = mock_dataset_data
            mock_db.log_agent_activity = MagicMock()
            mock_db.update_project_status = MagicMock()
            
            mock_storage.download_dataset.side_effect = Exception("Network timeout")
            
            result = await execute_training("test-project-123")
            
            assert result["success"] is False
            assert "failed to download" in result["error"].lower()
            mock_db.update_project_status.assert_called_with("test-project-123", "failed")
    
    async def test_storage_upload_error(
        self,
        mock_dataset_zip,
        mock_project_data,
        mock_dataset_data
    ):
        """Test handling of storage upload failure."""
        with patch('agent.services.training_service.db_service') as mock_db, \
             patch('agent.services.training_service.storage_service') as mock_storage:
            
            mock_db.get_project.return_value = mock_project_data
            mock_db.get_dataset.return_value = mock_dataset_data
            mock_db.log_agent_activity = MagicMock()
            mock_db.update_project_status = MagicMock()
            
            # Mock successful download
            def mock_download(gcs_url, dest_path):
                import os
                import shutil
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                shutil.copy(mock_dataset_zip, dest_path)
            
            mock_storage.download_dataset.side_effect = mock_download
            mock_storage.upload_model.side_effect = Exception("Upload quota exceeded")
            
            result = await execute_training("test-project-123")
            
            assert result["success"] is False
            assert "failed to upload" in result["error"].lower()
            mock_db.update_project_status.assert_called_with("test-project-123", "failed")
    
    async def test_model_initialization_error(
        self,
        mock_dataset_zip,
        mock_project_data,
        mock_dataset_data
    ):
        """Test handling of model initialization failure."""
        with patch('agent.services.training_service.db_service') as mock_db, \
             patch('agent.services.training_service.storage_service') as mock_storage, \
             patch('agent.services.training_service.create_model') as mock_create_model:
            
            # Setup project with unsupported model
            invalid_project = mock_project_data.copy()
            invalid_project["metadata"]["preferred_model"] = "unsupported_model"
            
            mock_db.get_project.return_value = invalid_project
            mock_db.get_dataset.return_value = mock_dataset_data
            mock_db.log_agent_activity = MagicMock()
            mock_db.update_project_status = MagicMock()
            
            # Mock successful download
            def mock_download(gcs_url, dest_path):
                import os
                import shutil
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                shutil.copy(mock_dataset_zip, dest_path)
            
            mock_storage.download_dataset.side_effect = mock_download
            mock_create_model.side_effect = ValueError("Unsupported model")
            
            result = await execute_training("test-project-123")
            
            assert result["success"] is False
            assert "failed to initialize model" in result["error"].lower()
            mock_db.update_project_status.assert_called_with("test-project-123", "failed")
    
    async def test_database_update_error(
        self,
        mock_dataset_zip,
        mock_project_data,
        mock_dataset_data
    ):
        """Test handling of database update failure after training."""
        with patch('agent.services.training_service.db_service') as mock_db, \
             patch('agent.services.training_service.storage_service') as mock_storage:
            
            mock_db.get_project.return_value = mock_project_data
            mock_db.get_dataset.return_value = mock_dataset_data
            mock_db.log_agent_activity = MagicMock()
            
            # Mock successful download and upload
            def mock_download(gcs_url, dest_path):
                import os
                import shutil
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                shutil.copy(mock_dataset_zip, dest_path)
            
            mock_storage.download_dataset.side_effect = mock_download
            mock_storage.upload_model.return_value = "gs://test-bucket/models/test_model.pth"
            
            # Mock database insert failure
            mock_db.insert_model.side_effect = Exception("Database write failed")
            
            result = await execute_training("test-project-123")
            
            assert result["success"] is False
            assert "failed to update database" in result["error"].lower()


class TestDatabaseServiceErrors:
    """Tests for database service error handling."""
    
    def test_get_project_database_error(self):
        """Test get_project with database error."""
        with patch('agent.services.database_service.create_client') as mock_create:
            mock_client = MagicMock()
            mock_create.return_value = mock_client
            
            # Mock database error
            mock_client.table.return_value.select.return_value.eq.return_value.execute.side_effect = \
                Exception("Connection timeout")
            
            db_service = DatabaseService()
            
            with pytest.raises(Exception) as exc_info:
                db_service.get_project("test-project-123")
            
            assert "failed to retrieve project" in str(exc_info.value).lower()
    
    def test_insert_model_database_error(self):
        """Test insert_model with database error."""
        with patch('agent.services.database_service.create_client') as mock_create:
            mock_client = MagicMock()
            mock_create.return_value = mock_client
            
            # Mock database error
            mock_client.table.return_value.insert.return_value.execute.side_effect = \
                Exception("Write failed")
            
            db_service = DatabaseService()
            
            from agent.models.schemas import ModelData
            model_data = ModelData(
                project_id="test-project",
                name="test_model",
                framework="pytorch",
                gcs_url="gs://bucket/model.pth",
                metadata={}
            )
            
            with pytest.raises(Exception) as exc_info:
                db_service.insert_model(model_data)
            
            assert "failed to insert model" in str(exc_info.value).lower()


class TestStorageServiceErrors:
    """Tests for storage service error handling."""
    
    def test_parse_gcs_url_invalid_format(self):
        """Test parse_gcs_url with invalid URL format."""
        with pytest.raises(ValueError) as exc_info:
            StorageService.parse_gcs_url("http://invalid-url.com/file.zip")
        
        assert "invalid gcs url format" in str(exc_info.value).lower()
    
    def test_parse_gcs_url_missing_path(self):
        """Test parse_gcs_url with missing path."""
        with pytest.raises(ValueError) as exc_info:
            StorageService.parse_gcs_url("gs://bucket-only")
        
        assert "invalid gcs url format" in str(exc_info.value).lower()
    
    def test_download_dataset_invalid_url(self, temp_dir):
        """Test download_dataset with invalid GCS URL."""
        with patch('agent.services.storage_service.storage.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            
            storage_service = StorageService()
            
            with pytest.raises(ValueError):
                storage_service.download_dataset(
                    "invalid-url",
                    f"{temp_dir}/dataset.zip"
                )
    
    def test_upload_model_file_not_found(self, temp_dir):
        """Test upload_model with non-existent file."""
        with patch('agent.services.storage_service.storage.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            
            storage_service = StorageService()
            
            with pytest.raises(FileNotFoundError):
                storage_service.upload_model(
                    f"{temp_dir}/nonexistent.pth",
                    "test_project"
                )
