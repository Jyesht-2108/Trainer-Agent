# Requirements Document

## Introduction

The Training Agent is a microservice component of the AutoML Multi-Agent System responsible for training PyTorch models. It monitors the Supabase database for projects with status "pending_training", downloads datasets from Google Cloud Storage, trains deep learning models locally, and uploads the trained model weights back to GCS. The agent communicates exclusively through Supabase tables and operates as a stateless FastAPI service that can be triggered by the MCP Server.

## Glossary

- **Training_Agent**: FastAPI microservice that downloads datasets, trains PyTorch models locally, and uploads trained models to GCP.
- **Supabase_Database**: Centralized PostgreSQL database used for agent coordination and metadata storage.
- **GCP_Bucket**: Google Cloud Storage bucket for storing datasets and trained model files.
- **MCP_Server**: Model Context Protocol Server that triggers the Training Agent when project status changes.
- **Project_Metadata**: JSON object stored in the projects table containing training configuration like epochs, model architecture, and number of classes.
- **Model_Weights**: PyTorch state dictionary saved as .pth file containing trained neural network parameters.
- **Dataset_URL**: GCS path (gs://bucket/path) pointing to the zipped dataset uploaded by the Dataset Agent.

## Requirements

### Requirement 1: Training Agent Activation

**User Story:** As the Training Agent, I want to detect when a project is ready for training, so that I can begin the model training workflow.

#### Acceptance Criteria

1. WHEN the MCP_Server calls the POST endpoint with a project_id, THE Training_Agent SHALL retrieve the project record from the Supabase_Database projects table.
2. THE Training_Agent SHALL verify that the project status is "pending_training" before proceeding.
3. IF the project status is not "pending_training", THEN THE Training_Agent SHALL return an error response with status code 400.
4. THE Training_Agent SHALL retrieve the associated dataset record from the datasets table using the project_id.
5. THE Training_Agent SHALL log the training initiation to the agent_logs table with log_level "info".

### Requirement 2: Dataset Retrieval from Cloud Storage

**User Story:** As the Training Agent, I want to download datasets from GCP, so that I have the data needed for model training.

#### Acceptance Criteria

1. WHEN the Training_Agent retrieves the dataset metadata, THE Training_Agent SHALL extract the gcs_url field from the dataset record.
2. THE Training_Agent SHALL parse the GCS URL to identify the bucket name and blob path.
3. THE Training_Agent SHALL authenticate with Google Cloud Storage using the service account credentials from the GOOGLE_APPLICATION_CREDENTIALS environment variable.
4. THE Training_Agent SHALL download the dataset file from the GCP_Bucket to a local temporary directory.
5. IF the download fails, THEN THE Training_Agent SHALL log the error to agent_logs and return an error response.

### Requirement 3: Dataset Preparation

**User Story:** As the Training Agent, I want to extract and organize downloaded datasets, so that PyTorch DataLoaders can access the training data.

#### Acceptance Criteria

1. WHEN the dataset download completes, THE Training_Agent SHALL unzip the dataset file to a local directory.
2. THE Training_Agent SHALL verify that the extracted dataset contains subdirectories for train, val, and test splits.
3. IF the dataset structure is invalid, THEN THE Training_Agent SHALL log an error and update the project status to "failed".
4. THE Training_Agent SHALL count the number of classes by examining the subdirectories in the train folder.
5. THE Training_Agent SHALL log the dataset structure information to the agent_logs table.

### Requirement 4: Model Architecture Initialization

**User Story:** As the Training Agent, I want to load the appropriate PyTorch model architecture, so that I can train a model suitable for the task.

#### Acceptance Criteria

1. THE Training_Agent SHALL read the preferred_model field from the Project_Metadata in the projects table.
2. THE Training_Agent SHALL load the specified model architecture from torchvision.models with pretrained weights.
3. THE Training_Agent SHALL replace the final fully connected layer with a new layer matching the number of classes detected in the dataset.
4. THE Training_Agent SHALL initialize the loss function as CrossEntropyLoss for classification tasks.
5. THE Training_Agent SHALL initialize the Adam optimizer with a learning rate specified in the Project_Metadata or default to 0.001.

### Requirement 5: Model Training Execution

**User Story:** As the Training Agent, I want to train the model on the dataset, so that I produce trained weights for evaluation.

#### Acceptance Criteria

1. THE Training_Agent SHALL create PyTorch DataLoader instances for the train and validation datasets with batch size 32.
2. THE Training_Agent SHALL apply image transformations including resize to 224x224 and conversion to tensor.
3. THE Training_Agent SHALL train the model for the number of epochs specified in the Project_Metadata.
4. WHILE training, THE Training_Agent SHALL log the loss value for each epoch to the agent_logs table.
5. THE Training_Agent SHALL save the model state dictionary to a local .pth file after training completes.

### Requirement 6: Model Upload to Cloud Storage

**User Story:** As the Training Agent, I want to upload trained models to GCP, so that the Evaluation Agent can access them.

#### Acceptance Criteria

1. WHEN model training completes successfully, THE Training_Agent SHALL upload the .pth file to the GCP_Bucket under the path "models/{project_name}_model.pth".
2. THE Training_Agent SHALL authenticate with Google Cloud Storage using the service account credentials.
3. THE Training_Agent SHALL verify the upload by checking that the blob exists in the GCP_Bucket.
4. IF the upload fails, THEN THE Training_Agent SHALL retry once before logging an error.
5. THE Training_Agent SHALL construct the full GCS URL (gs://bucket/path) for the uploaded model.

### Requirement 7: Metadata Update and Status Transition

**User Story:** As the Training Agent, I want to record model metadata in Supabase, so that the Evaluation Agent knows a model is ready.

#### Acceptance Criteria

1. WHEN the model upload succeeds, THE Training_Agent SHALL insert a new row into the Supabase_Database models table.
2. THE Training_Agent SHALL populate the models table with project_id, name, framework, gcs_url, and metadata fields.
3. THE Training_Agent SHALL update the projects table status to "pending_evaluation" for the associated project.
4. THE Training_Agent SHALL update the projects table updated_at timestamp to the current time.
5. THE Training_Agent SHALL log the successful completion to the agent_logs table with log_level "info".

### Requirement 8: Error Handling and Recovery

**User Story:** As the Training Agent, I want to handle errors gracefully, so that failures are logged and the system can recover.

#### Acceptance Criteria

1. IF any step in the training workflow fails, THEN THE Training_Agent SHALL log the error details to the agent_logs table with log_level "error".
2. THE Training_Agent SHALL update the project status to "failed" if a critical error occurs.
3. THE Training_Agent SHALL include the error message and stack trace in the Project_Metadata under an "error" field.
4. THE Training_Agent SHALL clean up temporary files including downloaded datasets and model checkpoints after completion or failure.
5. THE Training_Agent SHALL return appropriate HTTP status codes (200 for success, 400 for bad request, 500 for server error).

### Requirement 9: FastAPI Service Endpoints

**User Story:** As the MCP Server, I want to interact with the Training Agent through REST endpoints, so that I can trigger training jobs programmatically.

#### Acceptance Criteria

1. THE Training_Agent SHALL expose a POST endpoint at "/agents/training/start" that accepts a JSON payload with project_id.
2. THE Training_Agent SHALL expose a GET endpoint at "/agents/training/status/{project_id}" that returns training progress and logs.
3. THE Training_Agent SHALL expose a GET endpoint at "/health" that returns service health status.
4. THE Training_Agent SHALL validate all incoming request payloads using Pydantic models.
5. THE Training_Agent SHALL return JSON responses with appropriate status codes and error messages.

### Requirement 10: Environment Configuration

**User Story:** As a developer, I want to configure the Training Agent using environment variables, so that I can deploy it in different environments.

#### Acceptance Criteria

1. THE Training_Agent SHALL read the SUPABASE_URL environment variable to connect to the Supabase_Database.
2. THE Training_Agent SHALL read the SUPABASE_KEY environment variable for database authentication.
3. THE Training_Agent SHALL read the GCP_BUCKET_NAME environment variable to identify the storage bucket.
4. THE Training_Agent SHALL read the GOOGLE_APPLICATION_CREDENTIALS environment variable for GCP authentication.
5. THE Training_Agent SHALL read the LOG_LEVEL environment variable to configure logging verbosity with default value "INFO".
