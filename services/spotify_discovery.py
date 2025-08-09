"""Spotify discovery engine implementation."""

import random
from datetime import datetime
from typing import Dict, List, Any, Set
from collections import Counter

from loguru import logger

from base_music_service import BaseDiscoveryEngine, TrackInfo, ArtistInfo
from services.spotify_service import SpotifyService


class SpotifyDiscoveryEngine(BaseDiscoveryEngine):
    """Spotify-specific implementation of music discovery."""
    
    def __init__(self, music_service: SpotifyService):
        """Initialize with Spotify service."""
        super().__init__(music_service)
        self.spotify = music_service
    
    async def discover_new_playlist(self, reference_playlist_id: str, target_size: int = 30) -> Dict[str, Any]:
        """Discover new tracks based on a Spotify reference playlist."""
        try:
            logger.info("Starting Spotify music discovery process")
            
            # Step 1: Analyze taste profile
            taste_profile = await self.analyze_taste_profile(reference_playlist_id)
            logger.info(f"Analyzed taste profile: {len(taste_profile['artists'])} artists, {len(taste_profile['genres'])} genres")
            
            # Step 2: Discover new tracks
            new_tracks = await self._discover_tracks(taste_profile, target_size * 3)  # Get more than needed for better selection
            logger.info(f"Discovered {len(new_tracks)} potential new tracks")
            
            # Step 3: Filter out known tracks
            filtered_tracks = await self._filter_unknown_tracks(new_tracks, taste_profile['known_track_ids'])
            logger.info(f"After filtering known tracks: {len(filtered_tracks)} truly new tracks")
            
            if not filtered_tracks:
                raise ValueError("No new tracks discovered. Try expanding your reference playlist or check back later.")
            
            # Step 4: Select best tracks for playlist
            selected_tracks = self._select_best_tracks(filtered_tracks, target_size)
            
            # Step 5: Create discovery playlist
            result = await self._create_discovery_playlist(selected_tracks, taste_profile)
            
            logger.info(f"Successfully created discovery playlist with {len(selected_tracks)} new tracks")
            return result
            
        except Exception as e:
            logger.error(f"Discovery failed: {e}")
            raise
    
    async def analyze_taste_profile(self, reference_playlist_id: str) -> Dict[str, Any]:
        """Analyze user's taste profile from Spotify reference playlist."""
        # Get reference playlist tracks
        reference_tracks = await self.spotify.get_playlist_tracks(reference_playlist_id)
        
        if not reference_tracks:
            raise ValueError("Reference playlist is empty or inaccessible")
        
        logger.info(f"Analyzing taste from {len(reference_tracks)} reference tracks")
        
        # Extract unique artists
        artists = []
        for track in reference_tracks:
            # Handle multiple artists (split by comma)
            track_artists = [artist.strip() for artist in track.artist.split(',')]
            artists.extend(track_artists)
        
        # Get detailed artist info and genres
        unique_artists = list(set(artists))
        artist_genres = []
        artist_infos = []
        
        for artist_name in unique_artists[:50]:  # Limit to avoid rate limits
            try:
                # Search for artist to get ID
                search_results = await self.spotify.search_tracks(f"artist:{artist_name}", limit=1)
                if search_results:
                    # Get the actual track to extract artist info
                    track_data = self.spotify.client.track(search_results[0].id)
                    if track_data and track_data['artists']:
                        main_artist_id = track_data['artists'][0]['id']
                        artist_info = await self.spotify.get_artist_info(main_artist_id)
                        artist_infos.append(artist_info)
                        artist_genres.extend(artist_info.genres)
            except Exception as e:
                logger.warning(f"Could not get artist info for {artist_name}: {e}")
                continue
        
        # Count genres
        genre_counts = Counter(artist_genres)
        top_genres = [genre for genre, count in genre_counts.most_common(10)]
        
        # Get known track IDs (for filtering)
        known_track_ids = {track.id for track in reference_tracks}
        
        # Also add user's saved tracks to known list
        try:
            saved_tracks = await self.spotify.get_user_saved_tracks(limit=200)
            known_track_ids.update(track.id for track in saved_tracks)
        except Exception as e:
            logger.warning(f"Could not get saved tracks: {e}")

        # Also add recently played track IDs to avoid repeats
        try:
            recent_ids = await self.spotify.get_recently_played_ids(limit=50)
            known_track_ids.update(recent_ids)
        except Exception as e:
            logger.warning(f"Could not get recently played tracks: {e}")
        
        taste_profile = {
            'genres': top_genres,
            'artists': unique_artists,
            'artist_infos': artist_infos,
            'known_track_ids': known_track_ids,
            'reference_tracks': reference_tracks,
            'artists_analyzed': len(artist_infos)
        }
        
        logger.info(f"Taste profile: {len(top_genres)} genres, {len(unique_artists)} artists")
        return taste_profile
    
    async def _discover_tracks(self, taste_profile: Dict[str, Any], target_count: int) -> List[TrackInfo]:
        """Discover new tracks using advanced Spotify discovery methods."""
        discovered_tracks = []
        
        # Method 1: Spotify Recommendations API (MOST POWERFUL - millions of tracks)
        recommendation_tracks = await self._get_spotify_recommendations(taste_profile, target_count)
        discovered_tracks.extend(recommendation_tracks)
        
        # Method 2: Advanced genre + audio feature searches
        feature_tracks = await self._search_by_audio_features(taste_profile, target_count // 2)
        discovered_tracks.extend(feature_tracks)
        
        # Method 3: Genre-based search (expanded)
        genre_tracks = await self._search_by_genres(taste_profile['genres'], target_count // 2)
        discovered_tracks.extend(genre_tracks)
        
        # Method 4: Related artist exploration (expanded)
        related_tracks = await self._find_related_artists_tracks(taste_profile['artist_infos'], target_count // 2)
        discovered_tracks.extend(related_tracks)
        
        # Method 5: Similar track searches
        similar_tracks = await self._search_similar_tracks(taste_profile, target_count // 3)
        discovered_tracks.extend(similar_tracks)
        
        # Method 6: Workout-specific search (expanded)
        workout_tracks = await self._search_workout_genres(taste_profile, target_count // 4)
        discovered_tracks.extend(workout_tracks)
        
        # Method 7: Popularity tier searches (find hidden gems)
        hidden_gems = await self._search_hidden_gems(taste_profile, target_count // 4)
        discovered_tracks.extend(hidden_gems)
        
        # Remove duplicates while preserving order
        seen_ids = set()
        unique_tracks = []
        for track in discovered_tracks:
            if track.id not in seen_ids:
                seen_ids.add(track.id)
                unique_tracks.append(track)
        
        logger.info(f"Discovered {len(unique_tracks)} unique tracks from {len(discovered_tracks)} total searches")
        return unique_tracks
    
    async def _search_by_genres(self, genres: List[str], target_count: int) -> List[TrackInfo]:
        """Search for tracks by genre."""
        tracks = []
        
        for genre in genres[:5]:  # Use top 5 genres
            try:
                # Search with genre filter
                query = f"genre:{genre}"
                search_limit = max(1, target_count // max(1, len(genres[:5])))  # Ensure minimum 1
                genre_tracks = await self.spotify.search_tracks(query, limit=search_limit)
                tracks.extend(genre_tracks)
                
                logger.info(f"Found {len(genre_tracks)} tracks for genre: {genre}")
            except Exception as e:
                logger.warning(f"Genre search failed for {genre}: {e}")
        
        return tracks
    
    async def _find_related_artists_tracks(self, artist_infos: List[ArtistInfo], target_count: int) -> List[TrackInfo]:
        """Find tracks from artists related to user's favorites."""
        tracks = []
        
        for artist_info in artist_infos[:10]:  # Use top 10 artists
            try:
                # Get related artists
                related_artists = await self.spotify.get_related_artists(artist_info.id)
                
                # Get top tracks from related artists
                for related_artist in related_artists[:3]:  # Top 3 related per artist
                    try:
                        artist_tracks = await self.spotify.get_artist_top_tracks(related_artist.id, limit=2)
                        tracks.extend(artist_tracks)
                    except Exception as e:
                        logger.warning(f"Could not get tracks for related artist {related_artist.name}: {e}")
                        
            except Exception as e:
                logger.warning(f"Could not get related artists for {artist_info.name}: {e}")
        
        logger.info(f"Found {len(tracks)} tracks from related artists")
        return tracks
    
    async def _search_workout_genres(self, taste_profile: Dict[str, Any], target_count: int) -> List[TrackInfo]:
        """Search for workout music based on user's actual taste profile."""
        tracks = []
        
        # Use the ACTUAL genres from the user's playlist
        user_genres = taste_profile.get('genres', [])[:5]  # Top 5 genres
        
        if not user_genres:
            # Fallback to general workout search if no genres found
            user_genres = ['workout', 'rock', 'metal']
        
        # Create workout-focused searches based on USER'S genres
        workout_searches = []
        for genre in user_genres:
            # Add workout/energy modifiers to user's genres
            workout_searches.extend([
                f"{genre} workout high energy",
                f"{genre} aggressive fast tempo",
                f"{genre} pump up intense"
            ])
        
        per_query = max(1, target_count // len(workout_searches))
        
        for query in workout_searches[:10]:  # Limit to 10 searches
            try:
                query_tracks = await self.spotify.search_tracks(query, limit=per_query)
                tracks.extend(query_tracks)
            except Exception as e:
                logger.warning(f"Workout search failed for '{query}': {e}")
        
        logger.info(f"Found {len(tracks)} workout tracks based on user's genres: {user_genres}")
        return tracks
    
    async def _get_spotify_recommendations(self, taste_profile: Dict[str, Any], target_count: int) -> List[TrackInfo]:
        """Use Spotify's powerful recommendations API to discover millions of tracks."""
        tracks = []
        
        try:
            # Spotify recommendations API parameters
            seed_artists = [artist.id for artist in taste_profile['artist_infos'][:5]]  # Max 5 seed artists
            seed_genres = []
            # Validate genres against Spotify's allowed seeds to avoid 400 errors
            try:
                allowed = set(await self.spotify.get_available_genre_seeds())
                seed_genres = [g for g in taste_profile['genres'][:5] if g in allowed]
            except Exception:
                seed_genres = taste_profile['genres'][:5]
            
            # Audio feature targets for workout music
            audio_features = {
                'target_energy': 0.9,        # VERY high energy (aggressive)
                'target_danceability': 0.4,  # Lower danceability (more rock/metal)
                'target_valence': 0.5,       # Neutral/aggressive mood (not too happy)
                'min_tempo': 130,             # Higher minimum BPM (aggressive)
                'target_tempo': 160,          # Much higher target BPM (fast/aggressive)
                'min_popularity': 50,         # Popular tracks but allow some variety
                'target_popularity': 80       # Target popular tracks
            }
            
            # Multiple recommendation calls for variety
            for i in range(3):  # 3 batches of recommendations
                try:
                    # Vary the seed combinations for each batch
                    batch_artists = seed_artists[i:i+3] if len(seed_artists) > i else seed_artists[:3]
                    batch_genres = seed_genres[i:i+2] if len(seed_genres) > i else seed_genres[:2]
                    
                    # Slightly vary audio features for each batch
                    varied_features = audio_features.copy()
                    varied_features['target_energy'] += (i - 1) * 0.1  # 0.7, 0.8, 0.9
                    varied_features['target_tempo'] += i * 10  # 130, 140, 150
                    
                    recommendations = await self.spotify.get_recommendations(
                        seed_artists=batch_artists,
                        seed_genres=batch_genres,
                        limit=target_count // 2,  # Get plenty per batch
                        **varied_features
                    )
                    
                    tracks.extend(recommendations)
                    logger.info(f"Batch {i+1}: Found {len(recommendations)} recommendations")
                    
                except Exception as e:
                    logger.warning(f"Recommendation batch {i+1} failed: {e}")
            
            logger.info(f"Total recommendations found: {len(tracks)}")
            
        except Exception as e:
            logger.warning(f"Spotify recommendations failed: {e}")
        
        return tracks
    
    async def _search_by_audio_features(self, taste_profile: Dict[str, Any], target_count: int) -> List[TrackInfo]:
        """Search tracks by combining genres with specific audio features."""
        tracks = []
        
        # Audio feature combinations for different workout moods
        feature_combinations = [
            # High energy metal/rock
            {'genre': 'metal', 'energy': '0.8..1.0', 'tempo': '120..180', 'danceability': '0.3..0.8'},
            # Electronic workout
            {'genre': 'electronic', 'energy': '0.7..1.0', 'tempo': '128..140', 'danceability': '0.6..1.0'},
            # Hip hop workout
            {'genre': 'hip hop', 'energy': '0.6..0.9', 'tempo': '80..120', 'danceability': '0.7..1.0'},
            # Alternative/indie energy
            {'genre': 'alternative', 'energy': '0.6..0.9', 'tempo': '100..160', 'valence': '0.4..0.8'},
        ]
        
        for combo in feature_combinations:
            try:
                # Build advanced search query
                query_parts = [f"genre:{combo['genre']}"]
                
                # Add audio feature filters
                for feature, range_val in combo.items():
                    if feature != 'genre':
                        query_parts.append(f"{feature}:{range_val}")
                
                query = ' '.join(query_parts)
                search_tracks = await self.spotify.search_tracks(query, limit=target_count // 4)
                tracks.extend(search_tracks)
                
                logger.info(f"Audio feature search '{combo['genre']}': {len(search_tracks)} tracks")
                
            except Exception as e:
                logger.warning(f"Audio feature search failed for {combo}: {e}")
        
        return tracks
    
    async def _search_similar_tracks(self, taste_profile: Dict[str, Any], target_count: int) -> List[TrackInfo]:
        """Search for tracks similar to user's favorites using track names and artists."""
        tracks = []
        
        try:
            # Get some reference track names for similarity searches
            reference_tracks = taste_profile.get('sample_tracks', [])[:10]
            
            for ref_track in reference_tracks:
                try:
                    # Search variations of track/artist names
                    artist_name = ref_track.get('artist', '').split(',')[0].strip()
                    track_name = ref_track.get('name', '')
                    
                    # Search for similar artist styles
                    if artist_name:
                        query = f'artist:"{artist_name}" OR genre:"{artist_name.lower()}"'
                        similar_tracks = await self.spotify.search_tracks(query, limit=5)
                        tracks.extend(similar_tracks)
                    
                except Exception as e:
                    logger.warning(f"Similar track search failed for {ref_track}: {e}")
            
            logger.info(f"Similar track searches found: {len(tracks)} tracks")
            
        except Exception as e:
            logger.warning(f"Similar tracks search failed: {e}")
        
        return tracks
    
    async def _search_hidden_gems(self, taste_profile: Dict[str, Any], target_count: int) -> List[TrackInfo]:
        """Search for less popular but quality tracks in user's genres."""
        tracks = []
        
        for genre in taste_profile['genres'][:3]:
            try:
                # Search for tracks with lower popularity (hidden gems)
                queries = [
                    f'genre:"{genre}" year:2020..2024',  # Recent tracks
                    f'genre:"{genre}" year:2015..2019',  # Slightly older
                    f'genre:"{genre}" year:2010..2014',  # Classic period
                ]
                
                for query in queries:
                    hidden_tracks = await self.spotify.search_tracks(query, limit=target_count // 9)
                    tracks.extend(hidden_tracks)
                
                logger.info(f"Hidden gems for {genre}: {len(tracks)} tracks found")
                
            except Exception as e:
                logger.warning(f"Hidden gems search failed for {genre}: {e}")
        
        return tracks
    
    async def _filter_unknown_tracks(self, tracks: List[TrackInfo], known_track_ids: Set[str]) -> List[TrackInfo]:
        """Filter out tracks that the user already knows."""
        unknown_tracks = [track for track in tracks if track.id not in known_track_ids]
        
        logger.info(f"Filtered out {len(tracks) - len(unknown_tracks)} known tracks")
        return unknown_tracks
    
    def _select_best_tracks(self, tracks: List[TrackInfo], target_count: int) -> List[TrackInfo]:
        """Select the best tracks for the playlist."""
        if len(tracks) <= target_count:
            return tracks
        
        # Sort by popularity (higher is better) and randomize within popularity tiers
        sorted_tracks = sorted(tracks, key=lambda t: (t.popularity or 0), reverse=True)
        
        # Take top tracks with some randomization
        top_tier = sorted_tracks[:target_count * 2]  # Top tier candidates
        selected = random.sample(top_tier, min(target_count, len(top_tier)))
        
        logger.info(f"Selected {len(selected)} best tracks from {len(tracks)} candidates")
        return selected
    
    async def _create_discovery_playlist(self, tracks: List[TrackInfo], taste_profile: Dict[str, Any]) -> Dict[str, Any]:
        """Create the discovery playlist."""
        today = datetime.now()
        playlist_name = f"Music Discovery - {today.strftime('%Y-%m-%d')}"
        
        description = (
            f"Discovered {len(tracks)} new tracks based on your taste profile. "
            f"Genres: {', '.join(taste_profile['genres'][:3])}. "
            f"Generated on {today.strftime('%B %d, %Y')}."
        )
        
        # Check if playlist exists
        existing_playlist = await self.spotify.find_playlist_by_name(playlist_name)
        if existing_playlist:
            playlist_info = existing_playlist
            logger.info(f"Found existing playlist: {playlist_name}")
        else:
            playlist_info = await self.spotify.create_playlist(playlist_name, description)
            logger.info(f"Created new playlist: {playlist_name}")
        
        # Update playlist with tracks
        track_uris = [track.uri for track in tracks]
        await self.spotify.update_playlist_tracks(playlist_info.id, track_uris)
        
        return {
            'playlist_id': playlist_info.id,
            'playlist_name': playlist_info.name,
            'playlist_url': playlist_info.external_url,
            'tracks': tracks,
            'taste_profile': {
                'genres': taste_profile['genres'],
                'artists_analyzed': taste_profile['artists_analyzed']
            },
            'discovery_methods': ['genre_search', 'related_artists', 'workout_genres'],
            'stats': {
                'total_discovered': len(tracks),
                'avg_popularity': sum(track.popularity or 0 for track in tracks) / len(tracks) if tracks else 0
            }
        } 