"""Spotify client wrapper with authentication handling."""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from loguru import logger

from config import Settings


class SpotifyClient:
    """Wrapper for Spotify API client with authentication."""
    
    def __init__(self, settings: Settings):
        """Initialize Spotify client."""
        self.settings = settings
        self.client: Optional[spotipy.Spotify] = None
        self._setup_client()
    
    def _setup_client(self) -> None:
        """Set up Spotify client with OAuth authentication."""
        try:
            # Ensure data directory exists
            self.settings.data_dir.mkdir(parents=True, exist_ok=True)
            
            # Set up OAuth with required scopes
            scope = "playlist-modify-public playlist-modify-private playlist-read-private user-library-read"
            
            auth_manager = SpotifyOAuth(
                client_id=self.settings.spotify_client_id,
                client_secret=self.settings.spotify_client_secret,
                redirect_uri=self.settings.spotify_redirect_uri,
                scope=scope,
                cache_path=str(self.settings.data_dir / ".spotify_cache")
            )
            
            self.client = spotipy.Spotify(auth_manager=auth_manager)
            
            # Test authentication
            user = self.client.current_user()
            logger.info(f"Successfully authenticated as: {user['display_name']} ({user['id']})")
            
        except Exception as e:
            logger.error(f"Failed to authenticate with Spotify: {e}")
            raise
    
    def get_playlist_tracks(self, playlist_id: str) -> List[Dict[str, Any]]:
        """Get all tracks from a playlist."""
        try:
            tracks = []
            results = self.client.playlist_tracks(playlist_id)
            
            while results:
                for item in results['items']:
                    if item['track'] and item['track']['id']:  # Skip local files
                        tracks.append({
                            'id': item['track']['id'],
                            'name': item['track']['name'],
                            'artists': [artist['name'] for artist in item['track']['artists']],
                            'uri': item['track']['uri']
                        })
                
                results = self.client.next(results) if results['next'] else None
            
            logger.info(f"Retrieved {len(tracks)} tracks from playlist {playlist_id}")
            return tracks
            
        except Exception as e:
            logger.error(f"Failed to get playlist tracks: {e}")
            raise
    
    def get_audio_features(self, track_ids: List[str]) -> List[Dict[str, Any]]:
        """Get audio features for multiple tracks."""
        try:
            features = []
            # Spotify API allows max 100 tracks per request
            for i in range(0, len(track_ids), 100):
                batch = track_ids[i:i+100]
                batch_features = self.client.audio_features(batch)
                features.extend([f for f in batch_features if f is not None])
            
            logger.info(f"Retrieved audio features for {len(features)} tracks")
            return features
            
        except Exception as e:
            logger.error(f"Failed to get audio features: {e}")
            raise
    
    def get_recommendations(self, seed_tracks: List[str], target_features: Dict[str, float], limit: int = 50) -> List[Dict[str, Any]]:
        """Get track recommendations based on seed tracks and target audio features."""
        try:
            # Use up to 5 seed tracks (Spotify API limit)
            seed_tracks = seed_tracks[:5]
            
            recommendations = self.client.recommendations(
                seed_tracks=seed_tracks,
                limit=limit,
                target_energy=target_features.get('energy'),
                target_danceability=target_features.get('danceability'),
                target_valence=target_features.get('valence'),
                target_tempo=target_features.get('tempo'),
                min_energy=max(0, target_features.get('energy', 0.8) - 0.2),
                max_energy=min(1, target_features.get('energy', 0.8) + 0.2),
                min_danceability=max(0, target_features.get('danceability', 0.7) - 0.2),
                max_danceability=min(1, target_features.get('danceability', 0.7) + 0.2)
            )
            
            tracks = []
            for track in recommendations['tracks']:
                tracks.append({
                    'id': track['id'],
                    'name': track['name'],
                    'artists': [artist['name'] for artist in track['artists']],
                    'uri': track['uri']
                })
            
            logger.info(f"Retrieved {len(tracks)} recommendations")
            return tracks
            
        except Exception as e:
            logger.error(f"Failed to get recommendations: {e}")
            raise
    
    def create_playlist(self, name: str, description: str = "") -> str:
        """Create a new playlist and return its ID."""
        try:
            user_id = self.client.current_user()['id']
            playlist = self.client.user_playlist_create(
                user=user_id,
                name=name,
                description=description,
                public=False
            )
            
            logger.info(f"Created playlist '{name}' with ID: {playlist['id']}")
            return playlist['id']
            
        except Exception as e:
            logger.error(f"Failed to create playlist: {e}")
            raise
    
    def update_playlist(self, playlist_id: str, track_uris: List[str]) -> None:
        """Replace all tracks in a playlist with new tracks."""
        try:
            # Clear existing tracks
            self.client.playlist_replace_items(playlist_id, [])
            
            # Add new tracks in batches (Spotify API limit is 100 per request)
            for i in range(0, len(track_uris), 100):
                batch = track_uris[i:i+100]
                self.client.playlist_add_items(playlist_id, batch)
            
            logger.info(f"Updated playlist {playlist_id} with {len(track_uris)} tracks")
            
        except Exception as e:
            logger.error(f"Failed to update playlist: {e}")
            raise
    
    def find_playlist_by_name(self, name: str) -> Optional[str]:
        """Find a playlist by name and return its ID."""
        try:
            playlists = self.client.current_user_playlists()
            
            while playlists:
                for playlist in playlists['items']:
                    if playlist['name'] == name:
                        logger.info(f"Found playlist '{name}' with ID: {playlist['id']}")
                        return playlist['id']
                
                playlists = self.client.next(playlists) if playlists['next'] else None
            
            logger.info(f"Playlist '{name}' not found")
            return None
            
        except Exception as e:
            logger.error(f"Failed to search for playlist: {e}")
            raise 