"""
Evaluation service for trained models.

This module handles model evaluation, metric computation, and bundle creation
for end users.
"""

import os
import json
import shutil
import zipfile
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, classification_report
from typing import Dict, Any, List

from agent.services.database_service import db_service
from agent.services.storage_service import storage_service
from agent.training.model_factory import create_model
from agent.config import settings


async def execute_evaluation(project_id: str) -> Dict[str, Any]:
    """
    Execute the complete evaluation workflow for a trained model.
    
    Steps:
    1. Fetch project, model, and dataset metadata
    2. Download model and dataset from GCP
    3. Load model and run inference on test set
    4. Compute metrics (accuracy, precision, recall, F1)
    5. Create user bundle (model + predict.py + labels.json + README)
    6. Upload bundle to GCP
    7. Update database with metrics and bundle URL
    8. Update project status to 'completed'
    
    Args:
        project_id: UUID of the project to evaluate
        
    Returns:
        Dictionary containing success status, metrics, and bundle_url
    """
    temp_files = []
    
    try:
        # Step 1: Fetch metadata
        db_service.log_agent_activity(
            project_id,
            "Evaluation workflow initiated",
            "info"
        )
        
        project = db_service.get_project(project_id)
        if not project:
            error_msg = f"Project {project_id} not found"
            db_service.log_agent_activity(project_id, error_msg, "error")
            return {"success": False, "error": error_msg}
        
        if project.get("status") != "pending_evaluation":
            error_msg = f"Project status is '{project.get('status')}', expected 'pending_evaluation'"
            db_service.log_agent_activity(project_id, error_msg, "error")
            return {"success": False, "error": error_msg}
        
        # Update status to 'evaluating'
        db_service.update_project_status(project_id, "evaluating")
        
        # Get model metadata
        model_record = db_service.get_model_by_project(project_id)
        if not model_record:
            error_msg = f"Model not found for project {project_id}"
            db_service.log_agent_activity(project_id, error_msg, "error")
            db_service.update_project_status(project_id, "failed")
            return {"success": False, "error": error_msg}
        
        # Get dataset metadata
        dataset = db_service.get_dataset(project_id)
        if not dataset:
            error_msg = f"Dataset not found for project {project_id}"
            db_service.log_agent_activity(project_id, error_msg, "error")
            db_service.update_project_status(project_id, "failed")
            return {"success": False, "error": error_msg}
        
        db_service.log_agent_activity(
            project_id,
            f"Metadata retrieved - Model: {model_record.get('name')}, Dataset: {dataset.get('name')}",
            "info"
        )
        
        # Extract project info
        project_name = project.get("name", "model")
        project_metadata = project.get("metadata", {})
        model_architecture = project_metadata.get("preferred_model", "resnet18")
        
        # Step 2: Download model and dataset
        temp_dir = f"/tmp/evaluation_{project_id}"
        os.makedirs(temp_dir, exist_ok=True)
        temp_files.append(temp_dir)
        
        model_path = os.path.join(temp_dir, "model.pth")
        dataset_zip_path = os.path.join(temp_dir, "dataset.zip")
        dataset_extract_dir = os.path.join(temp_dir, "dataset")
        
        temp_files.extend([model_path, dataset_zip_path, dataset_extract_dir])
        
        db_service.log_agent_activity(
            project_id,
            f"Downloading model from {model_record.get('gcs_url')}",
            "info"
        )
        
        storage_service.download_model(model_record.get("gcs_url"), model_path)
        
        db_service.log_agent_activity(
            project_id,
            f"Downloading dataset from {dataset.get('gcs_url')}",
            "info"
        )
        
        storage_service.download_dataset(dataset.get("gcs_url"), dataset_zip_path)
        
        # Extract dataset
        from agent.utils.file_utils import unzip_dataset, auto_flatten_dataset, normalize_folder_names
        unzip_dataset(dataset_zip_path, dataset_extract_dir)
        auto_flatten_dataset(dataset_extract_dir)
        normalize_folder_names(dataset_extract_dir)
        
        test_dir = os.path.join(dataset_extract_dir, "test")
        if not os.path.exists(test_dir):
            error_msg = "Test directory not found in dataset"
            db_service.log_agent_activity(project_id, error_msg, "error")
            db_service.update_project_status(project_id, "failed")
            return {"success": False, "error": error_msg}
        
        # Step 3: Load model and run evaluation
        db_service.log_agent_activity(
            project_id,
            "Loading model and preparing test data",
            "info"
        )
        
        metrics = evaluate_model(
            model_path=model_path,
            test_dir=test_dir,
            model_architecture=model_architecture,
            project_id=project_id
        )
        
        db_service.log_agent_activity(
            project_id,
            f"Evaluation complete - Accuracy: {metrics['accuracy']:.2%}",
            "info"
        )
        
        # Step 4: Create user bundle
        db_service.log_agent_activity(
            project_id,
            "Creating downloadable user bundle",
            "info"
        )
        
        bundle_url = create_user_bundle(
            project_id=project_id,
            project_name=project_name,
            model_path=model_path,
            model_architecture=model_architecture,
            class_labels=metrics["class_labels"],
            num_classes=metrics["num_classes"]
        )
        
        db_service.log_agent_activity(
            project_id,
            f"Bundle uploaded to {bundle_url}",
            "info"
        )
        
        # Step 5: Update database
        db_service.update_model_metrics(
            model_id=model_record.get("id"),
            accuracy=metrics["accuracy"],
            metadata=metrics["detailed_metrics"]
        )
        
        # Update project with bundle URL
        project_metadata["bundle_url"] = bundle_url
        project_metadata["evaluation_metrics"] = metrics["detailed_metrics"]
        
        db_service.update_project_metadata(project_id, project_metadata)
        db_service.update_project_status(project_id, "completed")
        
        db_service.log_agent_activity(
            project_id,
            "Evaluation workflow completed successfully",
            "info"
        )
        
        return {
            "success": True,
            "accuracy": metrics["accuracy"],
            "bundle_url": bundle_url,
            "metrics": metrics["detailed_metrics"]
        }
        
    except Exception as e:
        error_msg = f"Evaluation failed: {str(e)}"
        db_service.log_agent_activity(project_id, error_msg, "error")
        
        try:
            db_service.update_project_status(project_id, "failed")
        except:
            pass
        
        return {"success": False, "error": error_msg}
    
    finally:
        # Cleanup
        from agent.utils.file_utils import cleanup_temp_files
        cleanup_temp_files(temp_files)


