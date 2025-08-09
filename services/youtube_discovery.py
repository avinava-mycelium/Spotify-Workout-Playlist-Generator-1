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
        # Lightweight stopwords for token extraction (formatting words, non-genre)
        self._stopwords = {
            'official', 'audio', 'video', 'music', 'feat', 'ft', 'and', 'with', 'the', 'a', 'an',
            'remix', 'mix', 'hd', '4k', 'live', 'lyrics', 'edit', 'version', 'new', 'song', 'track',
            'vol', 'volume', 'best', 'epic', 'workout', 'gym', 'running', 'fitness'
        }
    
    async def discover_new_playlist(self, reference_playlist_id: str, target_size: int = 30) -> Dict[str, Any]:
        """Discover new tracks for YouTube Music playlist based on user's taste."""
        try:
            logger.info("Starting YouTube Music discovery process")

            # Reuse the track discovery routine
            discovery = await self.discover_tracks(reference_playlist_id, target_size)
            final_tracks = discovery.get('tracks', [])

            # Create playlist using discovered tracks
            playlist_payload = await self._create_discovery_playlist(final_tracks)

            # Flatten shape to match Spotify's return for CLI compatibility
            playlist_payload['taste_profile'] = discovery.get('taste_profile', {})
            playlist_payload['strategies_used'] = discovery.get('strategies_used', [])
            return playlist_payload
            
        except Exception as e:
            logger.error(f"Discovery failed: {e}")
            raise Exception(f"Failed to discover YouTube Music tracks: {str(e)}")

    async def discover_tracks(self, reference_playlist_id: str, target_size: int = 30) -> Dict[str, Any]:
        """Discover tracks only (without creating a playlist), used by curator fallback.

        Returns a dict with keys: 'tracks', 'taste_profile', 'strategies_used'.
        """
        # Analyze user's taste from reference playlist
        taste_profile = await self.analyze_taste_profile(reference_playlist_id)
        logger.info(f"Analyzed taste profile: {len(taste_profile['artists'])} artists, {len(taste_profile['genres'])} genres")

        # Get user's existing tracks to avoid duplicates
        existing_tracks = await self._get_user_tracks()
        existing_video_ids = {track.id for track in existing_tracks}
        logger.info(f"Found {len(existing_video_ids)} existing tracks to avoid")

        # Discover new tracks using multiple strategies
        discovered_tracks: List[TrackInfo] = []

        # Strategy 1: Search by workout terms (40%)
        workout_target = max(1, int(target_size * 0.4))
        workout_tracks = await self._search_workout_content(workout_target, existing_video_ids, taste_profile)
        discovered_tracks.extend(workout_tracks)

        # Strategy 2: Search by user's favorite terms (40%)
        if taste_profile['artists']:
            artist_target = max(1, int(target_size * 0.4))
            artist_tracks = await self._search_by_artists(taste_profile['artists'][:10], artist_target, existing_video_ids)
            discovered_tracks.extend(artist_tracks)

        # Strategy 3: Recent music search (fresh-first, 20%)
        diverse_target = max(1, target_size - len(discovered_tracks))
        if diverse_target > 0:
            recent_tracks = await self._search_recent_music(diverse_target, existing_video_ids, taste_profile)
            discovered_tracks.extend(recent_tracks)

        # Remove duplicates
        unique_tracks = self._deduplicate_tracks(discovered_tracks)

        # Enforce freshness: filter out any tracks from reference playlist and usage history
        usage_used_ids = self._load_used_track_ids()
        reference_ids = set(taste_profile.get('known_track_ids', set()))
        reference_names = set(taste_profile.get('reference_track_names', set()))
        slow_words = {'interview', 'interlude', 'ballad', 'acoustic', 'unplugged', 
                      'slow', 'soft', 'quiet', 'gentle', 'mellow', 'calm', 'peaceful'}

        filtered_tracks = []
        # Adaptive blocklist: only exclude tokens not present in user's taste tokens (derived from reference)
        edm_like = {'edm', 'trap', 'dubstep', 'electro', 'dance', 'remix', 'mix'}
        allowed_tokens = set((g or '').lower() for g in (taste_profile.get('genres') or [])) | set(
            (t or '').lower() for t in taste_profile.get('taste_tokens', [])
        )
        for tr in unique_tracks:
            name_l = tr.name.lower().strip() if tr.name else ''
            if tr.id in reference_ids:
                continue
            if name_l in reference_names:
                continue
            if tr.id in usage_used_ids:
                continue
            if any(w in name_l for w in slow_words):
                continue
            if any(w in name_l for w in edm_like) and not any(term in allowed_tokens for term in edm_like):
                continue
            filtered_tracks.append(tr)

        final_tracks = filtered_tracks[:target_size]

        logger.info(f"Discovered {len(final_tracks)} new tracks")

        return {
            'tracks': final_tracks,
            'taste_profile': taste_profile,
            'strategies_used': ['workout_search', 'artist_search', 'diverse_search']
        }
    
    async def analyze_taste_profile(self, reference_playlist_id: str) -> Dict[str, Any]:
        """Analyze user's music taste from reference playlist."""
        try:
            # Get reference playlist tracks
            reference_tracks = await self.youtube.get_playlist_tracks(reference_playlist_id)
            logger.info(f"Analyzing {len(reference_tracks)} reference tracks")
            
            if not reference_tracks:
                logger.warning("No reference tracks found")
                return {
                    'artists': [],
                    'genres': [],
                    'track_count': 0,
                    'known_track_ids': set(),
                    'reference_track_names': set()
                }
            
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

            # Also parse reference titles for genre-like hints (e.g., metal/rock) to guide searches
            title_genres = set()
            keyword_map = {
                'metal': 'metal',
                'rock': 'rock',
                'hardcore': 'hardcore',
                'grunge': 'grunge',
                'nu': 'nu metal',
                'post-grunge': 'post-grunge',
                'industrial': 'industrial',
                'hip hop': 'hip hop',
                'rap metal': 'rap metal',
                'alt': 'alternative',
                'alternative': 'alternative',
            }
            for t in reference_tracks:
                name_l = (t.name or '').lower()
                if 'hip hop' in name_l:
                    title_genres.add('hip hop')
                for kw, g in keyword_map.items():
                    if kw in name_l:
                        title_genres.add(g)
            if title_genres:
                genres = list(set(genres) | title_genres)
            
            # Build token-based taste profile from titles and artists
            taste_tokens = set()
            for t in reference_tracks:
                taste_tokens |= self._extract_tokens((t.name or '') + ' ' + (t.artist or ''))

            taste_profile = {
                'artists': top_artists,
                'genres': genres,
                'track_count': len(reference_tracks),
                'top_artist_counts': dict(artist_counts.most_common(10)),
                'known_track_ids': {t.id for t in reference_tracks},
                'reference_track_names': {t.name.lower().strip() for t in reference_tracks if t.name},
                'taste_tokens': list(taste_tokens)
            }
            
            logger.info(f"Taste profile: {len(top_artists)} artists, {len(genres)} derived genres")
            return taste_profile
            
        except Exception as e:
            logger.error(f"Failed to analyze taste profile: {e}")
            return {'artists': [], 'genres': [], 'track_count': 0, 'known_track_ids': set(), 'reference_track_names': set(), 'taste_tokens': []}
    
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
        
        # Normalize combined genres (e.g., hip hop)
        if 'hip' in genres and 'hop' in genres:
            genres.discard('hip')
            genres.discard('hop')
            genres.add('hip hop')

        return list(genres)

    def _extract_tokens(self, text: str) -> Set[str]:
        """Extract normalized tokens from text, excluding stopwords. Used to adapt filters to the reference playlist."""
        tokens: Set[str] = set()
        for raw in text.lower().replace('|', ' ').replace('-', ' ').split():
            t = raw.strip()
            if not t or t in self._stopwords or len(t) <= 2:
                continue
            tokens.add(t)
        return tokens
    
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

                # Prefer newer content: try multiple queries per artist
                queries = [
                    f"{artist} latest official audio",
                    f"{artist} new 2024",
                    f"{artist} new 2025",
                    f"{artist} songs"
                ]

                search_results: List[TrackInfo] = []
                for q in queries:
                    results = await self.youtube.search_tracks(q, limit=search_limit)
                    search_results.extend(results)

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
    
    async def _search_recent_music(self, target_count: int, existing_ids: Set[str], taste_profile: Dict[str, Any]) -> List[TrackInfo]:
        """Search for recent music uploads using YouTube Data API with publishedAfter filter."""
        tracks: List[TrackInfo] = []
        queries: List[str] = []

        # Bias queries with artists and derived genres from reference
        for artist in (taste_profile.get('artists') or [])[:5]:
            queries.append(f"{artist} official audio")
            queries.append(f"{artist} new song")

        for genre in (taste_profile.get('genres') or [])[:3]:
            queries.append(f"{genre} new music")

        # Generic if none available
        if not queries:
            queries = ["new music", "latest release"]

        per_query = max(1, target_count // max(1, len(queries)))
        for q in queries:
            try:
                # Use last 30 days for maximum freshness
                results = await self.youtube.search_recent_music(q, limit=per_query, days=30)
                for tr in results:
                    if tr.id not in existing_ids and tr not in tracks:
                        tracks.append(tr)
                        if len(tracks) >= target_count:
                            break
                if len(tracks) >= target_count:
                    break
            except Exception as e:
                logger.warning(f"Recent search failed for '{q}': {e}")
                continue

        logger.info(f"Found {len(tracks)} recent tracks")
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

    def _load_used_track_ids(self) -> Set[str]:
        """Load previously used track IDs from youtube_usage_history.json for freshness filtering."""
        from pathlib import Path
        import json
        used: Set[str] = set()
        history_path = Path.cwd() / "youtube_usage_history.json"
        try:
            if history_path.exists():
                with open(history_path, 'r') as f:
                    data = json.load(f)
                for day in data.values():
                    for t in day.get('tracks', []):
                        tid = t.get('id')
                        if tid:
                            used.add(tid)
        except Exception as e:
            logger.warning(f"Could not read usage history for freshness: {e}")
        return used
    
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