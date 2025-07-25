"""Configuration management for Spotify Workout Playlist Generator."""

import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    # Spotify API credentials
    spotify_client_id: str = Field(..., env="SPOTIFY_CLIENT_ID")
    spotify_client_secret: str = Field(..., env="SPOTIFY_CLIENT_SECRET")
    spotify_redirect_uri: str = Field(default="http://localhost:8080/callback", env="SPOTIFY_REDIRECT_URI")
    
    # Playlist configuration
    reference_playlist_id: str = Field(..., env="REFERENCE_PLAYLIST_ID")
    target_playlist_name: str = Field(default="Daily Workout Mix", env="TARGET_PLAYLIST_NAME")
    playlist_size: int = Field(default=30, env="PLAYLIST_SIZE")
    
    # Scheduling
    update_time: str = Field(default="07:00", env="UPDATE_TIME")  # 24-hour format
    
    # Storage
    data_dir: Path = Field(default=Path.home() / ".spotify_workout_generator")
    
    # Audio feature preferences (for fine-tuning recommendations)
    target_energy: float = Field(default=0.8, ge=0.0, le=1.0)
    target_danceability: float = Field(default=0.7, ge=0.0, le=1.0)
    target_valence: float = Field(default=0.6, ge=0.0, le=1.0)  # Positivity
    target_tempo: float = Field(default=120.0, ge=50.0, le=200.0)  # BPM
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def get_settings() -> Settings:
    """Get application settings."""
    return Settings() 