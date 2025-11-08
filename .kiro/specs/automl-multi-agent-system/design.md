# Design Document

## Overview

The Training Agent is a FastAPI-based microservice that orchestrates the model training workflow for the AutoML Multi-Agent System. It acts as a bridge between cloud storage (GCP), the Supabase database, and local PyTorch training infrastructure. The agent follows a stateless design pattern where all state is persisted in Supabase, enabling horizontal scaling and fault tolerance.

The agent's core workflow consists of: (1) retrieving project and dataset metadata from Supabase, (2) downloading datasets from GCP, (3) training PyTorch models locally, (4) uploading trained models to GCP, and (5) updating Supabase with model metadata and status transitions.

## Architecture

### High-Level Architecture

```
MCP Server
    ↓ (HTTP POST /agents/training/start)
Training Agent (FastAPI)
    ↓ (read)
Supabase Database (projects, datasets tables)
    ↓ (download)
GCP Bucket (raw/dataset.zip)
    ↓ (local training)
PyTorch Training Loop
    ↓ (upload)
GCP Bucket (models/model.pth)
    ↓ (write)
Supabase Database (models table, status update)
```

### Component Architecture

The Training Agent consists of the following layers:

1. **API Layer** (FastAPI): Exposes REST endpoints for triggering training and querying status
2. **Service Layer**: Orchestrates the training workflow and coordinates between components
3. **Storage Layer**: Handles GCP bucket interactions for download/upload operations
4. **Training Layer**: Manages PyTorch model initialization, data loading, and training loops
5. **Database Layer**: Manages Supabase interactions for metadata and logging

### Directory Structure

```
agent/
├── main.py                 # FastAPI application entry point
├── config.py              # Environment configuration and settings
├── models/                # Pydantic models for request/response validation
│   ├── __init__.py
│   └── schemas.py         # API schemas and data models
├── services/              # Business logic layer
│   ├── __init__.py
│   ├── training_service.py    # Main training orchestration
│   ├── storage_service.py     # GCP storage operations
│   └── database_service.py    # Supabase operations
├── training/              # PyTorch training logic
│   ├── __init__.py
│   ├── trainer.py         # Training loop implementation
│   └── model_factory.py   # Model architecture loading
├── utils/                 # Utility functions
│   ├── __init__.py
│   ├── logger.py          # Logging configuration
│   └── file_utils.py      # File operations (unzip, cleanup)
└── requirements.txt       # Python dependencies
```

## Components and Interfaces

### 1. API Layer (main.py)

**Purpose**: Expose HTTP endpoints for the MCP Server to trigger training jobs and query status.

**Endpoints**:

- `POST /agents/training/start`
  - Request: `{"project_id": "uuid"}`
  - Response: `{"success": true, "model_url": "gs://bucket/path"}`
  - Triggers the complete training workflow

- `GET /agents/training/status/{project_id}`
  - Response: `{"status": "training", "progress": {...}, "logs": [...]}`
  - Returns current training status and recent logs

- `GET /health`
  - Response: `{"status": "healthy", "timestamp": "..."}`
  - Health check endpoint for monitoring

**Key Classes**:
- `TrainingRequest`: Pydantic model for validating incoming requests
- `TrainingResponse`: Pydantic model for response formatting

### 2. Configuration (config.py)

**Purpose**: Centralize environment variable management and application settings.

**Configuration Class**:
```python
class Settings:
    supabase_url: str
    supabase_key: str
    gcp_bucket_name: str
    google_application_credentials: str
    log_level: str = "INFO"
    batch_size: int = 32
    default_epochs: int = 10
    default_learning_rate: float = 0.001
```

### 3. Database Service (database_service.py)

**Purpose**: Abstract Supabase interactions and provide type-safe database operations.

**Key Methods**:
- `get_project(project_id: str) -> dict`: Retrieve project metadata
- `get_dataset(project_id: str) -> dict`: Retrieve dataset metadata
- `insert_model(model_data: dict) -> dict`: Insert trained model record
- `update_project_status(project_id: str, status: str)`: Update project status
- `log_agent_activity(project_id: str, message: str, level: str)`: Write to agent_logs

**Database Schema Integration**:
- **projects table**: Read metadata (name, task_type, framework, metadata JSON)
- **datasets table**: Read gcs_url and dataset info
- **models table**: Insert model metadata (project_id, name, framework, gcs_url, metadata)
- **agent_logs table**: Insert training progress and error logs

