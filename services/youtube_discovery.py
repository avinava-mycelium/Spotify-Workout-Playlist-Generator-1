"""YouTube Music discovery engine implementation."""

import random
from typing import Dict, List, Any, Set
from collections import Counter

from loguru import logger

from base_music_service import BaseDiscoveryEngine, TrackInfo
from services.youtube_service import YouTubeMusicService


class YouTubeDiscoveryEngine(BaseDiscoveryEngine):
    """YouTube Music-specific implementation of music discovery."""
    
    def __init__(self, music_service: YouTubeMusicService):
        """Initialize with YouTube Music service."""
        super().__init__(music_service)
        self.youtube = music_service
        
        # YouTube Music workout-related search terms
        self.workout_genres = [
            "workout", "gym", "fitness", "cardio", "running", "training",
            "exercise", "motivation", "pump up", "energy", "beast mode"
        ]
    
    async def discover_new_playlist(self, reference_playlist_id: str, target_size: int = 30) -> Dict[str, Any]:
        """Discover new tracks for YouTube Music playlist based on user's taste."""
        try:
            logger.info("Starting YouTube Music discovery process")
            
            # Analyze user's taste from reference playlist
            taste_profile = await self.analyze_taste_profile(reference_playlist_id)
            logger.info(f"Analyzed taste profile: {len(taste_profile['artists'])} artists, {len(taste_profile['genres'])} genres")
            
            # Get user's existing tracks to avoid duplicates
            existing_tracks = await self._get_user_tracks()
            existing_video_ids = {track.id for track in existing_tracks}
            logger.info(f"Found {len(existing_video_ids)} existing tracks to avoid")
            
            # Discover new tracks using multiple strategies
            discovered_tracks = []
            
            # Strategy 1: Search by workout terms (40%)
            workout_target = max(1, int(target_size * 0.4))
            workout_tracks = await self._search_workout_content(workout_target, existing_video_ids, taste_profile)
            discovered_tracks.extend(workout_tracks)
            
            # Strategy 2: Search by user's favorite terms (40%)
            if taste_profile['artists']:
                artist_target = max(1, int(target_size * 0.4))
                artist_tracks = await self._search_by_artists(taste_profile['artists'][:10], artist_target, existing_video_ids)
                discovered_tracks.extend(artist_tracks)
            
            # Strategy 3: Diverse music search (20%)
            diverse_target = max(1, target_size - len(discovered_tracks))
            if diverse_target > 0:
                diverse_tracks = await self._search_diverse_music(diverse_target, existing_video_ids)
                discovered_tracks.extend(diverse_tracks)
            
            # Remove duplicates and limit to target size
            unique_tracks = self._deduplicate_tracks(discovered_tracks)
            final_tracks = unique_tracks[:target_size]
            
            logger.info(f"Discovered {len(final_tracks)} new tracks")
            
            # Create playlist
            playlist_info = await self._create_discovery_playlist(final_tracks)
            
            return {
                'playlist': playlist_info,
                'tracks': final_tracks,
                'taste_profile': taste_profile,
                'strategies_used': ['workout_search', 'artist_search', 'diverse_search']
            }
            
        except Exception as e:
            logger.error(f"Discovery failed: {e}")
            raise Exception(f"Failed to discover YouTube Music tracks: {str(e)}")
    
    async def analyze_taste_profile(self, reference_playlist_id: str) -> Dict[str, Any]:
        """Analyze user's music taste from reference playlist."""
        try:
            # Get reference playlist tracks
            reference_tracks = await self.youtube.get_playlist_tracks(reference_playlist_id)
            logger.info(f"Analyzing {len(reference_tracks)} reference tracks")
            
            if not reference_tracks:
                logger.warning("No reference tracks found")
                return {'artists': [], 'genres': [], 'track_count': 0}
            
            # Extract artists
            artists = []
            for track in reference_tracks:
                if track.artist and track.artist != 'Unknown Artist':
                    # Split comma-separated artists
                    track_artists = [a.strip() for a in track.artist.split(',') if a.strip()]
                    artists.extend(track_artists)
            
            # Count artist frequency
            artist_counts = Counter(artists)
            top_artists = [artist for artist, count in artist_counts.most_common(20)]
            
            # YouTube Music doesn't provide detailed genre info, so we'll derive it from search
            genres = await self._derive_genres_from_artists(top_artists[:5])
            
            taste_profile = {
                'artists': top_artists,
                'genres': genres,
                'track_count': len(reference_tracks),
                'top_artist_counts': dict(artist_counts.most_common(10))
            }
            
            logger.info(f"Taste profile: {len(top_artists)} artists, {len(genres)} derived genres")
            return taste_profile
            
        except Exception as e:
            logger.error(f"Failed to analyze taste profile: {e}")
            return {'artists': [], 'genres': [], 'track_count': 0}
    
    async def _derive_genres_from_artists(self, artists: List[str]) -> List[str]:
        """Derive genre-like terms from top artists by searching related content."""
        genres = set()
        
        for artist in artists[:3]:  # Limit to avoid too many API calls
            try:
                # Search for the artist to get related content
                search_results = await self.youtube.search_tracks(f"{artist} music", limit=5)
                
                # Extract genre-like keywords from titles and artists
                for track in search_results:
                    title_words = track.name.lower().split()
                    for word in title_words:
                        # Look for genre-like words
                        if word in ['rock', 'pop', 'metal', 'rap', 'hip', 'hop', 'electronic', 
                                  'dance', 'acoustic', 'folk', 'country', 'jazz', 'blues',
                                  'reggae', 'punk', 'alternative', 'indie', 'classical']:
                            genres.add(word)
                
            except Exception as e:
                logger.warning(f"Could not derive genres for artist {artist}: {e}")
                continue
        
        return list(genres)
    
    async def _search_workout_content(self, target_count: int, existing_ids: Set[str], taste_profile: Dict[str, Any] = None) -> List[TrackInfo]:
        """Search for workout-related music content based on user's taste."""
        tracks = []
        
        # Use genres from taste profile if available, otherwise use defaults
        if taste_profile and taste_profile.get('genres'):
            search_terms = []
            for genre in taste_profile['genres'][:3]:
                # Add workout modifiers to user's genres
                search_terms.extend([
                    f"{genre} workout high energy",
                    f"{genre} aggressive intense"
                ])
        else:
            search_terms = [f"{term} music" for term in self.workout_genres[:5]]
        
        for term in search_terms[:5]:  # Limit searches
            try:
                search_limit = max(1, target_count // max(1, len(search_terms[:5])))
                search_results = await self.youtube.search_tracks(term, limit=search_limit)
                
                for track in search_results:
                    if track.id not in existing_ids and track not in tracks:
                        tracks.append(track)
                        if len(tracks) >= target_count:
                            break
                
                if len(tracks) >= target_count:
                    break
                    
            except Exception as e:
                logger.warning(f"Workout search failed for '{term}': {e}")
                continue
        
        logger.info(f"Found {len(tracks)} workout tracks")
        return tracks
    
    async def _search_by_artists(self, artists: List[str], target_count: int, existing_ids: Set[str]) -> List[TrackInfo]:
        """Search for tracks by user's favorite artists and similar artists."""
        tracks = []
        
        for artist in artists[:8]:  # Limit to avoid too many API calls
            try:
                search_limit = max(1, target_count // max(1, len(artists[:8])))
                
                # Search for tracks by this artist
                search_results = await self.youtube.search_tracks(f"{artist} songs", limit=search_limit)
                
                for track in search_results:
                    if track.id not in existing_ids and track not in tracks:
                        tracks.append(track)
                        if len(tracks) >= target_count:
                            break
                
                if len(tracks) >= target_count:
                    break
                    
            except Exception as e:
                logger.warning(f"Artist search failed for '{artist}': {e}")
                continue
        
        logger.info(f"Found {len(tracks)} artist-based tracks")
        return tracks
    
    async def _search_diverse_music(self, target_count: int, existing_ids: Set[str]) -> List[TrackInfo]:
        """Search for diverse music to fill remaining slots."""
        tracks = []
        
        diverse_terms = [
            "new music 2024", "trending songs", "popular music", "top hits",
            "fresh tracks", "latest releases", "viral songs"
        ]
        
        for term in diverse_terms[:3]:  # Limit searches
            try:
                search_limit = max(1, target_count // max(1, len(diverse_terms[:3])))
                search_results = await self.youtube.search_tracks(term, limit=search_limit)
                
                for track in search_results:
                    if track.id not in existing_ids and track not in tracks:
                        tracks.append(track)
                        if len(tracks) >= target_count:
                            break
                
                if len(tracks) >= target_count:
                    break
                    
            except Exception as e:
                logger.warning(f"Diverse search failed for '{term}': {e}")
                continue
        
        logger.info(f"Found {len(tracks)} diverse tracks")
        return tracks
    
    async def _get_user_tracks(self) -> List[TrackInfo]:
        """Get user's existing tracks to avoid duplicates."""
        try:
            # Get liked songs
            liked_tracks = await self.youtube.get_user_saved_tracks(limit=200)
            return liked_tracks
        except Exception as e:
            logger.warning(f"Could not get user tracks: {e}")
            return []
    
    def _deduplicate_tracks(self, tracks: List[TrackInfo]) -> List[TrackInfo]:
        """Remove duplicate tracks based on ID and similar names."""
        seen_ids = set()
        seen_names = set()
        unique_tracks = []
        
        for track in tracks:
            # Check ID
            if track.id in seen_ids:
                continue
            
            # Check similar names (normalize for comparison)
            normalized_name = track.name.lower().strip()
            if normalized_name in seen_names:
                continue
            
            seen_ids.add(track.id)
            seen_names.add(normalized_name)
            unique_tracks.append(track)
        
        return unique_tracks
    
    async def _create_discovery_playlist(self, tracks: List[TrackInfo]) -> Dict[str, Any]:
        """Create a new discovery playlist with the found tracks."""
        from datetime import datetime
        
        # Create playlist name with date
        today = datetime.now()
        playlist_name = f"Music Discovery - {today.strftime('%Y-%m-%d')}"
        
        try:
            # Check if playlist already exists
            existing_playlist = await self.youtube.find_playlist_by_name(playlist_name)
            
            if existing_playlist:
                logger.info(f"Found existing playlist: {playlist_name}")
                playlist_info = existing_playlist
            else:
                # Create new playlist
                description = f"Daily music discovery playlist generated on {today.strftime('%B %d, %Y')}"
                playlist_info = await self.youtube.create_playlist(playlist_name, description)
                logger.info(f"Created new playlist: {playlist_name}")
            
            # Update playlist with tracks
            track_uris = [track.uri for track in tracks]
            success, actual_count = await self.youtube.update_playlist_tracks(playlist_info.id, track_uris)
            
            if success:
                playlist_info.track_count = actual_count
                logger.info(f"Updated playlist {playlist_info.id} with {actual_count} tracks")
            else:
                logger.warning("Failed to update playlist tracks")
            
            return {
                'playlist_id': playlist_info.id,
                'playlist_name': playlist_info.name,
                'playlist_url': playlist_info.external_url,
                'tracks': tracks[:actual_count] if success else tracks,
                'stats': {
                    'total_discovered': actual_count if success else len(tracks)
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to create/update playlist: {e}")
            raise Exception(f"Could not create discovery playlist: {str(e)}") 