"""Spotify service implementation using the modular interface."""

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

from loguru import logger

from base_music_service import BaseMusicService, MusicServiceType, TrackInfo, PlaylistInfo, ArtistInfo


class SpotifyService(BaseMusicService):
    """Spotify implementation of the music service interface."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Spotify service."""
        super().__init__(config)
        self.client: Optional[spotipy.Spotify] = None
    
    @property
    def service_type(self) -> MusicServiceType:
        """Get the service type."""
        return MusicServiceType.SPOTIFY
    
    @property
    def service_name(self) -> str:
        """Get the human-readable service name."""
        return "Spotify"
    
    def validate_config(self) -> Tuple[bool, List[str]]:
        """Validate Spotify configuration."""
        errors = []
        
        required_keys = [
            'SPOTIFY_CLIENT_ID',
            'SPOTIFY_CLIENT_SECRET',
            'SPOTIFY_REDIRECT_URI',
            'REFERENCE_PLAYLIST_ID'
        ]
        
        for key in required_keys:
            if not self.config.get(key):
                errors.append(f"Missing required configuration: {key}")
            elif self.config.get(key) in ['your_client_id_here', 'your_client_secret_here', 'your_playlist_id_here']:
                errors.append(f"Please set a real value for {key}")
        
        # Validate redirect URI format
        redirect_uri = self.config.get('SPOTIFY_REDIRECT_URI', '')
        if redirect_uri and not (redirect_uri.startswith('http://') or redirect_uri.startswith('https://')):
            errors.append("SPOTIFY_REDIRECT_URI must be a valid HTTP/HTTPS URL")
        
        return len(errors) == 0, errors
    
    async def authenticate(self) -> bool:
        """Authenticate with Spotify."""
        try:
            # Setup cache directory
            cache_dir = Path.home() / ".multi_music_generator" / "spotify"
            cache_dir.mkdir(parents=True, exist_ok=True)
            
            # Set up OAuth with required scopes
            scope = "playlist-modify-public playlist-modify-private playlist-read-private user-library-read"
            
            auth_manager = SpotifyOAuth(
                client_id=self.config['SPOTIFY_CLIENT_ID'],
                client_secret=self.config['SPOTIFY_CLIENT_SECRET'],
                redirect_uri=self.config['SPOTIFY_REDIRECT_URI'],
                scope=scope,
                cache_path=str(cache_dir / ".spotify_cache")
            )
            
            self.client = spotipy.Spotify(auth_manager=auth_manager)
            
            # Test authentication by getting current user
            user = self.client.current_user()
            if user:
                self.authenticated = True
                logger.info(f"Successfully authenticated with Spotify as: {user['display_name']} ({user['id']})")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Failed to authenticate with Spotify: {e}")
            return False
    
    async def get_current_user(self) -> Dict[str, Any]:
        """Get current authenticated user information."""
        if not self.authenticated or not self.client:
            raise Exception("Not authenticated with Spotify")
        
        user = self.client.current_user()
        return {
            'id': user['id'],
            'name': user.get('display_name', 'Unknown'),
            'followers': user.get('followers', {}).get('total', 0),
            'country': user.get('country', 'Unknown'),
            'external_url': user.get('external_urls', {}).get('spotify', '')
        }
    
    async def get_playlist_tracks(self, playlist_id: str) -> List[TrackInfo]:
        """Get all tracks from a Spotify playlist."""
        if not self.authenticated or not self.client:
            raise Exception("Not authenticated with Spotify")
        
        tracks = []
        results = self.client.playlist_tracks(playlist_id)
        
        while results:
            for item in results['items']:
                if item['track'] and item['track']['id']:
                    track = item['track']
                    
                    # Get artist names
                    artists = [artist['name'] for artist in track['artists']]
                    
                    track_info = TrackInfo(
                        id=track['id'],
                        name=track['name'],
                        artist=', '.join(artists),
                        album=track['album']['name'],
                        uri=track['uri'],
                        external_url=track['external_urls']['spotify'],
                        duration_ms=track['duration_ms'],
                        explicit=track['explicit'],
                        popularity=track['popularity']
                    )
                    tracks.append(track_info)
            
            # Check if there are more pages
            if results['next']:
                results = self.client.next(results)
            else:
                results = None
        
        logger.info(f"Retrieved {len(tracks)} tracks from playlist {playlist_id}")
        return tracks
    
    async def create_playlist(self, name: str, description: str = "", public: bool = True) -> PlaylistInfo:
        """Create a new Spotify playlist."""
        if not self.authenticated or not self.client:
            raise Exception("Not authenticated with Spotify")
        
        user = self.client.current_user()
        playlist = self.client.user_playlist_create(
            user=user['id'],
            name=name,
            public=public,
            description=description
        )
        
        playlist_info = PlaylistInfo(
            id=playlist['id'],
            name=playlist['name'],
            description=playlist['description'],
            track_count=playlist['tracks']['total'],
            external_url=playlist['external_urls']['spotify'],
            public=playlist['public']
        )
        
        logger.info(f"Created playlist: {name} ({playlist['id']})")
        return playlist_info
    
    async def update_playlist_tracks(self, playlist_id: str, track_uris: List[str]) -> bool:
        """Update Spotify playlist with new tracks."""
        if not self.authenticated or not self.client:
            raise Exception("Not authenticated with Spotify")
        
        try:
            # Clear existing tracks
            self.client.playlist_replace_items(playlist_id, [])
            
            # Add new tracks in batches (Spotify API limit is 100 per request)
            batch_size = 100
            for i in range(0, len(track_uris), batch_size):
                batch = track_uris[i:i + batch_size]
                self.client.playlist_add_items(playlist_id, batch)
            
            logger.info(f"Updated playlist {playlist_id} with {len(track_uris)} tracks")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update playlist {playlist_id}: {e}")
            return False
    
    async def find_playlist_by_name(self, name: str) -> Optional[PlaylistInfo]:
        """Find a Spotify playlist by name."""
        if not self.authenticated or not self.client:
            raise Exception("Not authenticated with Spotify")
        
        user = self.client.current_user()
        playlists = self.client.user_playlists(user['id'])
        
        while playlists:
            for playlist in playlists['items']:
                if playlist['name'] == name:
                    return PlaylistInfo(
                        id=playlist['id'],
                        name=playlist['name'],
                        description=playlist['description'] or "",
                        track_count=playlist['tracks']['total'],
                        external_url=playlist['external_urls']['spotify'],
                        public=playlist['public']
                    )
            
            if playlists['next']:
                playlists = self.client.next(playlists)
            else:
                playlists = None
        
        return None
    
    async def search_tracks(self, query: str, limit: int = 20) -> List[TrackInfo]:
        """Search for tracks on Spotify."""
        if not self.authenticated or not self.client:
            raise Exception("Not authenticated with Spotify")
        
        results = self.client.search(q=query, type='track', limit=limit, market='US')
        tracks = []
        
        for track in results['tracks']['items']:
            artists = [artist['name'] for artist in track['artists']]
            
            track_info = TrackInfo(
                id=track['id'],
                name=track['name'],
                artist=', '.join(artists),
                album=track['album']['name'],
                uri=track['uri'],
                external_url=track['external_urls']['spotify'],
                duration_ms=track['duration_ms'],
                explicit=track['explicit'],
                popularity=track['popularity']
            )
            tracks.append(track_info)
        
        return tracks
    
    async def get_artist_info(self, artist_id: str) -> ArtistInfo:
        """Get detailed Spotify artist information."""
        if not self.authenticated or not self.client:
            raise Exception("Not authenticated with Spotify")
        
        artist = self.client.artist(artist_id)
        
        return ArtistInfo(
            id=artist['id'],
            name=artist['name'],
            genres=artist['genres'],
            popularity=artist['popularity'],
            external_url=artist['external_urls']['spotify']
        )
    
    async def get_related_artists(self, artist_id: str) -> List[ArtistInfo]:
        """Get artists related to the given Spotify artist."""
        if not self.authenticated or not self.client:
            raise Exception("Not authenticated with Spotify")
        
        results = self.client.artist_related_artists(artist_id)
        artists = []
        
        for artist in results['artists']:
            artist_info = ArtistInfo(
                id=artist['id'],
                name=artist['name'],
                genres=artist['genres'],
                popularity=artist['popularity'],
                external_url=artist['external_urls']['spotify']
            )
            artists.append(artist_info)
        
        return artists
    
    async def get_artist_top_tracks(self, artist_id: str, limit: int = 10) -> List[TrackInfo]:
        """Get top tracks for a Spotify artist."""
        if not self.authenticated or not self.client:
            raise Exception("Not authenticated with Spotify")
        
        results = self.client.artist_top_tracks(artist_id, country='US')
        tracks = []
        
        for track in results['tracks'][:limit]:
            artists = [artist['name'] for artist in track['artists']]
            
            track_info = TrackInfo(
                id=track['id'],
                name=track['name'],
                artist=', '.join(artists),
                album=track['album']['name'],
                uri=track['uri'],
                external_url=track['external_urls']['spotify'],
                duration_ms=track['duration_ms'],
                explicit=track['explicit'],
                popularity=track['popularity']
            )
            tracks.append(track_info)
        
        return tracks
    
    async def get_user_saved_tracks(self, limit: int = 50) -> List[TrackInfo]:
        """Get user's saved/liked tracks from Spotify."""
        if not self.authenticated or not self.client:
            raise Exception("Not authenticated with Spotify")
        
        tracks = []
        results = self.client.current_user_saved_tracks(limit=min(limit, 50))
        
        for item in results['items']:
            track = item['track']
            artists = [artist['name'] for artist in track['artists']]
            
            track_info = TrackInfo(
                id=track['id'],
                name=track['name'],
                artist=', '.join(artists),
                album=track['album']['name'],
                uri=track['uri'],
                external_url=track['external_urls']['spotify'],
                duration_ms=track['duration_ms'],
                explicit=track['explicit'],
                popularity=track['popularity']
            )
            tracks.append(track_info)
        
        return tracks 
    async def get_recommendations(self, seed_artists: List[str] = None, seed_genres: List[str] = None, 
                                 seed_tracks: List[str] = None, limit: int = 20, **audio_features) -> List[TrackInfo]:
        """Get track recommendations using Spotify's powerful recommendations API.
        
        This taps into Spotify's millions of tracks using machine learning.
        
        Args:
            seed_artists: List of artist IDs to base recommendations on
            seed_genres: List of genre names (e.g., ['metal', 'rock'])  
            seed_tracks: List of track IDs to base recommendations on
            limit: Number of recommendations to return (max 100)
            **audio_features: Audio feature targets (e.g., target_energy=0.8, min_tempo=120)
        """
        try:
            # Build parameters
            params = {'limit': min(limit, 100)}  # Spotify max is 100
            
            # Add seed parameters (must have at least 1, max 5 total)
            if seed_artists:
                params['seed_artists'] = ','.join(seed_artists[:5])
            if seed_genres:
                params['seed_genres'] = ','.join(seed_genres[:5])  
            if seed_tracks:
                params['seed_tracks'] = ','.join(seed_tracks[:5])
            
            # Add audio feature parameters
            for key, value in audio_features.items():
                params[key] = value
            
            # Make API call
            result = self.client.recommendations(**params)
            
            # Convert to TrackInfo objects
            tracks = []
            for track in result['tracks']:
                track_info = TrackInfo(
                    id=track['id'],
                    name=track['name'],
                    artist=', '.join([artist['name'] for artist in track['artists']]),
                    album=track['album']['name'],
                    uri=track['uri'],
                    external_url=track['external_urls'].get('spotify', ''),
                    duration_ms=track['duration_ms'],
                    explicit=track['explicit'],
                    popularity=track['popularity']
                )
                tracks.append(track_info)
            
            logger.info(f"Got {len(tracks)} recommendations from Spotify API")
            return tracks
            
        except Exception as e:
            logger.error(f"Failed to get recommendations: {e}")
            return []
