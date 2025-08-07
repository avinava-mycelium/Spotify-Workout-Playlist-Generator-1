"""Abstract base classes for music service integrations."""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class MusicServiceType(Enum):
    """Supported music service types."""
    SPOTIFY = "spotify"
    YOUTUBE_MUSIC = "youtube_music"
    AMAZON_MUSIC = "amazon_music"


@dataclass
class TrackInfo:
    """Standardized track information across all services."""
    id: str
    name: str
    artist: str
    album: str
    uri: str  # Service-specific URI
    external_url: str
    duration_ms: int
    explicit: bool = False
    popularity: Optional[int] = None
    genres: List[str] = None
    
    def __post_init__(self):
        if self.genres is None:
            self.genres = []


@dataclass
class PlaylistInfo:
    """Standardized playlist information across all services."""
    id: str
    name: str
    description: str
    track_count: int
    external_url: str
    public: bool = True


@dataclass
class ArtistInfo:
    """Standardized artist information across all services."""
    id: str
    name: str
    genres: List[str]
    popularity: Optional[int] = None
    external_url: str = ""
    
    def __post_init__(self):
        if self.genres is None:
            self.genres = []


class BaseMusicService(ABC):
    """Abstract base class for music service integrations."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the music service with configuration."""
        self.config = config
        self.authenticated = False
    
    @abstractmethod
    async def authenticate(self) -> bool:
        """Authenticate with the music service.
        
        Returns:
            bool: True if authentication successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_current_user(self) -> Dict[str, Any]:
        """Get current authenticated user information."""
        pass
    
    @abstractmethod
    async def get_playlist_tracks(self, playlist_id: str) -> List[TrackInfo]:
        """Get all tracks from a playlist.
        
        Args:
            playlist_id: The playlist identifier
            
        Returns:
            List of TrackInfo objects
        """
        pass
    
    @abstractmethod
    async def create_playlist(self, name: str, description: str = "", public: bool = True) -> PlaylistInfo:
        """Create a new playlist.
        
        Args:
            name: Playlist name
            description: Playlist description
            public: Whether the playlist should be public
            
        Returns:
            PlaylistInfo object with created playlist details
        """
        pass
    
    @abstractmethod
    async def update_playlist_tracks(self, playlist_id: str, track_uris: List[str]) -> bool:
        """Update playlist with new tracks (replaces existing tracks).
        
        Args:
            playlist_id: The playlist identifier
            track_uris: List of track URIs to set as playlist content
            
        Returns:
            bool: True if successful
        """
        pass
    
    @abstractmethod
    async def find_playlist_by_name(self, name: str) -> Optional[PlaylistInfo]:
        """Find a playlist by name in user's library.
        
        Args:
            name: Playlist name to search for
            
        Returns:
            PlaylistInfo if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def search_tracks(self, query: str, limit: int = 20) -> List[TrackInfo]:
        """Search for tracks using a query string.
        
        Args:
            query: Search query (genre, artist, etc.)
            limit: Maximum number of results
            
        Returns:
            List of TrackInfo objects
        """
        pass
    
    @abstractmethod
    async def get_artist_info(self, artist_id: str) -> ArtistInfo:
        """Get detailed artist information.
        
        Args:
            artist_id: The artist identifier
            
        Returns:
            ArtistInfo object
        """
        pass
    
    @abstractmethod
    async def get_related_artists(self, artist_id: str) -> List[ArtistInfo]:
        """Get artists related to the given artist.
        
        Args:
            artist_id: The artist identifier
            
        Returns:
            List of related ArtistInfo objects
        """
        pass
    
    @abstractmethod
    async def get_artist_top_tracks(self, artist_id: str, limit: int = 10) -> List[TrackInfo]:
        """Get top tracks for an artist.
        
        Args:
            artist_id: The artist identifier
            limit: Maximum number of tracks
            
        Returns:
            List of TrackInfo objects
        """
        pass
    
    @abstractmethod
    async def get_user_saved_tracks(self, limit: int = 50) -> List[TrackInfo]:
        """Get user's saved/liked tracks.
        
        Args:
            limit: Maximum number of tracks to fetch
            
        Returns:
            List of TrackInfo objects
        """
        pass
    
    @property
    @abstractmethod
    def service_type(self) -> MusicServiceType:
        """Get the service type."""
        pass
    
    @property
    @abstractmethod
    def service_name(self) -> str:
        """Get the human-readable service name."""
        pass
    
    def validate_config(self) -> Tuple[bool, List[str]]:
        """Validate the service configuration.
        
        Returns:
            Tuple of (is_valid, list_of_error_messages)
        """
        errors = []
        
        # Common validation - subclasses should override this
        if not self.config:
            errors.append("Configuration is empty")
            
        return len(errors) == 0, errors
    
    async def health_check(self) -> Tuple[bool, str]:
        """Perform a health check on the service.
        
        Returns:
            Tuple of (is_healthy, status_message)
        """
        try:
            if not self.authenticated:
                auth_success = await self.authenticate()
                if not auth_success:
                    return False, "Authentication failed"
            
            user = await self.get_current_user()
            if user:
                return True, f"Connected as {user.get('name', 'Unknown User')}"
            else:
                return False, "Failed to get user information"
                
        except Exception as e:
            return False, f"Health check failed: {str(e)}"


class BaseDiscoveryEngine(ABC):
    """Abstract base class for music discovery engines."""
    
    def __init__(self, music_service: BaseMusicService):
        """Initialize with a music service."""
        self.music_service = music_service
    
    @abstractmethod
    async def discover_new_playlist(self, reference_playlist_id: str, target_size: int = 30) -> Dict[str, Any]:
        """Discover new tracks based on a reference playlist.
        
        Args:
            reference_playlist_id: ID of the reference playlist
            target_size: Number of tracks to discover
            
        Returns:
            Dict containing discovered tracks and metadata
        """
        pass
    
    @abstractmethod
    async def analyze_taste_profile(self, reference_playlist_id: str) -> Dict[str, Any]:
        """Analyze user's taste profile from reference playlist.
        
        Args:
            reference_playlist_id: ID of the reference playlist
            
        Returns:
            Dict containing taste profile (genres, artists, etc.)
        """
        pass


class BaseCurator(ABC):
    """Abstract base class for playlist curators."""
    
    def __init__(self, music_service: BaseMusicService):
        """Initialize with a music service."""
        self.music_service = music_service
    
    @abstractmethod
    async def generate_curated_playlist(self, reference_playlist_id: str, target_size: int = 30) -> Dict[str, Any]:
        """Generate a curated playlist from existing tracks.
        
        Args:
            reference_playlist_id: ID of the reference playlist
            target_size: Number of tracks for the new playlist
            
        Returns:
            Dict containing curated playlist info and stats
        """
        pass
    
    @abstractmethod
    async def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics for the curator.
        
        Returns:
            Dict containing usage statistics
        """
        pass 