def evaluate_model(
    model_path: str,
    test_dir: str,
    model_architecture: str,
    project_id: str
) -> Dict[str, Any]:
    """
    Load model and evaluate on test set.
    
    Args:
        model_path: Path to model .pth file
        test_dir: Path to test directory with class folders
        model_architecture: Model architecture name
        project_id: Project ID for logging
        
    Returns:
        Dictionary with accuracy, class labels, and detailed metrics
    """
    # Setup device
    if torch.backends.mps.is_available():
        device = torch.device("mps")
    elif torch.cuda.is_available():
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")
    
    db_service.log_agent_activity(project_id, f"Using device: {device}", "info")
    
    # Load test dataset
    transform = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225]
        )
    ])
    
    test_dataset = datasets.ImageFolder(test_dir, transform=transform)
    test_loader = DataLoader(
        test_dataset,
        batch_size=64,
        shuffle=False,
        num_workers=4
    )
    
    num_classes = len(test_dataset.classes)
    class_labels = test_dataset.classes
    
    db_service.log_agent_activity(
        project_id,
        f"Test dataset loaded: {len(test_dataset)} images, {num_classes} classes",
        "info"
    )
    
    # Load model
    model = create_model(model_architecture, num_classes)
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.to(device)
    model.eval()
    
    # Run inference
    y_true = []
    y_pred = []
    
    with torch.no_grad():
        for inputs, labels in test_loader:
            inputs = inputs.to(device)
            labels = labels.to(device)
            
            outputs = model(inputs)
            _, preds = torch.max(outputs, 1)
            
            y_true.extend(labels.cpu().numpy())
            y_pred.extend(preds.cpu().numpy())
    
    # Compute metrics
    accuracy = accuracy_score(y_true, y_pred)
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, average='weighted', zero_division=0
    )
    
    # Detailed classification report
    report = classification_report(
        y_true, y_pred,
        target_names=class_labels,
        output_dict=True,
        zero_division=0
    )
    
    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "num_classes": num_classes,
        "class_labels": class_labels,
        "detailed_metrics": report
    }


