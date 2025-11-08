"""
Storage service for GCP bucket operations.

This module handles all interactions with Google Cloud Storage including:
- Downloading datasets from GCS buckets
- Uploading trained models to GCS buckets
- Verifying uploads
- Retry logic with exponential backoff

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 6.1, 6.2, 6.3, 6.4, 6.5
"""

import os
import time
from typing import Tuple
from google.cloud import storage
from google.api_core import retry
from google.api_core.exceptions import GoogleAPIError, NotFound

from agent.config import settings


class StorageService:
    """Service for managing GCP Storage operations."""
    
    def __init__(self):
        """
        Initialize GCP Storage client.
        
        Requirements: 2.3, 6.2
        Uses GOOGLE_APPLICATION_CREDENTIALS environment variable for authentication.
        """
        # Set credentials path from settings
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = settings.google_application_credentials
        
        # Initialize storage client
        self.client = storage.Client()
        self.bucket_name = settings.gcp_bucket_name
        self.bucket = self.client.bucket(self.bucket_name)
    
    @staticmethod
    def parse_gcs_url(gcs_url: str) -> Tuple[str, str]:
        """
        Parse GCS URL to extract bucket name and blob path.
        
        Args:
            gcs_url: GCS URL in format gs://bucket-name/path/to/file
            
        Returns:
            Tuple of (bucket_name, blob_path)
            
        Raises:
            ValueError: If URL format is invalid
            
        Requirement: 2.2
        
        Example:
            >>> parse_gcs_url("gs://my-bucket/raw/dataset.zip")
            ("my-bucket", "raw/dataset.zip")
        """
        if not gcs_url.startswith("gs://"):
            raise ValueError(f"Invalid GCS URL format: {gcs_url}. Must start with 'gs://'")
        
        # Remove gs:// prefix
        path = gcs_url[5:]
        
        # Split into bucket and blob path
        parts = path.split("/", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid GCS URL format: {gcs_url}. Must include bucket and path")
        
        bucket_name, blob_path = parts
        return bucket_name, blob_path
    
    def download_dataset(self, gcs_url: str, dest_path: str) -> None:
        """
        Download dataset from GCP bucket to local path with retry logic.
        
        Args:
            gcs_url: GCS URL of the dataset (gs://bucket/path)
            dest_path: Local destination path for the downloaded file
            
        Raises:
            ValueError: If GCS URL is invalid
            NotFound: If file doesn't exist in bucket
            GoogleAPIError: If download fails after retries
            
        Requirements: 2.1, 2.2, 2.3, 2.4
        
        The method implements exponential backoff retry logic:
        - Initial retry after 1 second
        - Maximum retry after 60 seconds
        - Multiplier of 2.0 for exponential backoff
        """
        # Parse GCS URL to get bucket and blob path
        bucket_name, blob_path = self.parse_gcs_url(gcs_url)
        
        # Get bucket and blob
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        
        # Create destination directory if it doesn't exist
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        
        # Download with retry logic (Requirement 2.5)
        max_retries = 2
        retry_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                # Download blob to destination
                blob.download_to_filename(dest_path)
                
                # Verify file was downloaded
                if not os.path.exists(dest_path):
                    raise FileNotFoundError(f"Downloaded file not found at {dest_path}")
                
                return
                
            except (GoogleAPIError, Exception) as e:
                if attempt < max_retries - 1:
                    # Exponential backoff
                    time.sleep(retry_delay)
                    retry_delay *= 2.0
                else:
                    # Final attempt failed
                    raise GoogleAPIError(
                        f"Failed to download dataset from {gcs_url} after {max_retries} attempts: {str(e)}"
                    )
    
    def upload_model(self, local_path: str, project_name: str) -> str:
        """
        Upload trained model file to GCP bucket with retry logic.
        
        Args:
            local_path: Local path to the .pth model file
            project_name: Name of the project (used to construct GCS path)
            
        Returns:
            Full GCS URL of the uploaded model (gs://bucket/models/project_name_model.pth)
            
        Raises:
            FileNotFoundError: If local file doesn't exist
            GoogleAPIError: If upload fails after retries
            
        Requirements: 6.1, 6.2, 6.3, 6.5
        
        The model is uploaded to: models/{project_name}_model.pth
        """
        # Verify local file exists
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Model file not found at {local_path}")
        
        # Construct blob path
        blob_path = f"models/{project_name}_model.pth"
        blob = self.bucket.blob(blob_path)
        
        # Upload with retry logic (Requirement 6.4)
        max_retries = 2
        retry_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                # Upload file to GCS
                blob.upload_from_filename(local_path)
                
                # Construct and return GCS URL
                gcs_url = f"gs://{self.bucket_name}/{blob_path}"
                
                # Verify upload succeeded
                if not self.verify_upload(gcs_url):
                    raise GoogleAPIError(f"Upload verification failed for {gcs_url}")
                
                return gcs_url
                
            except (GoogleAPIError, Exception) as e:
                if attempt < max_retries - 1:
                    # Exponential backoff
                    time.sleep(retry_delay)
                    retry_delay *= 2.0
                else:
                    # Final attempt failed
                    raise GoogleAPIError(
                        f"Failed to upload model to GCS after {max_retries} attempts: {str(e)}"
                    )
    
    def verify_upload(self, gcs_url: str) -> bool:
        """
        Verify that a file exists in the GCP bucket.
        
        Args:
            gcs_url: GCS URL to verify (gs://bucket/path)
            
        Returns:
            True if file exists, False otherwise
            
        Requirement: 6.3
        """
        try:
            # Parse GCS URL
            bucket_name, blob_path = self.parse_gcs_url(gcs_url)
            
            # Get bucket and blob
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(blob_path)
            
            # Check if blob exists
            return blob.exists()
            
        except Exception:
            return False
    
    def upload_bundle(self, local_path: str, filename: str) -> str:
        """
        Upload user bundle (zip file) to GCP bucket.
        
        Args:
            local_path: Local path to the zip file
            filename: Name of the file
            
        Returns:
            Full GCS URL of the uploaded bundle
            
        Raises:
            FileNotFoundError: If local file doesn't exist
            GoogleAPIError: If upload fails
        """
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Bundle file not found at {local_path}")
        
        # Upload to exports folder
        blob_path = f"exports/{filename}"
        blob = self.bucket.blob(blob_path)
        
        # Upload file
        blob.upload_from_filename(local_path)
        
        # Make it publicly accessible (optional)
        # blob.make_public()
        
        gcs_url = f"gs://{self.bucket_name}/{blob_path}"
        return gcs_url
    
    def download_model(self, gcs_url: str, local_path: str) -> None:
        """
        Download model file from GCP bucket.
        
        Args:
            gcs_url: GCS URL of the model
            local_path: Local path to save the model
            
        Raises:
            NotFound: If file doesn't exist in GCS
            GoogleAPIError: If download fails
        """
        bucket_name, blob_path = self.parse_gcs_url(gcs_url)
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        # Download file
        blob.download_to_filename(local_path)


# Global storage service instance
storage_service = StorageService()