### 4. Storage Service (storage_service.py)

**Purpose**: Handle all GCP bucket operations for dataset download and model upload.

**Key Methods**:
- `parse_gcs_url(gcs_url: str) -> tuple[str, str]`: Extract bucket and blob path
- `download_dataset(gcs_url: str, dest_path: str)`: Download dataset from GCP
- `upload_model(local_path: str, project_name: str) -> str`: Upload model and return GCS URL
- `verify_upload(gcs_url: str) -> bool`: Verify file exists in bucket

**GCP Authentication**:
- Uses service account credentials from `GOOGLE_APPLICATION_CREDENTIALS` environment variable
- Requires read permissions on `raw/*` and write permissions on `models/*`

### 5. Training Service (training_service.py)

**Purpose**: Orchestrate the complete training workflow from dataset download to model upload.

**Main Workflow Method**:
```python
async def execute_training(project_id: str) -> dict:
    1. Validate project status
    2. Fetch project and dataset metadata
    3. Download dataset from GCP
    4. Extract and prepare dataset
    5. Initialize model architecture
    6. Execute training loop
    7. Upload trained model to GCP
    8. Update Supabase metadata
    9. Clean up temporary files
    10. Return success response
```

**Error Handling**:
- Wrap each step in try-except blocks
- Log errors to agent_logs table
- Update project status to "failed" on critical errors
- Clean up temporary files in finally block

### 6. Model Factory (model_factory.py)

**Purpose**: Load and configure PyTorch model architectures based on project metadata.

**Key Methods**:
- `create_model(model_name: str, num_classes: int) -> nn.Module`: Load pretrained model and modify final layer
- `get_supported_models() -> list[str]`: Return list of available architectures

**Supported Models**:
- ResNet18, ResNet34, ResNet50
- MobileNetV2
- EfficientNet-B0

**Model Initialization**:
- Load pretrained weights from ImageNet
- Replace final fully connected layer with new layer matching num_classes
- Return model ready for training

### 7. Trainer (trainer.py)

**Purpose**: Implement the PyTorch training loop with data loading and optimization.

**Key Class**:
```python
class ModelTrainer:
    def __init__(self, model, data_dir, num_classes, epochs, lr, batch_size)
    def prepare_data_loaders() -> tuple[DataLoader, DataLoader]
    def train() -> nn.Module
    def _train_epoch(epoch: int) -> float
    def save_model(path: str)
```

**Training Configuration**:
- **Transforms**: Resize(224, 224), ToTensor(), Normalize(ImageNet stats)
- **Loss Function**: CrossEntropyLoss
- **Optimizer**: Adam with configurable learning rate
- **Data Loading**: ImageFolder with train/val splits

**Logging During Training**:
- Log epoch number and loss to agent_logs after each epoch
- Log total training time on completion

### 8. File Utils (file_utils.py)

**Purpose**: Handle file system operations for dataset extraction and cleanup.

**Key Methods**:
- `unzip_dataset(zip_path: str, extract_dir: str)`: Extract dataset archive
- `validate_dataset_structure(data_dir: str) -> bool`: Verify train/val/test folders exist
- `count_classes(train_dir: str) -> int`: Count subdirectories in train folder
- `cleanup_temp_files(paths: list[str])`: Remove temporary files and directories

## Data Models

### Request/Response Models (Pydantic)

```python
class TrainingRequest(BaseModel):
    project_id: str

class TrainingResponse(BaseModel):
    success: bool
    model_url: Optional[str] = None
    error: Optional[str] = None

class StatusResponse(BaseModel):
    status: str
    progress: dict
    logs: list[dict]
```

### Database Models

**Projects Table** (read):
```python
{
    "id": "uuid",
    "name": "Project Name",
    "task_type": "image_classification",
    "framework": "pytorch",
    "status": "pending_training",
    "metadata": {
        "preferred_model": "resnet18",
        "epochs": 10,
        "learning_rate": 0.001,
        "num_classes": 5
    }
}
```

**Datasets Table** (read):
```python
{
    "id": "uuid",
    "project_id": "uuid",
    "name": "dataset_name",
    "gcs_url": "gs://bucket/raw/dataset.zip",
    "size": "4.2 GB",
    "source": "kaggle"
}
```

