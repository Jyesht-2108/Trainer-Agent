from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""
    
    # Supabase configuration (Requirements 10.1, 10.2)
    supabase_url: str
    supabase_key: str
    
    # GCP configuration (Requirements 10.3, 10.4)
    gcp_bucket_name: str
    google_application_credentials: str
    
    # Logging configuration (Requirement 10.5)
    log_level: str = "INFO"
    
    # Training defaults
    batch_size: int = 64  # Increased for better GPU utilization on M3
    default_epochs: int = 10  # Increased for better accuracy
    default_learning_rate: float = 0.001
    
    model_config = SettingsConfigDict(
        env_file="agent/.env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )


# Global settings instance
settings = Settings()
