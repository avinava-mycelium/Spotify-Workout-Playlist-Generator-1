"""Service manager for handling multiple music service integrations."""

import os
from typing import Dict, List, Any, Optional, Type, Tuple
from pathlib import Path

from loguru import logger

from base_music_service import BaseMusicService, MusicServiceType, BaseDiscoveryEngine, BaseCurator


class MusicServiceError(Exception):
    """Custom exception for music service errors with user-friendly messages."""
    
    def __init__(self, message: str, suggestions: List[str] = None, service_type: str = None):
        self.message = message
        self.suggestions = suggestions or []
        self.service_type = service_type
        super().__init__(message)
    
    def get_formatted_error(self) -> str:
        """Get a formatted error message with suggestions."""
        error_msg = f"❌ {self.message}"
        
        if self.service_type:
            error_msg = f"❌ [{self.service_type.upper()}] {self.message}"
        
        if self.suggestions:
            error_msg += "\n\n💡 Suggestions:"
            for i, suggestion in enumerate(self.suggestions, 1):
                error_msg += f"\n  {i}. {suggestion}"
        
        return error_msg


class ServiceManager:
    """Manages multiple music service integrations with user-friendly setup."""
    
    def __init__(self, config_dir: Path = None):
        """Initialize the service manager."""
        self.config_dir = config_dir or Path.cwd()  # Use current working directory for transparency
        
        # Registry of available services
        self._service_registry: Dict[MusicServiceType, Type[BaseMusicService]] = {}
        self._discovery_registry: Dict[MusicServiceType, Type[BaseDiscoveryEngine]] = {}
        self._curator_registry: Dict[MusicServiceType, Type[BaseCurator]] = {}
        
        # Current active services
        self._active_services: Dict[MusicServiceType, BaseMusicService] = {}
    
    def register_service(
        self, 
        service_type: MusicServiceType, 
        service_class: Type[BaseMusicService],
        discovery_class: Type[BaseDiscoveryEngine] = None,
        curator_class: Type[BaseCurator] = None
    ):
        """Register a music service implementation."""
        self._service_registry[service_type] = service_class
        
        if discovery_class:
            self._discovery_registry[service_type] = discovery_class
        
        if curator_class:
            self._curator_registry[service_type] = curator_class
        
        logger.info(f"Registered service: {service_type.value}")
    
    def get_available_services(self) -> List[MusicServiceType]:
        """Get list of available (registered) services."""
        return list(self._service_registry.keys())
    
    def get_service_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all registered services."""
        status = {}
        
        for service_type in self._service_registry:
            config = self._load_service_config(service_type)
            service_class = self._service_registry[service_type]
            
            # Create temporary instance for validation
            try:
                temp_service = service_class(config)
                is_valid, errors = temp_service.validate_config()
                
                status[service_type.value] = {
                    "configured": is_valid,
                    "errors": errors,
                    "has_discovery": service_type in self._discovery_registry,
                    "has_curator": service_type in self._curator_registry,
                    "config_file": self._get_config_file_path(service_type)
                }
            except Exception as e:
                status[service_type.value] = {
                    "configured": False,
                    "errors": [str(e)],
                    "has_discovery": service_type in self._discovery_registry,
                    "has_curator": service_type in self._curator_registry,
                    "config_file": self._get_config_file_path(service_type)
                }
        
        return status
    
    async def initialize_service(self, service_type: MusicServiceType) -> BaseMusicService:
        """Initialize and authenticate a music service."""
        if service_type not in self._service_registry:
            raise MusicServiceError(
                f"Service '{service_type.value}' is not registered",
                suggestions=[
                    f"Available services: {', '.join([s.value for s in self.get_available_services()])}",
                    "Check if the service module is properly imported"
                ]
            )
        
        # Check if already initialized
        if service_type in self._active_services:
            return self._active_services[service_type]
        
        # Load configuration
        config = self._load_service_config(service_type)
        
        # Validate configuration
        service_class = self._service_registry[service_type]
        temp_service = service_class(config)
        is_valid, errors = temp_service.validate_config()
        
        if not is_valid:
            config_file = self._get_config_file_path(service_type)
            raise MusicServiceError(
                f"Invalid configuration for {service_type.value}",
                suggestions=[
                    f"Check your configuration file: {config_file}",
                    f"Run: python main.py setup {service_type.value}",
                    "Ensure all required API credentials are provided"
                ] + [f"• {error}" for error in errors],
                service_type=service_type.value
            )
        
        # Initialize and authenticate
        try:
            service = service_class(config)
            auth_success = await service.authenticate()
            
            if not auth_success:
                raise MusicServiceError(
                    f"Failed to authenticate with {service_type.value}",
                    suggestions=self._get_auth_suggestions(service_type),
                    service_type=service_type.value
                )
            
            self._active_services[service_type] = service
            logger.info(f"Successfully initialized {service_type.value}")
            return service
            
        except Exception as e:
            if isinstance(e, MusicServiceError):
                raise
            
            raise MusicServiceError(
                f"Failed to initialize {service_type.value}: {str(e)}",
                suggestions=self._get_troubleshooting_suggestions(service_type),
                service_type=service_type.value
            )
    
    def get_discovery_engine(self, service_type: MusicServiceType) -> BaseDiscoveryEngine:
        """Get discovery engine for a service."""
        if service_type not in self._discovery_registry:
            raise MusicServiceError(
                f"Discovery engine not available for {service_type.value}",
                suggestions=[
                    "This service may not support music discovery",
                    "Try using the curator instead"
                ]
            )
        
        if service_type not in self._active_services:
            raise MusicServiceError(
                f"Service {service_type.value} is not initialized",
                suggestions=[f"Run: python main.py init {service_type.value}"]
            )
        
        discovery_class = self._discovery_registry[service_type]
        return discovery_class(self._active_services[service_type])
    
    def get_curator(self, service_type: MusicServiceType) -> BaseCurator:
        """Get curator for a service."""
        if service_type not in self._curator_registry:
            raise MusicServiceError(
                f"Curator not available for {service_type.value}",
                suggestions=[
                    "This service may not support curation",
                    "Try using the discovery engine instead"
                ]
            )
        
        if service_type not in self._active_services:
            raise MusicServiceError(
                f"Service {service_type.value} is not initialized",
                suggestions=[f"Run: python main.py init {service_type.value}"]
            )
        
        curator_class = self._curator_registry[service_type]
        return curator_class(self._active_services[service_type])
    
    def _load_service_config(self, service_type: MusicServiceType) -> Dict[str, Any]:
        """Load configuration for a specific service."""
        config_file = self._get_config_file_path(service_type)
        
        if not config_file.exists():
            return {}
        
        # Load from .env style file
        config = {}
        try:
            with open(config_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        config[key.strip()] = value.strip()
        except Exception as e:
            logger.warning(f"Failed to load config for {service_type.value}: {e}")
        
        return config
    
    def _get_config_file_path(self, service_type: MusicServiceType) -> Path:
        """Get config file path for a service."""
        return self.config_dir / f"{service_type.value}.env"
    
    def _get_auth_suggestions(self, service_type: MusicServiceType) -> List[str]:
        """Get authentication troubleshooting suggestions for a service."""
        base_suggestions = [
            "Verify your API credentials are correct",
            "Check if your API keys have expired",
            "Ensure your application has the required permissions"
        ]
        
        if service_type == MusicServiceType.SPOTIFY:
            return base_suggestions + [
                "Check your Spotify redirect URI matches exactly: http://127.0.0.1:8080/callback",
                "Verify your Spotify app is not in development mode restrictions",
                "Try refreshing your Spotify token cache"
            ]
        elif service_type == MusicServiceType.YOUTUBE_MUSIC:
            return base_suggestions + [
                "Ensure you have a YouTube Music subscription",
                "Check if your OAuth consent screen is configured",
                "Verify the OAuth redirect URI is correct"
            ]
        elif service_type == MusicServiceType.AMAZON_MUSIC:
            return base_suggestions + [
                "Verify your Amazon Music subscription is active",
                "Check your Amazon Developer account credentials",
                "Ensure your app is approved for Music API access"
            ]
        
        return base_suggestions
    
    def _get_troubleshooting_suggestions(self, service_type: MusicServiceType) -> List[str]:
        """Get general troubleshooting suggestions for a service."""
        return [
            f"Check if {service_type.value} is experiencing outages",
            "Verify your internet connection",
            "Try clearing the service cache",
            f"Re-run the setup: python main.py setup {service_type.value}",
            "Check the logs for detailed error information"
        ]
    
    def create_service_config_template(self, service_type: MusicServiceType) -> str:
        """Create a configuration template for a service."""
        config_file = self._get_config_file_path(service_type)
        
        if service_type == MusicServiceType.SPOTIFY:
            template = """# Spotify Configuration
