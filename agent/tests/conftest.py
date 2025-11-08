"""
Pytest configuration and shared fixtures for integration tests.
"""
import os
import pytest
import tempfile
import shutil
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
import zipfile
from PIL import Image
import numpy as np


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    with patch('agent.config.settings') as mock:
        mock.supabase_url = "https://test.supabase.co"
        mock.supabase_key = "test-key"
        mock.gcp_bucket_name = "test-bucket"
        mock.google_application_credentials = "/tmp/test-credentials.json"
        mock.log_level = "INFO"
        mock.batch_size = 4
        mock.default_epochs = 2
        mock.default_learning_rate = 0.001
        yield mock


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    # Cleanup after test
    if os.path.exists(temp_path):
        shutil.rmtree(temp_path)


@pytest.fixture
def mock_dataset_zip(temp_dir):
    """Create a mock dataset zip file with proper structure."""
    dataset_dir = os.path.join(temp_dir, "dataset")
    
    # Create train/val/test directories with class subdirectories
    for split in ['train', 'val', 'test']:
        for class_name in ['class1', 'class2', 'class3']:
            class_dir = os.path.join(dataset_dir, split, class_name)
            os.makedirs(class_dir, exist_ok=True)
            
            # Create a few dummy images in each class
            num_images = 5 if split == 'train' else 2
            for i in range(num_images):
                img_path = os.path.join(class_dir, f"image_{i}.jpg")
                # Create a small random RGB image
                img = Image.fromarray(np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8))
                img.save(img_path)
    
    # Create zip file
    zip_path = os.path.join(temp_dir, "dataset.zip")
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for root, dirs, files in os.walk(dataset_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, temp_dir)
                zipf.write(file_path, arcname)
    
    return zip_path


@pytest.fixture
def mock_project_data():
    """Mock project data from database."""
    return {
        "id": "test-project-123",
        "name": "test_project",
        "task_type": "image_classification",
        "framework": "pytorch",
        "status": "pending_training",
        "metadata": {
            "preferred_model": "resnet18",
            "epochs": 2,
            "learning_rate": 0.001,
            "num_classes": 3
        },
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00"
    }


@pytest.fixture
def mock_dataset_data():
    """Mock dataset data from database."""
    return {
        "id": "test-dataset-456",
        "project_id": "test-project-123",
        "name": "test_dataset",
        "gcs_url": "gs://test-bucket/raw/dataset.zip",
        "size": "1.2 MB",
        "source": "test",
        "created_at": "2024-01-01T00:00:00"
    }


@pytest.fixture
def mock_supabase_client(mock_project_data, mock_dataset_data):
    """Mock Supabase client for database operations."""
    mock_client = MagicMock()
    
    # Mock table operations
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    
    # Mock select operations
    mock_select = MagicMock()
    mock_table.select.return_value = mock_select
    
    # Mock eq operations
    mock_eq = MagicMock()
    mock_select.eq.return_value = mock_eq
    
    # Mock execute for projects table
    def execute_side_effect(*args, **kwargs):
        mock_response = MagicMock()
        # Determine which table is being queried based on call stack
        if hasattr(mock_table, '_last_table_name'):
            if mock_table._last_table_name == 'projects':
                mock_response.data = [mock_project_data]
            elif mock_table._last_table_name == 'datasets':
                mock_response.data = [mock_dataset_data]
            elif mock_table._last_table_name == 'agent_logs':
                mock_response.data = []
            else:
                mock_response.data = []
        else:
            mock_response.data = []
        return mock_response
    
    mock_eq.execute.side_effect = execute_side_effect
    
    # Track table name
    def table_side_effect(table_name):
        mock_table._last_table_name = table_name
        return mock_table
    
    mock_client.table.side_effect = table_side_effect
    
    # Mock insert operations
    mock_insert = MagicMock()
    mock_table.insert.return_value = mock_insert
    mock_insert.execute.return_value = MagicMock(data=[{"id": "new-id"}])
    
    # Mock update operations
    mock_update = MagicMock()
    mock_table.update.return_value = mock_update
    mock_update.eq.return_value = mock_eq
    
    # Mock order and limit for logs
    mock_order = MagicMock()
    mock_eq.order.return_value = mock_order
    mock_limit = MagicMock()
    mock_order.limit.return_value = mock_limit
    mock_limit.execute.return_value = MagicMock(data=[])
    
    return mock_client


@pytest.fixture
def mock_gcs_client(mock_dataset_zip, temp_dir):
    """Mock Google Cloud Storage client."""
    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    
    mock_client.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob
    
    # Mock download - copy the mock dataset zip to destination
    def download_to_filename(dest_path):
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        shutil.copy(mock_dataset_zip, dest_path)
    
    mock_blob.download_to_filename.side_effect = download_to_filename
    
    # Mock upload
    def upload_from_filename(source_path):
        # Just verify file exists
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Source file not found: {source_path}")
    
    mock_blob.upload_from_filename.side_effect = upload_from_filename
    
    # Mock exists check
    mock_blob.exists.return_value = True
    
    return mock_client
