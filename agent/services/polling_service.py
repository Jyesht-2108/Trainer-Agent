"""
Polling service for automatic training trigger.

This service continuously monitors the Supabase database for projects
with status 'pending_training' and automatically triggers the training workflow.
"""

import asyncio
import time
from typing import Set
from datetime import datetime

from agent.services.database_service import db_service
from agent.services.training_service import execute_training
from agent.services.evaluation_service import execute_evaluation


class PollingService:
    """Service that polls for projects ready for training."""
    
    def __init__(self, poll_interval: int = 10):
        """
        Initialize the polling service.
        
        Args:
            poll_interval: Seconds between each poll (default: 10)
        """
        self.poll_interval = poll_interval
        self.is_running = False
        self.processed_projects: Set[str] = set()
        
    async def start(self):
        """Start the polling loop."""
        self.is_running = True
        print(f"[{datetime.now()}] Polling service started (interval: {self.poll_interval}s)")
        
        while self.is_running:
            try:
                await self._poll_and_process()
            except Exception as e:
                print(f"[{datetime.now()}] Error in polling loop: {str(e)}")
            
            # Wait before next poll
            await asyncio.sleep(self.poll_interval)
    
    def stop(self):
        """Stop the polling loop."""
        self.is_running = False
        print(f"[{datetime.now()}] Polling service stopped")
    
    async def _poll_and_process(self):
        """Poll database and process pending projects."""
        try:
            # Query for projects with status 'pending_training'
            training_projects = db_service.get_projects_by_status("pending_training")
            
            if training_projects:
                print(f"[{datetime.now()}] Found {len(training_projects)} project(s) pending training")
                
                for project in training_projects:
                    project_id = project.get("id")
                    project_name = project.get("name", "Unknown")
                    
                    # Skip if already processed in this session
                    if project_id in self.processed_projects:
                        continue
                    
                    print(f"[{datetime.now()}] Triggering training for project: {project_name} ({project_id})")
                    
                    # Mark as processing to avoid duplicate triggers in this session
                    self.processed_projects.add(project_id)
                    
                    # Execute training asynchronously
                    try:
                        result = await execute_training(project_id)
                        
                        if result.get("success"):
                            print(f"[{datetime.now()}] ✓ Training completed successfully for {project_name}")
                            print(f"[{datetime.now()}] Model URL: {result.get('model_url')}")
                        else:
                            print(f"[{datetime.now()}] ✗ Training failed for {project_name}: {result.get('error')}")
                            self.processed_projects.discard(project_id)
                            
                    except Exception as e:
                        print(f"[{datetime.now()}] ✗ Exception during training for {project_name}: {str(e)}")
                        self.processed_projects.discard(project_id)
            
            # Query for projects with status 'pending_evaluation'
            evaluation_projects = db_service.get_projects_by_status("pending_evaluation")
            
            if evaluation_projects:
                print(f"[{datetime.now()}] Found {len(evaluation_projects)} project(s) pending evaluation")
                
                for project in evaluation_projects:
                    project_id = project.get("id")
                    project_name = project.get("name", "Unknown")
                    
                    # Skip if already processed in this session
                    if project_id in self.processed_projects:
                        continue
                    
                    print(f"[{datetime.now()}] Triggering evaluation for project: {project_name} ({project_id})")
                    
                    # Mark as processing
                    self.processed_projects.add(project_id)
                    
                    # Execute evaluation asynchronously
                    try:
                        result = await execute_evaluation(project_id)
                        
                        if result.get("success"):
                            print(f"[{datetime.now()}] ✓ Evaluation completed successfully for {project_name}")
                            print(f"[{datetime.now()}] Accuracy: {result.get('accuracy'):.2%}")
                            print(f"[{datetime.now()}] Bundle URL: {result.get('bundle_url')}")
                        else:
                            print(f"[{datetime.now()}] ✗ Evaluation failed for {project_name}: {result.get('error')}")
                            self.processed_projects.discard(project_id)
                            
                    except Exception as e:
                        print(f"[{datetime.now()}] ✗ Exception during evaluation for {project_name}: {str(e)}")
                        self.processed_projects.discard(project_id)
                    
        except Exception as e:
            print(f"[{datetime.now()}] Error polling database: {str(e)}")


# Global polling service instance
polling_service = PollingService(poll_interval=10)
