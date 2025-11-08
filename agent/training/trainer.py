"""
PyTorch model trainer for image classification.

This module provides the ModelTrainer class that handles data loading,
training loop execution, and model checkpoint saving.
"""

import os
import time
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from typing import Tuple


class ModelTrainer:
    """
    Handles PyTorch model training with data loading and optimization.
    
    This class manages the complete training workflow including data preparation,
    training loop execution, and model saving.
    """
    
    def __init__(
        self,
        model: nn.Module,
        data_dir: str,
        num_classes: int,
        epochs: int = 10,
        lr: float = 0.001,
        batch_size: int = 32,
        use_amp: bool = False  # Automatic Mixed Precision
    ):
        """
        Initialize the ModelTrainer.
        
        Args:
            model: PyTorch model to train
            data_dir: Path to dataset directory containing train/val folders
            num_classes: Number of output classes
            epochs: Number of training epochs
            lr: Learning rate for optimizer
            batch_size: Batch size for data loaders
            use_amp: Whether to use automatic mixed precision (faster on supported hardware)
        """
        self.model = model
        self.data_dir = data_dir
        self.num_classes = num_classes
        self.epochs = epochs
        self.lr = lr
        self.batch_size = batch_size
        self.use_amp = use_amp
        
        # Initialize loss function and optimizer
        self.criterion = nn.CrossEntropyLoss()
        # Use AdamW (better than Adam) with weight decay for regularization
        self.optimizer = torch.optim.AdamW(
            self.model.parameters(), 
            lr=self.lr,
            weight_decay=0.01  # L2 regularization
        )
        
        # Learning rate scheduler for better convergence
        self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer,
            mode='min',
            factor=0.5,
            patience=2
        )
        
        # Determine device: MPS (Apple Silicon) > CUDA > CPU
        if torch.backends.mps.is_available():
            self.device = torch.device("mps")
            print("✅ Using Apple Silicon GPU (MPS)")
        elif torch.cuda.is_available():
            self.device = torch.device("cuda")
            print("✅ Using NVIDIA GPU (CUDA)")
        else:
            self.device = torch.device("cpu")
            print("⚠️  Using CPU (training will be slower)")
        
        self.model.to(self.device)
        
        # Compile model for faster execution (PyTorch 2.0+)
        # Note: torch.compile has issues with MPS, so only use it for CUDA
        try:
            if hasattr(torch, 'compile') and self.device.type == 'cuda':
                print("⚡ Compiling model with torch.compile for faster execution...")
                self.model = torch.compile(self.model, mode='reduce-overhead')
            elif self.device.type == 'mps':
                print("ℹ️  torch.compile not used (MPS compatibility issues)")
        except Exception as e:
            print(f"⚠️  Model compilation not available: {e}")
        
        # Setup gradient scaler for mixed precision training
        self.scaler = torch.cuda.amp.GradScaler() if self.use_amp and self.device.type == 'cuda' else None
        
        # Data loaders will be initialized when prepare_data_loaders is called
        self.train_loader = None
        self.val_loader = None

    def prepare_data_loaders(self) -> Tuple[DataLoader, DataLoader]:
        """
        Create train and validation DataLoaders with ImageFolder.
        
        Applies image transformations including resize to 224x224, conversion to tensor,
        and normalization with ImageNet statistics.
        
        Returns:
            Tuple of (train_loader, val_loader)
        """
        # Training transforms with data augmentation for better generalization
        train_transform = transforms.Compose([
            transforms.Resize(256),
            transforms.RandomCrop(224),  # Random crop for augmentation
            transforms.RandomHorizontalFlip(p=0.5),  # Random flip
            transforms.RandomRotation(15),  # Random rotation up to 15 degrees
            transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),  # Color augmentation
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],  # ImageNet mean
                std=[0.229, 0.224, 0.225]     # ImageNet std
            )
        ])
        
        # Validation transforms without augmentation
        val_transform = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])
        
        # Create datasets using ImageFolder with different transforms
        train_dir = os.path.join(self.data_dir, "train")
        val_dir = os.path.join(self.data_dir, "val")
        
        train_dataset = datasets.ImageFolder(train_dir, transform=train_transform)
        val_dataset = datasets.ImageFolder(val_dir, transform=val_transform)
        
        # Create data loaders with optimized settings
        # Use more workers for faster data loading (prevents GPU starvation)
        num_workers = 6  # Increased for M3 (8-core CPU can handle it)
        pin_memory = self.device.type == 'cuda'  # Only CUDA supports pin_memory
        
        self.train_loader = DataLoader(
            train_dataset,
            batch_size=self.batch_size,
            shuffle=True,
            num_workers=num_workers,
            pin_memory=pin_memory,
            persistent_workers=True if num_workers > 0 else False,
            prefetch_factor=2  # Prefetch 2 batches per worker
        )
        
        self.val_loader = DataLoader(
            val_dataset,
            batch_size=self.batch_size * 2,  # Larger batch for validation (no gradients)
            shuffle=False,
            num_workers=num_workers,
            pin_memory=pin_memory,
            persistent_workers=True if num_workers > 0 else False,
            prefetch_factor=2
        )
        
        return self.train_loader, self.val_loader

    def _train_epoch(self, epoch: int) -> float:
        """
        Train for one epoch and return average loss.
        
        Args:
            epoch: Current epoch number (for logging)
            
        Returns:
            Average training loss for the epoch
        """
        self.model.train()
        running_loss = 0.0
        num_batches = 0
        
        for batch_idx, (inputs, labels) in enumerate(self.train_loader):
            # Move data to device
            inputs = inputs.to(self.device, non_blocking=True)
            labels = labels.to(self.device, non_blocking=True)
            
            # Zero the parameter gradients (set_to_none is faster than zero_grad)
            self.optimizer.zero_grad(set_to_none=True)
            
            # Mixed precision training
            if self.use_amp and self.scaler is not None:
                with torch.cuda.amp.autocast():
                    outputs = self.model(inputs)
                    loss = self.criterion(outputs, labels)
                
                # Backward pass with gradient scaling
                self.scaler.scale(loss).backward()
                self.scaler.step(self.optimizer)
                self.scaler.update()
            else:
                # Standard training
                outputs = self.model(inputs)
                loss = self.criterion(outputs, labels)
                loss.backward()
                self.optimizer.step()
            
            # Accumulate loss
            running_loss += loss.item()
            num_batches += 1
            
            # Print progress every 20 batches (reduced logging overhead)
            if batch_idx > 0 and batch_idx % 20 == 0:
                print(f"  Batch {batch_idx}/{len(self.train_loader)} - Loss: {loss.item():.4f}")
        
        # Synchronize device operations for accurate timing
        if self.device.type == 'mps':
            torch.mps.synchronize()
        elif self.device.type == 'cuda':
            torch.cuda.synchronize()
        
        # Calculate average loss for the epoch
        avg_loss = running_loss / num_batches if num_batches > 0 else 0.0
        
        return avg_loss

    def _validate_epoch(self) -> Tuple[float, float]:
        """
        Run validation and return loss and accuracy.
        
        Returns:
            Tuple of (validation_loss, validation_accuracy)
        """
        self.model.eval()
        running_loss = 0.0
        correct = 0
        total = 0
        
        with torch.no_grad():
            for inputs, labels in self.val_loader:
                inputs = inputs.to(self.device, non_blocking=True)
                labels = labels.to(self.device, non_blocking=True)
                
                outputs = self.model(inputs)
                loss = self.criterion(outputs, labels)
                
                running_loss += loss.item()
                _, predicted = torch.max(outputs, 1)
                total += labels.size(0)
                correct += (predicted == labels).sum().item()
        
        val_loss = running_loss / len(self.val_loader)
        val_accuracy = 100 * correct / total
        
        return val_loss, val_accuracy
    
    def train(self) -> nn.Module:
        """
        Execute the complete training loop for all epochs.
        
        Trains the model for the specified number of epochs, logging progress
        and loss values after each epoch.
        
        Returns:
            Trained PyTorch model
        """
        # Prepare data loaders if not already done
        if self.train_loader is None or self.val_loader is None:
            self.prepare_data_loaders()
        
        print(f"🚀 Starting training for {self.epochs} epochs on {self.device}")
        print(f"📊 Dataset: {len(self.train_loader.dataset)} training images, {len(self.val_loader.dataset)} validation images")
        print(f"📦 Batch size: {self.batch_size}, Batches per epoch: {len(self.train_loader)}")
        
        start_time = time.time()
        best_val_acc = 0.0
        
        # Training loop
        for epoch in range(1, self.epochs + 1):
            epoch_start_time = time.time()
            
            print(f"\n📈 Epoch {epoch}/{self.epochs}")
            
            # Train for one epoch
            train_loss = self._train_epoch(epoch)
            
            # Validate
            val_loss, val_acc = self._validate_epoch()
            
            # Update learning rate based on validation loss
            self.scheduler.step(val_loss)
            
            # Synchronize for accurate timing
            if self.device.type == 'mps':
                torch.mps.synchronize()
            elif self.device.type == 'cuda':
                torch.cuda.synchronize()
            
            epoch_time = time.time() - epoch_start_time
            
            # Log progress
            print(f"✓ Epoch {epoch}/{self.epochs} - Train Loss: {train_loss:.4f} - Val Loss: {val_loss:.4f} - Val Acc: {val_acc:.2f}% - Time: {epoch_time:.2f}s")
            
            # Track best model
            if val_acc > best_val_acc:
                best_val_acc = val_acc
                print(f"  🌟 New best validation accuracy: {best_val_acc:.2f}%")
        
        total_time = time.time() - start_time
        print(f"\n🎉 Training completed in {total_time:.2f}s ({total_time/60:.1f} minutes)")
        print(f"🏆 Best validation accuracy: {best_val_acc:.2f}%")
        
        return self.model

    def save_model(self, path: str) -> None:
        """
        Save model state dictionary to a .pth file.
        
        Args:
            path: File path where the model should be saved (should end with .pth)
        """
        # Ensure the directory exists
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        # Save the model state dictionary
        torch.save(self.model.state_dict(), path)
        print(f"Model saved to {path}")
