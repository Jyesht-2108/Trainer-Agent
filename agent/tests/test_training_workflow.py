"""
Integration tests for the complete training workflow.

Tests the end-to-end training process with mock dataset and services.
"""
import pytest
import os
from unittest.mock import patch, MagicMock
from agent.services.training_service import execute_training


@pytest.mark.asyncio
class TestTrainingWorkflow:
    """Tests for complete training workflow."""
    
    async def test_complete_training_workflow_success(
        self,
        mock_supabase_client,
        mock_gcs_client,
        mock_dataset_zip,
        temp_dir,
        mock_project_data,
        mock_dataset_data
    ):
        """Test successful end-to-end training workflow."""
        with patch('agent.services.database_service.create_client', return_value=mock_supabase_client), \
             patch('agent.services.storage_service.storage.Client', return_value=mock_gcs_client), \
             patch('agent.services.training_service.db_service') as mock_db, \
             patch('agent.services.training_service.storage_service') as mock_storage:
            
            # Setup mocks
            mock_db.get_project.return_value = mock_project_data
            mock_db.get_dataset.return_value = mock_dataset_data
            mock_db.log_agent_activity = MagicMock()
            mock_db.insert_model = MagicMock()
            mock_db.update_project_status = MagicMock()
            
            # Mock storage operations
            def mock_download(gcs_url, dest_path):
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                import shutil
                shutil.copy(mock_dataset_zip, dest_path)
            
            mock_storage.download_dataset.side_effect = mock_download
            mock_storage.upload_model.return_value = "gs://test-bucket/models/test_project_model.pth"
            
            # Execute training
            result = await execute_training("test-project-123")
            
            # Verify success
            assert result["success"] is True
            assert "model_url" in result
            assert result["model_url"] == "gs://test-bucket/models/test_project_model.pth"
            
            # Verify database calls
            mock_db.get_project.assert_called_once_with("test-project-123")
            mock_db.get_dataset.assert_called_once_with("test-project-123")
            mock_db.insert_model.assert_called_once()
            mock_db.update_project_status.assert_called_with("test-project-123", "pending_evaluation")
            
            # Verify storage calls
            mock_storage.download_dataset.assert_called_once()
            mock_storage.upload_model.assert_called_once()
    
    async def test_training_workflow_invalid_status(
        self,
        mock_supabase_client,
        mock_project_data
    ):
        """Test training workflow with invalid project status."""
        with patch('agent.services.training_service.db_service') as mock_db:
            # Setup project with wrong status
            invalid_project = mock_project_data.copy()
            invalid_project["status"] = "completed"
            
            mock_db.get_project.return_value = invalid_project
            mock_db.log_agent_activity = MagicMock()
            
            # Execute training
            result = await execute_training("test-project-123")
            
            # Verify failure
            assert result["success"] is False
            assert "status" in result["error"].lower()
            assert "pending_training" in result["error"].lower()
    
    async def test_training_workflow_project_not_found(self):
        """Test training workflow with non-existent project."""
        with patch('agent.services.training_service.db_service') as mock_db:
            # Setup mock to return None
            mock_db.get_project.return_value = None
            mock_db.log_agent_activity = MagicMock()
            
            # Execute training
            result = await execute_training("test-project-999")
            
            # Verify failure
            assert result["success"] is False
            assert "not found" in result["error"].lower()
    
    async def test_training_workflow_dataset_not_found(
        self,
        mock_project_data
    ):
        """Test training workflow with missing dataset."""
        with patch('agent.services.training_service.db_service') as mock_db:
            # Setup mocks
            mock_db.get_project.return_value = mock_project_data
            mock_db.get_dataset.return_value = None
            mock_db.log_agent_activity = MagicMock()
            mock_db.update_project_status = MagicMock()
            
            # Execute training
            result = await execute_training("test-project-123")
            
            # Verify failure
            assert result["success"] is False
            assert "dataset not found" in result["error"].lower()
            
            # Verify status updated to failed
            mock_db.update_project_status.assert_called_with("test-project-123", "failed")
    
    async def test_training_workflow_download_failure(
        self,
        mock_project_data,
        mock_dataset_data
    ):
        """Test training workflow with dataset download failure."""
        with patch('agent.services.training_service.db_service') as mock_db, \
             patch('agent.services.training_service.storage_service') as mock_storage:
            
            # Setup mocks
            mock_db.get_project.return_value = mock_project_data
            mock_db.get_dataset.return_value = mock_dataset_data
            mock_db.log_agent_activity = MagicMock()
            mock_db.update_project_status = MagicMock()
            
            # Mock download failure
            mock_storage.download_dataset.side_effect = Exception("Download failed")
            
            # Execute training
            result = await execute_training("test-project-123")
            
            # Verify failure
            assert result["success"] is False
            assert "failed to download dataset" in result["error"].lower()
            
            # Verify status updated to failed
            mock_db.update_project_status.assert_called_with("test-project-123", "failed")
    
    async def test_training_workflow_invalid_dataset_structure(
        self,
        mock_project_data,
        mock_dataset_data,
        temp_dir
    ):
        """Test training workflow with invalid dataset structure."""
        with patch('agent.services.training_service.db_service') as mock_db, \
             patch('agent.services.training_service.storage_service') as mock_storage:
            
            # Setup mocks
            mock_db.get_project.return_value = mock_project_data
            mock_db.get_dataset.return_value = mock_dataset_data
            mock_db.log_agent_activity = MagicMock()
            mock_db.update_project_status = MagicMock()
            
            # Create invalid dataset (missing required folders)
            import zipfile
            invalid_zip = os.path.join(temp_dir, "invalid.zip")
            with zipfile.ZipFile(invalid_zip, 'w') as zipf:
                zipf.writestr("random_file.txt", "invalid structure")
            
            def mock_download(gcs_url, dest_path):
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                import shutil
                shutil.copy(invalid_zip, dest_path)
            
            mock_storage.download_dataset.side_effect = mock_download
            
            # Execute training
            result = await execute_training("test-project-123")
            
            # Verify failure
            assert result["success"] is False
            assert "invalid dataset structure" in result["error"].lower()
            
            # Verify status updated to failed
            mock_db.update_project_status.assert_called_with("test-project-123", "failed")
    
    async def test_training_workflow_upload_failure(
        self,
        mock_supabase_client,
        mock_gcs_client,
        mock_dataset_zip,
        mock_project_data,
        mock_dataset_data
    ):
        """Test training workflow with model upload failure."""
        with patch('agent.services.database_service.create_client', return_value=mock_supabase_client), \
             patch('agent.services.storage_service.storage.Client', return_value=mock_gcs_client), \
             patch('agent.services.training_service.db_service') as mock_db, \
             patch('agent.services.training_service.storage_service') as mock_storage:
            
            # Setup mocks
            mock_db.get_project.return_value = mock_project_data
            mock_db.get_dataset.return_value = mock_dataset_data
            mock_db.log_agent_activity = MagicMock()
            mock_db.update_project_status = MagicMock()
            
            # Mock storage operations
            def mock_download(gcs_url, dest_path):
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                import shutil
                shutil.copy(mock_dataset_zip, dest_path)
            
            mock_storage.download_dataset.side_effect = mock_download
            mock_storage.upload_model.side_effect = Exception("Upload failed")
            
            # Execute training
            result = await execute_training("test-project-123")
            
            # Verify failure
            assert result["success"] is False
            assert "failed to upload model" in result["error"].lower()
            
            # Verify status updated to failed
            mock_db.update_project_status.assert_called_with("test-project-123", "failed")
