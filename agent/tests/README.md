# Training Agent Integration Tests

This directory contains comprehensive integration tests for the Training Agent microservice.

## Test Structure

- `conftest.py` - Pytest fixtures and shared test utilities
- `test_api_endpoints.py` - Tests for FastAPI REST endpoints
- `test_training_workflow.py` - Tests for complete end-to-end training workflow
- `test_error_handling.py` - Tests for error scenarios and edge cases
- `test_storage_operations.py` - Tests for GCP storage operations

## Running Tests

### Install Test Dependencies

```bash
cd agent
pip install -r requirements.txt
```

### Run All Tests

```bash
pytest
```

### Run Specific Test File

```bash
pytest tests/test_api_endpoints.py
```

### Run Specific Test Class

```bash
pytest tests/test_api_endpoints.py::TestStartTrainingEndpoint
```

### Run Specific Test

```bash
pytest tests/test_api_endpoints.py::TestStartTrainingEndpoint::test_start_training_success
```

### Run with Verbose Output

```bash
pytest -v
```

### Run with Coverage Report

```bash
pytest --cov=agent --cov-report=html
```

## Test Coverage

The integration tests cover:

### API Endpoints (test_api_endpoints.py)
- ✓ POST /agents/training/start - Success and error cases
- ✓ GET /agents/training/status/{project_id} - Status retrieval
- ✓ GET /health - Health check endpoint
- ✓ Request validation and error formatting
- ✓ HTTP status codes (200, 400, 404, 422, 500)

### Training Workflow (test_training_workflow.py)
- ✓ Complete end-to-end training with mock dataset
- ✓ Dataset download and extraction
- ✓ Model initialization and training
- ✓ Model upload to GCP
- ✓ Database metadata updates
- ✓ Status transitions (pending_training → pending_evaluation)
- ✓ Temporary file cleanup

### Error Handling (test_error_handling.py)
- ✓ Missing project scenarios
- ✓ Missing dataset scenarios
- ✓ Invalid dataset structure
- ✓ Invalid GCS URLs
- ✓ Database connection failures
- ✓ Storage download/upload failures
- ✓ Model initialization errors
- ✓ Database update failures

### Storage Operations (test_storage_operations.py)
- ✓ GCS URL parsing (valid and invalid formats)
- ✓ Dataset download with retry logic
- ✓ Model upload with retry logic
- ✓ Upload verification
- ✓ Error handling for network failures
- ✓ Max retries exceeded scenarios

## Test Fixtures

The tests use mocked services to avoid external dependencies:

- **mock_supabase_client** - Mocked Supabase database client
- **mock_gcs_client** - Mocked Google Cloud Storage client
- **mock_dataset_zip** - Generated mock dataset with proper structure
- **mock_project_data** - Sample project metadata
- **mock_dataset_data** - Sample dataset metadata
- **temp_dir** - Temporary directory for test files (auto-cleanup)

## Requirements Coverage

All requirements from the requirements.md document are tested:

- Requirement 1: Training Agent Activation ✓
- Requirement 2: Dataset Retrieval from Cloud Storage ✓
- Requirement 3: Dataset Preparation ✓
- Requirement 4: Model Architecture Initialization ✓
- Requirement 5: Model Training Execution ✓
- Requirement 6: Model Upload to Cloud Storage ✓
- Requirement 7: Metadata Update and Status Transition ✓
- Requirement 8: Error Handling and Recovery ✓
- Requirement 9: FastAPI Service Endpoints ✓
- Requirement 10: Environment Configuration ✓

## Notes

- Tests use mocked external services (Supabase, GCP) to run without credentials
- Mock datasets are generated with PIL to create realistic image files
- Training is configured with minimal epochs (2) for fast test execution
- Async tests are handled automatically with pytest-asyncio
- All tests clean up temporary files after execution
