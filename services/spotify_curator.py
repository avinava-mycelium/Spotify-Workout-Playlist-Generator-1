"""Spotify curator implementation."""

import json
import random
from datetime import datetime
from typing import Dict, List, Any
from pathlib import Path
from collections import Counter

from loguru import logger

from base_music_service import BaseCurator, TrackInfo
from services.spotify_service import SpotifyService


class SpotifyCurator(BaseCurator):
    """Spotify-specific implementation of playlist curation."""
    
    def __init__(self, music_service: SpotifyService):
        """Initialize with Spotify service."""
        super().__init__(music_service)
        self.spotify = music_service
        self.history_file = Path.cwd() / "spotify_usage_history.json"
    
    async def generate_curated_playlist(self, reference_playlist_id: str, target_size: int = 30) -> Dict[str, Any]:
        """Generate a curated playlist from existing Spotify tracks."""
        try:
            logger.info("Generating curated Spotify playlist with enhanced variety algorithms")
            
            # Get reference playlist tracks
            reference_tracks = await self.spotify.get_playlist_tracks(reference_playlist_id)
            logger.info(f"Reference playlist has {len(reference_tracks)} tracks")
            
            if not reference_tracks:
                raise ValueError("Reference playlist is empty")
            
            # Load usage history
            usage_history = self._load_usage_history()
            
            # Smart selection with variety optimization
            selected_tracks = await self._smart_select_with_history(reference_tracks, usage_history, target_size, reference_playlist_id)
            
            # Update usage history
            self._update_usage_history(selected_tracks, usage_history)
            
            logger.info(f"Selected {len(selected_tracks)} tracks with optimized variety")
            
            # Create playlist
            today = datetime.now()
            playlist_name = f"Daily Workout Mix - {today.strftime('%Y-%m-%d')}"
            
            # Check if playlist exists
            existing_playlist = await self.spotify.find_playlist_by_name(playlist_name)
            if existing_playlist:
                playlist_info = existing_playlist
                logger.info(f"Found existing playlist: {playlist_name}")
            else:
                description = f"Daily workout playlist with maximum variety, curated on {today.strftime('%B %d, %Y')}."
                playlist_info = await self.spotify.create_playlist(playlist_name, description)
                logger.info(f"Created new playlist: {playlist_name}")
            
            # Update playlist
            track_uris = [track.uri for track in selected_tracks]
            await self.spotify.update_playlist_tracks(playlist_info.id, track_uris)
            
            # Also update main playlist
            main_playlist = await self.spotify.find_playlist_by_name("Daily Workout Mix")
            if main_playlist:
                await self.spotify.update_playlist_tracks(main_playlist.id, track_uris)
                logger.info("Updated main Daily Workout Mix playlist")
            
            # Calculate freshness stats
            stats = self._calculate_freshness_stats(selected_tracks, usage_history)
            
            return {
                'playlist_id': playlist_info.id,
                'playlist_name': playlist_info.name,
                'playlist_url': playlist_info.external_url,
                'tracks': selected_tracks,
                'freshness_score': stats['freshness_score'],
                'stats': stats,
                'total_tracks_available': len(reference_tracks)
            }
            
        except Exception as e:
            logger.error(f"Curation failed: {e}")
            raise
    
    async def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics for the Spotify curator."""
        usage_history = self._load_usage_history()
        
        if not usage_history:
            return {
                'total_tracks_used': 0,
                'total_playlists_generated': 0,
                'most_used_tracks': [],
                'least_used_tracks': [],
                'usage_distribution': {}
            }
        
        track_usage_counts = {}
        for track_id, usage_data in usage_history.items():
            track_usage_counts[track_id] = usage_data['count']
        
        # Sort by usage count
        sorted_usage = sorted(track_usage_counts.items(), key=lambda x: x[1])
        
        return {
            'total_tracks_used': len(track_usage_counts),
            'total_playlists_generated': max(usage_data.get('count', 0) for usage_data in usage_history.values()) if usage_history else 0,
            'most_used_tracks': sorted_usage[-5:],  # Top 5 most used
            'least_used_tracks': sorted_usage[:5],   # Top 5 least used
            'usage_distribution': self._get_usage_distribution(track_usage_counts)
        }
    
    def _load_usage_history(self) -> Dict[str, Any]:
        """Load usage history from file."""
        try:
            if self.history_file.exists():
                with open(self.history_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load usage history: {e}")
        
        return {}
    
    def _save_usage_history(self, history: Dict[str, Any]) -> None:
        """Save usage history to file."""
        try:
            with open(self.history_file, 'w') as f:
                json.dump(history, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save usage history: {e}")
    
    async def _smart_select_with_history(self, reference_tracks: List[TrackInfo], usage_history: Dict[str, Any], target_size: int, reference_playlist_id: str = None) -> List[TrackInfo]:
        """Select tracks with anti-repetition algorithm."""
        # Score each track based on usage history and variety factors
        track_scores = []
        
        # Get artist distribution in reference playlist
        artist_counts = Counter()
        for track in reference_tracks:
            # Handle multiple artists
            artists = [artist.strip() for artist in track.artist.split(',')]
            for artist in artists:
                artist_counts[artist] += 1
        
        for track in reference_tracks:
            score = self._calculate_track_score(track, usage_history, artist_counts)
            track_scores.append((track, score))
        
        # Sort by score (higher is better)
        track_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Select tracks with artist variety constraints - but ONLY good scores
        selected_tracks = []
        used_artists = set()
        
        for track, score in track_scores:
            if len(selected_tracks) >= target_size:
                break
            
            # STRICT: Only consider tracks with decent scores (not recently used)
            if score < 5:  # Skip tracks with very poor scores (recently used)
                continue
                
            # Check artist variety
            track_artists = {artist.strip() for artist in track.artist.split(',')}
            
            # Allow track if it doesn't repeat artists too much
            artist_overlap = len(track_artists & used_artists)
            max_allowed_overlap = 1  # Allow some artist repetition but limit it
            
            if artist_overlap <= max_allowed_overlap or len(selected_tracks) < target_size // 2:
                selected_tracks.append(track)
                used_artists.update(track_artists)
        
        # If we don't have enough tracks, be MUCH more selective about fallback
        if len(selected_tracks) < target_size:
            # Only consider tracks that haven't been heavily used
            acceptable_tracks = []
            for track, score in track_scores:
                if track not in selected_tracks and score > 10:  # Only tracks with decent scores
                    track_usage = usage_history.get(track.id, {})
                    hours_since_last = float('inf')
                    
                    if track_usage.get('last_used'):
                        try:
                            last_used = datetime.fromisoformat(track_usage['last_used'])
                            hours_since_last = (datetime.now() - last_used).total_seconds() / 3600
                        except:
                            pass
                    
                    # Only add if not used recently or not used much
                    usage_count = track_usage.get('count', 0)
                    if hours_since_last >= 12 or usage_count <= 2:  # At least 12 hours old OR used ≤2 times
                        acceptable_tracks.append(track)
            
            # Add acceptable tracks up to target size
            needed = target_size - len(selected_tracks)
            selected_tracks.extend(acceptable_tracks[:needed])
            
            # If STILL not enough, DISCOVER NEW TRACKS from the internet!
            if len(selected_tracks) < target_size:
                logger.info(f"🔍 Only found {len(selected_tracks)} tracks from reference playlist. Discovering fresh tracks from the internet...")
                
                # Import and use discovery engine
                try:
                    from .spotify_discovery import SpotifyDiscoveryEngine
                    discovery_engine = SpotifyDiscoveryEngine(self.music_service)
                    
                    # DYNAMICALLY analyze the reference playlist to learn taste
                    logger.info("🔍 Analyzing your reference playlist to learn your taste...")
                    taste_profile = await discovery_engine.analyze_taste_profile(reference_playlist_id)
                    
                    logger.info(f"📊 Found genres: {', '.join(taste_profile['genres'][:5])}")
                    logger.info(f"🎤 Found {len(taste_profile['artist_infos'])} artists to use as seeds")
                    
                    # Discover fresh tracks based on ACTUAL analyzed taste
                    needed = target_size - len(selected_tracks)
                    logger.info(f"🎵 Discovering {needed} fresh tracks based on YOUR actual taste profile...")
                    
                    if taste_profile['genres'] or taste_profile['artist_infos']:
                        fresh_tracks = await discovery_engine._discover_tracks(taste_profile, needed * 2)  # Get extra for filtering
                    else:
                        logger.warning("No source tracks available for taste analysis")
                        fresh_tracks = []
                    
                    # Filter out any tracks we already have in usage history OR reference playlist
                    reference_track_names = {track.name.lower() for track in reference_tracks}
                    reference_track_ids = {track.id for track in reference_tracks}
                    
                    # Words that indicate slow/mellow tracks to avoid
                    slow_words = {'interview', 'interlude', 'ballad', 'acoustic', 'unplugged', 
                                 'slow', 'soft', 'quiet', 'gentle', 'mellow', 'calm', 'peaceful',
                                 'silence', 'whisper', 'lullaby', 'serenade', 'tender'}
                    
                    truly_fresh = []
                    for track in fresh_tracks:
                        track_name_lower = track.name.lower()
                        
                        # Check if track name contains slow/mellow indicators
                        has_slow_words = any(word in track_name_lower for word in slow_words)
                        
                        # Block if in usage history, reference playlist, already selected, or sounds slow
                        if (track.id not in usage_history and 
                            track.id not in reference_track_ids and
                            track.name.lower() not in reference_track_names and
                            track not in selected_tracks and
                            not has_slow_words):
                            truly_fresh.append(track)
                            if len(truly_fresh) >= needed:
                                break
                    
                    logger.info(f"✨ Found {len(truly_fresh)} completely fresh tracks from internet discovery")
                    selected_tracks.extend(truly_fresh)
                    
                except Exception as e:
                    logger.error(f"Failed to discover fresh tracks: {e}")
                    logger.warning(f"Could only find {len(selected_tracks)} fresh tracks out of {target_size} requested. Preferring quality over quantity.")
        
        # Shuffle to avoid predictable ordering
        random.shuffle(selected_tracks)
        
        logger.info(f"Selected {len(selected_tracks)} tracks with variety score optimization")
        return selected_tracks[:target_size]
    
    def _calculate_track_score(self, track: TrackInfo, usage_history: Dict[str, Any], artist_counts: Counter) -> float:
        """Calculate a score for track selection (higher = more likely to be selected)."""
        score = 100.0  # Base score
        
        # Factor 1: Usage frequency (less used = higher score)
        track_usage = usage_history.get(track.id, {})
        usage_count = track_usage.get('count', 0)
        
        # MUCH more aggressive penalties for recently used tracks
        if usage_count == 0:
            score += 80  # Huge bonus for never used tracks
        elif usage_count == 1:
            score += 40  # Good bonus for rarely used
        elif usage_count == 2:
            score += 15  # Small bonus for lightly used
        elif usage_count == 3:
            score -= 20  # Penalty for moderate use
        else:
            score -= usage_count * 15  # Heavy penalty for overuse
        
        # Factor 2: Time since last use - MUCH stricter
        last_used = track_usage.get('last_used')
        if last_used:
            try:
                last_used_date = datetime.fromisoformat(last_used)
                hours_since = (datetime.now() - last_used_date).total_seconds() / 3600
                
                if hours_since < 12:  # Used in last 12 hours
                    return 0.1  # Effectively block this track
                elif hours_since < 24:  # Used today
                    score -= 80  # Massive penalty
                elif hours_since < 72:  # Used in last 3 days
                    score -= 50  # Heavy penalty
                elif hours_since < 168:  # Used this week
                    score -= 25  # Moderate penalty
                else:  # Older than a week
                    days_since = hours_since / 24
                    score += min(days_since * 3, 50)  # Bonus for aging
            except:
                pass
        else:
            score += 30  # Bonus for tracks never used
        
        # Factor 3: Artist variety (prefer less common artists in the reference playlist)
        track_artists = [artist.strip() for artist in track.artist.split(',')]
        for artist in track_artists:
            artist_frequency = artist_counts.get(artist, 1)
            if artist_frequency == 1:
                score += 15  # Bigger bonus for unique artists
            elif artist_frequency <= 3:
                score += 8   # Good bonus for less common artists
            else:
                score -= 5   # Penalty for very common artists
        
        # Factor 4: Track popularity (slight preference for popular tracks)
        if track.popularity:
            score += track.popularity * 0.1
        
        # Factor 5: Randomization factor to avoid deterministic selection
        score += random.uniform(-3, 3)
        
        return max(score, 0.1)  # Ensure minimum score but allow very low ones
    
    def _update_usage_history(self, selected_tracks: List[TrackInfo], usage_history: Dict[str, Any]) -> None:
        """Update usage history with newly selected tracks."""
        current_time = datetime.now().isoformat()
        
        for track in selected_tracks:
            if track.id not in usage_history:
                usage_history[track.id] = {
                    'count': 0,
                    'first_used': current_time,
                    'track_name': track.name,
                    'artist': track.artist
                }
            
            usage_history[track.id]['count'] += 1
            usage_history[track.id]['last_used'] = current_time
        
        # Save updated history
        self._save_usage_history(usage_history)
        logger.info(f"Updated usage history for {len(selected_tracks)} tracks")
    
    def _calculate_freshness_stats(self, selected_tracks: List[TrackInfo], usage_history: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate freshness statistics for the selected tracks."""
        never_used = 0
        rarely_used = 0  # 1-2 times
        frequently_used = 0  # 3+ times
        
        for track in selected_tracks:
            usage_count = usage_history.get(track.id, {}).get('count', 0)
            
            if usage_count == 0:
                never_used += 1
            elif usage_count <= 2:
                rarely_used += 1
            else:
                frequently_used += 1
        
        total_tracks = len(selected_tracks)
        if total_tracks == 0:
            freshness_score = 0
        else:
            freshness_score = ((never_used * 1.0) + (rarely_used * 0.7) + (frequently_used * 0.3)) / total_tracks * 100
        
        return {
            'freshness_score': freshness_score,
            'never_used': never_used,
            'rarely_used': rarely_used,
            'frequently_used': frequently_used,
            'total_tracks': total_tracks,
            'distribution': {
                'never_used_pct': (never_used / total_tracks) * 100 if total_tracks > 0 else 0,
                'rarely_used_pct': (rarely_used / total_tracks) * 100 if total_tracks > 0 else 0,
                'frequently_used_pct': (frequently_used / total_tracks) * 100 if total_tracks > 0 else 0
            }
        }
    
    def _get_usage_distribution(self, track_usage_counts: Dict[str, int]) -> Dict[str, int]:
        """Get distribution of usage counts."""
        distribution = {}
        
        for count in track_usage_counts.values():
            if count in distribution:
                distribution[count] += 1
            else:
                distribution[count] = 1
        
        return distribution 