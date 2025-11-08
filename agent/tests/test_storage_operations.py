"""
Integration tests for GCP storage operations.

Tests download, upload, and verification operations with mocked GCS client.
"""
import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock
from google.api_core.exceptions import GoogleAPIError, NotFound
from agent.services.storage_service import StorageService


class TestStorageOperations:
    """Tests for storage service operations."""
    
    def test_parse_gcs_url_valid(self):
        """Test parsing valid GCS URL."""
        bucket, path = StorageService.parse_gcs_url("gs://my-bucket/raw/dataset.zip")
        
        assert bucket == "my-bucket"
        assert path == "raw/dataset.zip"
    
    def test_parse_gcs_url_nested_path(self):
        """Test parsing GCS URL with nested path."""
        bucket, path = StorageService.parse_gcs_url("gs://bucket/path/to/deep/file.pth")
        
        assert bucket == "bucket"
        assert path == "path/to/deep/file.pth"
    
    def test_parse_gcs_url_invalid_prefix(self):
        """Test parsing URL without gs:// prefix."""
        with pytest.raises(ValueError) as exc_info:
            StorageService.parse_gcs_url("http://bucket/file.zip")
        
        assert "must start with 'gs://'" in str(exc_info.value).lower()
    
    def test_parse_gcs_url_no_path(self):
        """Test parsing URL without path component."""
        with pytest.raises(ValueError) as exc_info:
            StorageService.parse_gcs_url("gs://bucket-only")
        
        assert "must include bucket and path" in str(exc_info.value).lower()
    
    def test_download_dataset_success(self, temp_dir):
        """Test successful dataset download."""
        with patch('agent.services.storage_service.storage.Client') as mock_client_class:
            # Setup mocks
            mock_client = MagicMock()
            mock_bucket = MagicMock()
            mock_blob = MagicMock()
            
            mock_client_class.return_value = mock_client
            mock_client.bucket.return_value = mock_bucket
            mock_bucket.blob.return_value = mock_blob
            
            # Mock successful download
            def mock_download(dest_path):
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                with open(dest_path, 'w') as f:
                    f.write("mock dataset content")
            
            mock_blob.download_to_filename.side_effect = mock_download
            
            # Create storage service and download
            storage_service = StorageService()
            dest_path = os.path.join(temp_dir, "dataset.zip")
            
            storage_service.download_dataset("gs://test-bucket/raw/dataset.zip", dest_path)
            
            # Verify file was created
            assert os.path.exists(dest_path)
            
            # Verify GCS calls
            mock_client.bucket.assert_called_with("test-bucket")
            mock_bucket.blob.assert_called_with("raw/dataset.zip")
            mock_blob.download_to_filename.assert_called_once()
    
    def test_download_dataset_with_retry(self, temp_dir):
        """Test dataset download with retry on failure."""
        with patch('agent.services.storage_service.storage.Client') as mock_client_class, \
             patch('agent.services.storage_service.time.sleep'):  # Mock sleep to speed up test
            
            # Setup mocks
            mock_client = MagicMock()
            mock_bucket = MagicMock()
            mock_blob = MagicMock()
            
            mock_client_class.return_value = mock_client
            mock_client.bucket.return_value = mock_bucket
            mock_bucket.blob.return_value = mock_blob
            
            # Mock first failure, then success
            call_count = [0]
            
            def mock_download(dest_path):
                call_count[0] += 1
                if call_count[0] == 1:
                    raise GoogleAPIError("Temporary network error")
                else:
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    with open(dest_path, 'w') as f:
                        f.write("mock dataset content")
            
            mock_blob.download_to_filename.side_effect = mock_download
            
            # Create storage service and download
            storage_service = StorageService()
            dest_path = os.path.join(temp_dir, "dataset.zip")
            
            storage_service.download_dataset("gs://test-bucket/raw/dataset.zip", dest_path)
            
            # Verify file was created after retry
            assert os.path.exists(dest_path)
            assert call_count[0] == 2  # First attempt failed, second succeeded
    
    def test_download_dataset_max_retries_exceeded(self, temp_dir):
        """Test dataset download failure after max retries."""
        with patch('agent.services.storage_service.storage.Client') as mock_client_class, \
             patch('agent.services.storage_service.time.sleep'):
            
            # Setup mocks
            mock_client = MagicMock()
            mock_bucket = MagicMock()
            mock_blob = MagicMock()
            
            mock_client_class.return_value = mock_client
            mock_client.bucket.return_value = mock_bucket
            mock_bucket.blob.return_value = mock_blob
            
            # Mock persistent failure
            mock_blob.download_to_filename.side_effect = GoogleAPIError("Persistent error")
            
            # Create storage service and attempt download
            storage_service = StorageService()
            dest_path = os.path.join(temp_dir, "dataset.zip")
            
            with pytest.raises(GoogleAPIError) as exc_info:
                storage_service.download_dataset("gs://test-bucket/raw/dataset.zip", dest_path)
            
            assert "failed to download dataset" in str(exc_info.value).lower()
    
    def test_upload_model_success(self, temp_dir):
        """Test successful model upload."""
        with patch('agent.services.storage_service.storage.Client') as mock_client_class:
            # Setup mocks
            mock_client = MagicMock()
            mock_bucket = MagicMock()
            mock_blob = MagicMock()
            
            mock_client_class.return_value = mock_client
            mock_client.bucket.return_value = mock_bucket
            mock_bucket.blob.return_value = mock_blob
            mock_blob.exists.return_value = True
            
            # Create a test model file
            model_path = os.path.join(temp_dir, "test_model.pth")
            with open(model_path, 'w') as f:
                f.write("mock model weights")
            
            # Create storage service and upload
            storage_service = StorageService()
            gcs_url = storage_service.upload_model(model_path, "test_project")
            
            # Verify GCS URL
            assert gcs_url == "gs://test-bucket/models/test_project_model.pth"
            
            # Verify GCS calls
            mock_bucket.blob.assert_called_with("models/test_project_model.pth")
            mock_blob.upload_from_filename.assert_called_once_with(model_path)
            mock_blob.exists.assert_called_once()
    
    def test_upload_model_file_not_found(self, temp_dir):
        """Test model upload with non-existent file."""
        with patch('agent.services.storage_service.storage.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            
            storage_service = StorageService()
            
            with pytest.raises(FileNotFoundError):
                storage_service.upload_model(
                    os.path.join(temp_dir, "nonexistent.pth"),
                    "test_project"
                )
    
    def test_upload_model_with_retry(self, temp_dir):
        """Test model upload with retry on failure."""
        with patch('agent.services.storage_service.storage.Client') as mock_client_class, \
             patch('agent.services.storage_service.time.sleep'):
            
            # Setup mocks
            mock_client = MagicMock()
            mock_bucket = MagicMock()
            mock_blob = MagicMock()
            
            mock_client_class.return_value = mock_client
            mock_client.bucket.return_value = mock_bucket
            mock_bucket.blob.return_value = mock_blob
            mock_blob.exists.return_value = True
            
            # Create a test model file
            model_path = os.path.join(temp_dir, "test_model.pth")
            with open(model_path, 'w') as f:
                f.write("mock model weights")
            
            # Mock first failure, then success
            call_count = [0]
            
            def mock_upload(source_path):
                call_count[0] += 1
                if call_count[0] == 1:
                    raise GoogleAPIError("Temporary upload error")
            
            mock_blob.upload_from_filename.side_effect = mock_upload
            
            # Create storage service and upload
            storage_service = StorageService()
            gcs_url = storage_service.upload_model(model_path, "test_project")
            
            # Verify upload succeeded after retry
            assert gcs_url == "gs://test-bucket/models/test_project_model.pth"
            assert call_count[0] == 2
    
    def test_upload_model_max_retries_exceeded(self, temp_dir):
        """Test model upload failure after max retries."""
        with patch('agent.services.storage_service.storage.Client') as mock_client_class, \
             patch('agent.services.storage_service.time.sleep'):
            
            # Setup mocks
            mock_client = MagicMock()
            mock_bucket = MagicMock()
            mock_blob = MagicMock()
            
            mock_client_class.return_value = mock_client
            mock_client.bucket.return_value = mock_bucket
            mock_bucket.blob.return_value = mock_blob
            
            # Create a test model file
            model_path = os.path.join(temp_dir, "test_model.pth")
            with open(model_path, 'w') as f:
                f.write("mock model weights")
            
            # Mock persistent failure
            mock_blob.upload_from_filename.side_effect = GoogleAPIError("Persistent upload error")
            
            # Create storage service and attempt upload
            storage_service = StorageService()
            
            with pytest.raises(GoogleAPIError) as exc_info:
                storage_service.upload_model(model_path, "test_project")
            
            assert "failed to upload model" in str(exc_info.value).lower()
    
    def test_verify_upload_success(self):
        """Test successful upload verification."""
        with patch('agent.services.storage_service.storage.Client') as mock_client_class:
            # Setup mocks
            mock_client = MagicMock()
            mock_bucket = MagicMock()
            mock_blob = MagicMock()
            
            mock_client_class.return_value = mock_client
            mock_client.bucket.return_value = mock_bucket
            mock_bucket.blob.return_value = mock_blob
            mock_blob.exists.return_value = True
            
            # Create storage service and verify
            storage_service = StorageService()
            result = storage_service.verify_upload("gs://test-bucket/models/test_model.pth")
            
            # Verify result
            assert result is True
            mock_blob.exists.assert_called_once()
    
    def test_verify_upload_file_not_found(self):
        """Test upload verification when file doesn't exist."""
        with patch('agent.services.storage_service.storage.Client') as mock_client_class:
            # Setup mocks
            mock_client = MagicMock()
            mock_bucket = MagicMock()
            mock_blob = MagicMock()
            
            mock_client_class.return_value = mock_client
            mock_client.bucket.return_value = mock_bucket
            mock_bucket.blob.return_value = mock_blob
            mock_blob.exists.return_value = False
            
            # Create storage service and verify
            storage_service = StorageService()
            result = storage_service.verify_upload("gs://test-bucket/models/test_model.pth")
            
            # Verify result
            assert result is False
    
    def test_verify_upload_exception(self):
        """Test upload verification with exception."""
        with patch('agent.services.storage_service.storage.Client') as mock_client_class:
            # Setup mocks
            mock_client = MagicMock()
            mock_bucket = MagicMock()
            mock_blob = MagicMock()
            
            mock_client_class.return_value = mock_client
            mock_client.bucket.return_value = mock_bucket
            mock_bucket.blob.return_value = mock_blob
            mock_blob.exists.side_effect = Exception("Connection error")
            
            # Create storage service and verify
            storage_service = StorageService()
            result = storage_service.verify_upload("gs://test-bucket/models/test_model.pth")
            
            # Verify result (should return False on exception)
            assert result is False