def create_user_bundle(
    project_id: str,
    project_name: str,
    model_path: str,
    model_architecture: str,
    class_labels: List[str],
    num_classes: int
) -> str:
    """
    Create a downloadable bundle with model, predict script, and labels.
    
    Args:
        project_id: Project UUID
        project_name: Name of the project
        model_path: Path to trained model
        model_architecture: Model architecture name
        class_labels: List of class names
        num_classes: Number of classes
        
    Returns:
        GCS URL of the uploaded bundle
    """
    export_dir = f"/tmp/export_{project_id}"
    os.makedirs(export_dir, exist_ok=True)
    
    # 1. Copy model
    shutil.copy(model_path, os.path.join(export_dir, "model.pth"))
    
    # 2. Create labels.json
    labels_dict = {str(i): label for i, label in enumerate(class_labels)}
    with open(os.path.join(export_dir, "labels.json"), "w") as f:
        json.dump(labels_dict, f, indent=2)
    
    # 3. Create predict.py
    predict_code = f'''"""
Inference script for trained model.

Usage:
    python predict.py path/to/image.jpg
"""

import torch
import json
import sys
from torchvision import models, transforms
from PIL import Image

# Load labels
with open('labels.json') as f:
    labels = json.load(f)

# Load model
def load_model():
    from torchvision.models import {model_architecture}
    model = {model_architecture}()
    
    # Modify final layer for number of classes
    if hasattr(model, 'fc'):
        model.fc = torch.nn.Linear(model.fc.in_features, {num_classes})
    elif hasattr(model, 'classifier'):
        if isinstance(model.classifier, torch.nn.Sequential):
            model.classifier[-1] = torch.nn.Linear(model.classifier[-1].in_features, {num_classes})
        else:
            model.classifier = torch.nn.Linear(model.classifier.in_features, {num_classes})
    
    model.load_state_dict(torch.load('model.pth', map_location='cpu'))
    model.eval()
    return model

model = load_model()

# Image preprocessing
transform = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

def predict(image_path):
    """Predict class for a single image."""
    img = Image.open(image_path).convert('RGB')
    img_tensor = transform(img).unsqueeze(0)
    
    with torch.no_grad():
        outputs = model(img_tensor)
        probabilities = torch.nn.functional.softmax(outputs, dim=1)
        confidence, predicted = torch.max(probabilities, 1)
    
    predicted_class = labels[str(predicted.item())]
    confidence_score = confidence.item()
    
    print(f"Prediction: {{predicted_class}}")
    print(f"Confidence: {{confidence_score:.2%}}")
    
    return predicted_class, confidence_score

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python predict.py <image_path>")
        sys.exit(1)
    
    image_path = sys.argv[1]
    predict(image_path)
'''
    
    with open(os.path.join(export_dir, "predict.py"), "w") as f:
        f.write(predict_code)
    
    # 4. Create README
    readme = f"""# {project_name} - Trained Model Bundle

## Contents
- `model.pth`: Trained PyTorch model weights
- `labels.json`: Class labels mapping
- `predict.py`: Inference script
- `README.txt`: This file

## Requirements
```bash
pip install torch torchvision pillow
```

## Usage
```bash
python predict.py path/to/your/image.jpg
```

## Model Details
- Architecture: {model_architecture}
- Number of classes: {num_classes}
- Classes: {', '.join(class_labels)}

## Example
```bash
python predict.py test_image.jpg
# Output:
# Prediction: melanoma
# Confidence: 94.32%
```

## Notes
- The model expects RGB images
- Images are automatically resized to 224x224
- Predictions include confidence scores
"""
    
    with open(os.path.join(export_dir, "README.txt"), "w") as f:
        f.write(readme)
    
    # 5. Create zip file
    zip_filename = f"{project_name.replace(' ', '_')}_bundle.zip"
    zip_path = f"/tmp/{zip_filename}"
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(export_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, export_dir)
                zf.write(file_path, arcname)
    
    # 6. Upload to GCP
    bundle_gcs_url = storage_service.upload_bundle(zip_path, zip_filename)
    
    # Cleanup
    shutil.rmtree(export_dir, ignore_errors=True)
    os.remove(zip_path)
    
    return bundle_gcs_url