**Models Table** (write):
```python
{
    "id": "uuid",
    "project_id": "uuid",
    "name": "project_name_model",
    "framework": "pytorch",
    "gcs_url": "gs://bucket/models/project_name_model.pth",
    "metadata": {
        "epochs": 10,
        "final_loss": 0.234,
        "training_time_seconds": 1234
    }
}
```

**Agent Logs Table** (write):
```python
{
    "id": "uuid",
    "project_id": "uuid",
    "agent_name": "training",
    "message": "Epoch 5/10 completed. Loss: 0.456",
    "log_level": "info",
    "created_at": "timestamp"
}
```

## Error Handling

### Error Categories

1. **Validation Errors** (400):
   - Invalid project_id format
   - Project status not "pending_training"
   - Missing required metadata fields

2. **Resource Errors** (404):
   - Project not found in database
   - Dataset not found for project
   - GCS file not found

3. **Storage Errors** (500):
   - GCP authentication failure
   - Download/upload timeout
   - Insufficient disk space

4. **Training Errors** (500):
   - Invalid dataset structure
   - Model initialization failure
   - Out of memory during training

### Error Handling Strategy

```python
try:
    # Execute training workflow
    result = await training_service.execute_training(project_id)
except ValidationError as e:
    # Log to agent_logs
    # Return 400 response
except ResourceNotFoundError as e:
    # Log to agent_logs
    # Return 404 response
except Exception as e:
    # Log to agent_logs with stack trace
    # Update project status to "failed"
    # Return 500 response
finally:
    # Clean up temporary files
```

### Retry Logic

- **GCP Downloads**: Retry once with exponential backoff
- **GCP Uploads**: Retry once before failing
- **Supabase Operations**: No retry (fail fast)

## Testing Strategy

### Unit Tests

1. **Storage Service Tests**:
   - Test GCS URL parsing
   - Mock GCP client for download/upload
   - Test error handling for missing files

2. **Database Service Tests**:
   - Mock Supabase client
   - Test CRUD operations
   - Test error handling for missing records

3. **Model Factory Tests**:
   - Test model creation for each supported architecture
   - Verify final layer has correct output size
   - Test unsupported model name handling

4. **File Utils Tests**:
   - Test unzip functionality
   - Test dataset structure validation
   - Test class counting logic

### Integration Tests

1. **End-to-End Training Flow**:
   - Use test dataset in GCP bucket
   - Train for 1 epoch
   - Verify model uploaded successfully
   - Verify Supabase updated correctly

2. **API Endpoint Tests**:
   - Test /start endpoint with valid project
   - Test /status endpoint returns correct data
   - Test /health endpoint

### Manual Testing Checklist

- [ ] Training completes successfully with valid dataset
- [ ] Error logged when dataset structure is invalid
- [ ] Model uploaded to correct GCP path
- [ ] Supabase status transitions correctly
- [ ] Temporary files cleaned up after completion
- [ ] Agent logs contain detailed progress information

## Deployment Considerations

### Environment Setup

1. **Python Environment**: Python 3.10+ with virtual environment
2. **Dependencies**: Install from requirements.txt (FastAPI, PyTorch, Supabase, GCP SDK)
3. **Environment Variables**: Configure .env file with all required credentials
4. **GCP Service Account**: JSON key file with bucket read/write permissions

### Running the Service

```bash
# Development
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
```

### Resource Requirements

- **CPU**: 4+ cores recommended for training
- **RAM**: 8GB minimum, 16GB recommended
- **Disk**: 50GB for temporary dataset storage
- **GPU**: Optional but recommended for faster training

### Monitoring

- Health check endpoint for uptime monitoring
- Agent logs table for debugging and audit trail
- GCP bucket metrics for storage usage
- FastAPI built-in metrics for request latency

## Security Considerations

1. **Credential Management**:
   - Store all credentials in environment variables
   - Never log sensitive credentials
   - Use service accounts with minimal permissions

2. **Input Validation**:
   - Validate all API inputs with Pydantic
   - Sanitize file paths to prevent directory traversal
   - Validate GCS URLs before download

3. **Resource Limits**:
   - Limit maximum dataset size
   - Timeout long-running downloads
   - Prevent disk space exhaustion

4. **Network Security**:
   - Use HTTPS for all external API calls
   - Validate SSL certificates
   - Implement rate limiting on endpoints
