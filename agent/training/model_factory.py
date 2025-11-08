"""
Model factory for loading and configuring PyTorch models.

This module provides functions to create pretrained models from torchvision
with custom classification heads matching the number of classes in the dataset.
"""

import torch
import torch.nn as nn
from torchvision import models
from typing import List


def get_supported_models() -> List[str]:
    """
    Return list of available model architectures.
    
    Returns:
        List of supported model architecture names
    """
    return [
        "resnet18",
        "resnet34",
        "resnet50",
        "mobilenet_v2",
        "efficientnet_b0"
    ]


def create_model(model_name: str, num_classes: int) -> nn.Module:
    """
    Load a pretrained model from torchvision and modify the final layer.
    
    This function loads a pretrained model with ImageNet weights and replaces
    the final fully connected layer with a custom layer matching num_classes.
    
    Args:
        model_name: Name of the model architecture (e.g., "resnet18", "mobilenet_v2")
        num_classes: Number of output classes for the classification task
        
    Returns:
        PyTorch model with modified final layer
        
    Raises:
        ValueError: If model_name is not supported
    """
    model_name_lower = model_name.lower()
    
    # Handle common model name variations
    model_aliases = {
        "efficientnet": "efficientnet_b0",
        "mobilenet": "mobilenet_v2",
        "resnet": "resnet18"
    }
    
    if model_name_lower in model_aliases:
        model_name_lower = model_aliases[model_name_lower]
        print(f"📝 Model name '{model_name}' mapped to '{model_name_lower}'")
    
    if model_name_lower not in get_supported_models():
        raise ValueError(
            f"Unsupported model: {model_name}. "
            f"Supported models: {', '.join(get_supported_models())}"
        )
    
    # Load pretrained model based on architecture
    if model_name_lower == "resnet18":
        model = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1)
        num_features = model.fc.in_features
        model.fc = nn.Linear(num_features, num_classes)
        
    elif model_name_lower == "resnet34":
        model = models.resnet34(weights=models.ResNet34_Weights.IMAGENET1K_V1)
        num_features = model.fc.in_features
        model.fc = nn.Linear(num_features, num_classes)
        
    elif model_name_lower == "resnet50":
        model = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V1)
        num_features = model.fc.in_features
        model.fc = nn.Linear(num_features, num_classes)
        
    elif model_name_lower == "mobilenet_v2":
        model = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.IMAGENET1K_V1)
        num_features = model.classifier[1].in_features
        model.classifier[1] = nn.Linear(num_features, num_classes)
        
    elif model_name_lower == "efficientnet_b0":
        model = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.IMAGENET1K_V1)
        num_features = model.classifier[1].in_features
        model.classifier[1] = nn.Linear(num_features, num_classes)
    
    return model
