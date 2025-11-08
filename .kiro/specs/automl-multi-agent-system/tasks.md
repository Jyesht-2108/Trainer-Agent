# Implementation Plan

- [x] 1. Set up project structure and configuration
  - Create directory structure (models/, services/, training/, utils/)
  - Create requirements.txt with all dependencies (fastapi, torch, torchvision, supabase, google-cloud-storage, pydantic, python-dotenv, uvicorn)
  - Create config.py to load environment variables using pydantic Settings
  - Create .env.example file documenting required environment variables
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 2. Implement database service layer
  - Create models/schemas.py with Pydantic models for API requests and responses
  - Create services/database_service.py with Supabase client initialization
  - Implement get_project() method to retrieve project by ID
  - Implement get_dataset() method to retrieve dataset by project_id
  - Implement insert_model() method to create model records
  - Implement update_project_status() method to transition project status
  - Implement log_agent_activity() method to write to agent_logs table
  - _Requirements: 1.1, 1.4, 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 3. Implement storage service layer
  - Create services/storage_service.py with GCP Storage client initialization
  - Implement parse_gcs_url() function to extract bucket name and blob path from GCS URLs
  - Implement download_dataset() method to download files from GCP bucket to local path
  - Implement upload_model() method to upload trained model files to GCP bucket
  - Implement verify_upload() method to confirm file exists in bucket after upload
  - Add retry logic for download and upload operations with exponential backoff
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 4. Implement file utilities
  - Create utils/file_utils.py with file system helper functions
  - Implement unzip_dataset() function to extract zip archives
  - Implement validate_dataset_structure() function to verify train/val/test folders exist
  - Implement count_classes() function to count subdirectories in train folder
  - Implement cleanup_temp_files() function to remove temporary files and directories
  - _Requirements: 3.1, 3.2, 3.4, 3.5_

- [x] 5. Implement model factory
  - Create training/model_factory.py for PyTorch model loading
  - Implement create_model() function that loads pretrained models from torchvision
  - Support ResNet18, ResNet34, ResNet50, MobileNetV2, and EfficientNet-B0 architectures
  - Implement logic to replace final fully connected layer with custom layer matching num_classes
  - Implement get_supported_models() function returning list of available architectures
  - _Requirements: 4.1, 4.2, 4.3_

- [x] 6. Implement PyTorch trainer
  - Create training/trainer.py with ModelTrainer class
  - Implement __init__() to accept model, data_dir, num_classes, epochs, lr, and batch_size
  - Implement prepare_data_loaders() to create train and validation DataLoaders with ImageFolder
  - Define image transforms (Resize to 224x224, ToTensor, Normalize with ImageNet stats)
  - Implement train() method with training loop iterating over epochs
  - Implement _train_epoch() helper method to train for one epoch and return loss
  - Initialize CrossEntropyLoss criterion and Adam optimizer in __init__
  - Implement save_model() method to save state_dict to .pth file
  - _Requirements: 4.4, 4.5, 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 7. Implement training orchestration service
  - Create services/training_service.py with execute_training() async function
  - Implement step 1: Validate project status is "pending_training"
  - Implement step 2: Fetch project and dataset metadata using database service
  - Implement step 3: Download dataset from GCP using storage service
  - Implement step 4: Extract dataset and validate structure using file utils
  - Implement step 5: Count classes and initialize model using model factory
  - Implement step 6: Create ModelTrainer instance and execute training
  - Implement step 7: Upload trained model to GCP using storage service
  - Implement step 8: Insert model record and update project status using database service
  - Implement step 9: Clean up temporary files in finally block
  - Add comprehensive error handling with try-except blocks around each step
  - Log all major operations to agent_logs table
  - _Requirements: 1.1, 1.2, 1.3, 1.5, 3.3, 8.1, 8.2, 8.3, 8.4_

- [x] 8. Implement FastAPI endpoints
  - Create main.py with FastAPI app initialization
  - Implement POST /agents/training/start endpoint accepting TrainingRequest
  - Call training_service.execute_training() from start endpoint
  - Return TrainingResponse with success status and model_url
  - Implement GET /agents/training/status/{project_id} endpoint
  - Query agent_logs table for recent logs in status endpoint
  - Implement GET /health endpoint returning service health status
  - Add request validation using Pydantic models
  - Add error handling middleware to catch and format exceptions
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 8.5_

- [x] 9. Implement logging configuration
  - Create utils/logger.py with logging setup
  - Configure logging level from LOG_LEVEL environment variable
  - Set up structured logging format with timestamps and log levels
  - Create helper functions for logging to both stdout and agent_logs table
  - _Requirements: 10.5, 8.3_

- [x] 10. Create integration tests
  - Create tests/ directory with test files
  - Write test for complete training workflow with mock dataset
  - Write test for API endpoints using FastAPI TestClient
  - Write test for error handling scenarios (missing project, invalid dataset)
  - Write test for GCP upload/download with mocked storage client
  - _Requirements: All requirements_

- [ ] 11. Create documentation
  - Create README.md in agent/ folder with setup instructions
  - Document environment variable requirements
  - Document API endpoint usage with example requests
  - Add troubleshooting section for common errors
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_
