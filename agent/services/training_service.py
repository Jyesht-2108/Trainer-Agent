"""
Training orchestration service.

This module coordinates the complete training workflow from dataset download
to model upload, integrating all service layers and handling errors gracefully.

Requirements: 1.1, 1.2, 1.3, 1.5, 3.3, 8.1, 8.2, 8.3, 8.4
"""

import os
import time
import traceback
from typing import Dict, Any

from agent.services.database_service import db_service
from agent.services.storage_service import storage_service
from agent.utils.file_utils import (
    unzip_dataset,
    auto_flatten_dataset,
    normalize_folder_names,
    validate_dataset_structure,
    create_val_from_train,
    auto_split_dataset,
    count_classes,
    cleanup_temp_files
)
from agent.training.model_factory import create_model
from agent.training.trainer import ModelTrainer
from agent.config import settings


async def execute_training(project_id: str) -> Dict[str, Any]:
    """
    Execute the complete training workflow for a project.
    
    This function orchestrates all steps of the training process:
    1. Validate project status is "pending_training"
    2. Fetch project and dataset metadata
    3. Download dataset from GCP
    4. Extract and validate dataset structure
    5. Count classes and initialize model
    6. Execute training
    7. Upload trained model to GCP
    8. Update database with model metadata and status
    9. Clean up temporary files
    
    Args:
        project_id: UUID of the project to train
        
    Returns:
        Dictionary containing success status and model_url or error message
        
    Raises:
        Exception: Various exceptions for different failure scenarios
        
    Requirements: 1.1, 1.2, 1.3, 1.5, 3.3, 8.1, 8.2, 8.3, 8.4
    """
    # Track temporary files for cleanup
    temp_files = []
    
    try:
        # Step 1: Validate project status (Requirement 1.1, 1.2)
        db_service.log_agent_activity(
            project_id,
            "Training workflow initiated",
            "info"
        )
        
        project = db_service.get_project(project_id)
        if not project:
            error_msg = f"Project {project_id} not found"
            db_service.log_agent_activity(project_id, error_msg, "error")
            return {"success": False, "error": error_msg}
        
        if project.get("status") != "pending_training":
            error_msg = f"Project status is '{project.get('status')}', expected 'pending_training'"
            db_service.log_agent_activity(project_id, error_msg, "error")
            return {"success": False, "error": error_msg}
        
        # Update status to 'training' to indicate work has started
        db_service.update_project_status(project_id, "training")
        db_service.log_agent_activity(
            project_id,
            f"Project validated: {project.get('name')} - Status updated to 'training'",
            "info"
        )
        
        # Step 2: Fetch project and dataset metadata (Requirement 1.4)
        dataset = db_service.get_dataset(project_id)
        if not dataset:
            error_msg = f"Dataset not found for project {project_id}"
            db_service.log_agent_activity(project_id, error_msg, "error")
            db_service.update_project_status(project_id, "failed")
            return {"success": False, "error": error_msg}
        
        db_service.log_agent_activity(
            project_id,
            f"Dataset retrieved: {dataset.get('name')}",
            "info"
        )
        
        # Extract metadata
        project_name = project.get("name", "model")
        project_metadata = project.get("metadata", {})
        preferred_model = project_metadata.get("preferred_model", "resnet18")
        epochs = project_metadata.get("epochs", settings.default_epochs)
        learning_rate = project_metadata.get("learning_rate", settings.default_learning_rate)
        
        # Step 3: Download dataset from GCP (Requirement 2.1, 2.4)
        gcs_url = dataset.get("gcs_url")
        if not gcs_url:
            error_msg = "Dataset gcs_url is missing"
            db_service.log_agent_activity(project_id, error_msg, "error")
            db_service.update_project_status(project_id, "failed")
            return {"success": False, "error": error_msg}
        
        db_service.log_agent_activity(
            project_id,
            f"Downloading dataset from {gcs_url}",
            "info"
        )
        
        # Create temp directory for dataset
        temp_dir = f"/tmp/training_{project_id}"
        os.makedirs(temp_dir, exist_ok=True)
        temp_files.append(temp_dir)
        
        dataset_zip_path = os.path.join(temp_dir, "dataset.zip")
        temp_files.append(dataset_zip_path)
        
        try:
            storage_service.download_dataset(gcs_url, dataset_zip_path)
            db_service.log_agent_activity(
                project_id,
                "Dataset downloaded successfully",
                "info"
            )
        except Exception as e:
            error_msg = f"Failed to download dataset: {str(e)}"
            db_service.log_agent_activity(project_id, error_msg, "error")
            db_service.update_project_status(project_id, "failed")
            return {"success": False, "error": error_msg}
        
        # Step 4: Extract dataset and validate structure (Requirement 3.1, 3.2, 3.3)
        db_service.log_agent_activity(
            project_id,
            "Extracting dataset",
            "info"
        )
        
        dataset_extract_dir = os.path.join(temp_dir, "dataset")
        temp_files.append(dataset_extract_dir)
        
        try:
            unzip_dataset(dataset_zip_path, dataset_extract_dir)
        except Exception as e:
            error_msg = f"Failed to extract dataset: {str(e)}"
            db_service.log_agent_activity(project_id, error_msg, "error")
            db_service.update_project_status(project_id, "failed")
            return {"success": False, "error": error_msg}
        
        # Flatten nested dataset structure if needed
        try:
            auto_flatten_dataset(dataset_extract_dir)
        except Exception as e:
            db_service.log_agent_activity(
                project_id,
                f"Warning: Failed to flatten dataset: {str(e)}",
                "warning"
            )
        
        # Normalize folder names (Train -> train, Test -> test)
        try:
            normalize_folder_names(dataset_extract_dir)
        except Exception as e:
            db_service.log_agent_activity(
                project_id,
                f"Warning: Failed to normalize folder names: {str(e)}",
                "warning"
            )
        
        # Check if we have train and test but no val
        has_train = os.path.exists(os.path.join(dataset_extract_dir, 'train'))
        has_test = os.path.exists(os.path.join(dataset_extract_dir, 'test'))
        has_val = os.path.exists(os.path.join(dataset_extract_dir, 'val'))
        
        if has_train and has_test and not has_val:
            # Create val from train
            db_service.log_agent_activity(
                project_id,
                "Found train/test but no val - creating validation set from training data",
                "info"
            )
            try:
                create_val_from_train(dataset_extract_dir, val_ratio=0.2)
            except Exception as e:
                error_msg = f"Failed to create validation set: {str(e)}"
                db_service.log_agent_activity(project_id, error_msg, "error")
                db_service.update_project_status(project_id, "failed")
                return {"success": False, "error": error_msg}
        
        # Validate dataset structure - if not valid, auto-split
        if not validate_dataset_structure(dataset_extract_dir):
            db_service.log_agent_activity(
                project_id,
                "No train/val/test structure found - auto-splitting dataset",
                "info"
            )
            
            try:
                auto_split_dataset(dataset_extract_dir, train_ratio=0.7, val_ratio=0.2)
                db_service.log_agent_activity(
                    project_id,
                    "Dataset auto-split completed successfully",
                    "info"
                )
            except Exception as e:
                error_msg = f"Failed to auto-split dataset: {str(e)}"
                db_service.log_agent_activity(project_id, error_msg, "error")
                db_service.update_project_status(project_id, "failed")
                return {"success": False, "error": error_msg}
        else:
            db_service.log_agent_activity(
                project_id,
                "Dataset structure validated (train/val/test folders found)",
                "info"
            )
        
        # Step 5: Count classes and initialize model (Requirement 3.4, 4.1, 4.2, 4.3)
        train_dir = os.path.join(dataset_extract_dir, "train")
        
        try:
            num_classes = count_classes(train_dir)
            db_service.log_agent_activity(
                project_id,
                f"Detected {num_classes} classes in dataset",
                "info"
            )
        except Exception as e:
            error_msg = f"Failed to count classes: {str(e)}"
            db_service.log_agent_activity(project_id, error_msg, "error")
            db_service.update_project_status(project_id, "failed")
            return {"success": False, "error": error_msg}
        
        # Initialize model
        try:
            model = create_model(preferred_model, num_classes)
            db_service.log_agent_activity(
                project_id,
                f"Model initialized: {preferred_model} with {num_classes} classes",
                "info"
            )
        except Exception as e:
            error_msg = f"Failed to initialize model: {str(e)}"
            db_service.log_agent_activity(project_id, error_msg, "error")
            db_service.update_project_status(project_id, "failed")
            return {"success": False, "error": error_msg}
        
        # Step 6: Create ModelTrainer and execute training (Requirement 4.4, 4.5, 5.1-5.5)
        db_service.log_agent_activity(
            project_id,
            f"Starting training: {epochs} epochs, lr={learning_rate}",
            "info"
        )
        
        training_start_time = time.time()
        
        try:
            trainer = ModelTrainer(
                model=model,
                data_dir=dataset_extract_dir,
                num_classes=num_classes,
                epochs=epochs,
                lr=learning_rate,
                batch_size=settings.batch_size
            )
            
            # Prepare data loaders
            trainer.prepare_data_loaders()
            
            # Execute training
            trained_model = trainer.train()
            
            training_time = time.time() - training_start_time
            
            db_service.log_agent_activity(
                project_id,
                f"Training completed in {training_time:.2f} seconds",
                "info"
            )
            
            # Save model locally
            model_save_path = os.path.join(temp_dir, f"{project_name}_model.pth")
            temp_files.append(model_save_path)
            trainer.save_model(model_save_path)
            
        except Exception as e:
            error_msg = f"Training failed: {str(e)}"
            db_service.log_agent_activity(project_id, error_msg, "error")
            db_service.update_project_status(project_id, "failed")
            return {"success": False, "error": error_msg}
        
        # Step 7: Upload trained model to GCP (Requirement 6.1, 6.2, 6.3, 6.4, 6.5)
        db_service.log_agent_activity(
            project_id,
            "Uploading trained model to GCP",
            "info"
        )
        
        try:
            model_gcs_url = storage_service.upload_model(model_save_path, project_name)
            db_service.log_agent_activity(
                project_id,
                f"Model uploaded successfully: {model_gcs_url}",
                "info"
            )
        except Exception as e:
            error_msg = f"Failed to upload model: {str(e)}"
            db_service.log_agent_activity(project_id, error_msg, "error")
            db_service.update_project_status(project_id, "failed")
            return {"success": False, "error": error_msg}
        
        # Step 8: Insert model record and update project status (Requirement 7.1-7.5)
        try:
            from agent.models.schemas import ModelData
            
            model_data = ModelData(
                project_id=project_id,
                name=f"{project_name}_model",
                framework="pytorch",
                gcs_url=model_gcs_url,
                metadata={
                    "epochs": epochs,
                    "learning_rate": learning_rate,
                    "num_classes": num_classes,
                    "architecture": preferred_model,
                    "training_time_seconds": int(training_time)
                }
            )
            
            db_service.insert_model(model_data)
            db_service.log_agent_activity(
                project_id,
                "Model record inserted into database",
                "info"
            )
            
            # Update project status to pending_evaluation
            db_service.update_project_status(project_id, "pending_evaluation")
            db_service.log_agent_activity(
                project_id,
                "Project status updated to pending_evaluation",
                "info"
            )
            
        except Exception as e:
            error_msg = f"Failed to update database: {str(e)}"
            db_service.log_agent_activity(project_id, error_msg, "error")
            return {"success": False, "error": error_msg}
        
        # Success
        db_service.log_agent_activity(
            project_id,
            "Training workflow completed successfully",
            "info"
        )
        
        return {
            "success": True,
            "model_url": model_gcs_url
        }
        
    except Exception as e:
        # Catch-all for unexpected errors (Requirement 8.1, 8.2, 8.3)
        error_msg = f"Unexpected error in training workflow: {str(e)}"
        stack_trace = traceback.format_exc()
        
        db_service.log_agent_activity(
            project_id,
            f"{error_msg}\n{stack_trace}",
            "error"
        )
        
        try:
            db_service.update_project_status(project_id, "failed")
        except:
            pass  # Best effort to update status
        
        return {
            "success": False,
            "error": error_msg
        }
        
    finally:
        # Step 9: Clean up temporary files (Requirement 8.4)
        db_service.log_agent_activity(
            project_id,
            "Cleaning up temporary files",
            "info"
        )
        cleanup_temp_files(temp_files)