# Get these from https://developer.spotify.com/dashboard/

# Required: Your Spotify app credentials
SPOTIFY_CLIENT_ID=your_client_id_here
SPOTIFY_CLIENT_SECRET=your_client_secret_here

# Required: Redirect URI (must match your Spotify app settings)
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8080/callback

# Required: Your reference workout playlist ID
# Get this from Spotify playlist URL: spotify:playlist:PLAYLIST_ID
REFERENCE_PLAYLIST_ID=your_playlist_id_here

# Optional: Playlist settings
TARGET_PLAYLIST_NAME=Daily Workout Mix
PLAYLIST_SIZE=30
"""
        elif service_type == MusicServiceType.YOUTUBE_MUSIC:
            template = """# YouTube Music Configuration
# Get these from https://console.developers.google.com/

# Required: Your Google OAuth credentials
YOUTUBE_CLIENT_ID=your_client_id_here
YOUTUBE_CLIENT_SECRET=your_client_secret_here
YOUTUBE_REDIRECT_URI=http://localhost:8080/callback

# Required: Your reference playlist ID
REFERENCE_PLAYLIST_ID=your_playlist_id_here

# Optional: Playlist settings
TARGET_PLAYLIST_NAME=Daily Workout Mix
PLAYLIST_SIZE=30
"""
        elif service_type == MusicServiceType.AMAZON_MUSIC:
            template = """# Amazon Music Configuration
# Get these from https://developer.amazon.com/

# Required: Your Amazon Music API credentials
AMAZON_CLIENT_ID=your_client_id_here
AMAZON_CLIENT_SECRET=your_client_secret_here
AMAZON_REDIRECT_URI=http://localhost:8080/callback

# Required: Your reference playlist ID
REFERENCE_PLAYLIST_ID=your_playlist_id_here

# Optional: Playlist settings
TARGET_PLAYLIST_NAME=Daily Workout Mix
PLAYLIST_SIZE=30
"""
        else:
            template = f"# {service_type.value.title()} Configuration\n# Add your configuration here\n"
        
        # Write template to file
        with open(config_file, 'w') as f:
            f.write(template)
        
        return str(config_file)
    
    async def health_check_all(self) -> Dict[str, Tuple[bool, str]]:
        """Perform health check on all active services."""
        results = {}
        
        for service_type, service in self._active_services.items():
            try:
                is_healthy, message = await service.health_check()
                results[service_type.value] = (is_healthy, message)
            except Exception as e:
                results[service_type.value] = (False, f"Health check failed: {str(e)}")
        
        return results 