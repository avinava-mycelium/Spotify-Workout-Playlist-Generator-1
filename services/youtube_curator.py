"""YouTube Music curator implementation."""

import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any
from pathlib import Path
from collections import Counter

from loguru import logger

from base_music_service import BaseCurator, TrackInfo
from services.youtube_service import YouTubeMusicService


class YouTubeCurator(BaseCurator):
    """YouTube Music-specific implementation of playlist curation."""
    
    def __init__(self, music_service: YouTubeMusicService):
        """Initialize with YouTube Music service."""
        super().__init__(music_service)
        self.youtube = music_service
        self.history_file = Path.cwd() / "youtube_usage_history.json"
    
    async def generate_curated_playlist(self, reference_playlist_id: str, target_size: int = 30) -> Dict[str, Any]:
        """Generate a curated playlist from existing YouTube Music tracks."""
        try:
            logger.info("Generating curated YouTube Music playlist with enhanced variety algorithms")
            
            # Get reference playlist tracks
            reference_tracks = await self.youtube.get_playlist_tracks(reference_playlist_id)
            logger.info(f"Reference playlist has {len(reference_tracks)} tracks")
            
            if not reference_tracks:
                raise ValueError("Reference playlist is empty")
            
            # Load usage history
            usage_history = self._load_usage_history()
            
            # Smart selection with variety optimization
            selected_tracks = await self._smart_select_with_history(reference_tracks, usage_history, target_size, reference_playlist_id)
            
            logger.info(f"Selected {len(selected_tracks)} tracks with optimized variety")
            
            # Create playlist
            today = datetime.now()
            playlist_name = f"Curated Workout - {today.strftime('%Y-%m-%d')}"
            
            # Check if playlist already exists
            existing_playlist = await self.youtube.find_playlist_by_name(playlist_name)
            
            if existing_playlist:
                logger.info(f"Found existing playlist: {playlist_name}")
                playlist_info = existing_playlist
            else:
                # Create new playlist
                description = f"Smart curated playlist generated on {today.strftime('%B %d, %Y')}"
                playlist_info = await self.youtube.create_playlist(playlist_name, description)
                logger.info(f"Created new playlist: {playlist_name}")
            
            # Update playlist with selected tracks
            track_uris = [track.uri for track in selected_tracks]
            success, actual_track_count = await self.youtube.update_playlist_tracks(playlist_info.id, track_uris)
            
            if not success:
                logger.warning("Failed to update playlist tracks")
            
            # Get selection stats for freshness score
            selection_stats = self._get_selection_stats(selected_tracks, reference_tracks, usage_history)
            
            # Calculate freshness score - simpler approach
            # Count tracks that haven't been used recently (last 7 days)
            recent_cutoff = datetime.now() - timedelta(days=7)
            recently_used = 0
            
            for track in selected_tracks[:actual_track_count]:
                is_recently_used = False
                for date_str, date_data in usage_history.items():
                    try:
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                        if date_obj >= recent_cutoff:
                            if any(t.get('id') == track.id for t in date_data.get('tracks', [])):
                                recently_used += 1
                                is_recently_used = True
                                break
                    except (ValueError, KeyError):
                        continue
                    if is_recently_used:
                        break
            
            freshness_score = round(((actual_track_count - recently_used) / actual_track_count) * 100, 1) if actual_track_count > 0 else 100.0
            
            # Update usage history AFTER calculating freshness
            self._update_usage_history(selected_tracks, usage_history)
            
            return {
                'playlist_id': playlist_info.id,
                'playlist_name': playlist_info.name,
                'playlist_url': playlist_info.external_url,
                'tracks': selected_tracks[:actual_track_count] if success else selected_tracks,
                'freshness_score': freshness_score,
                'stats': {
                    'total_added': actual_track_count,
                    'unique_artists': selection_stats['unique_artists'],
                    'recently_used': recently_used,
                    'freshness_details': f"{actual_track_count - recently_used}/{actual_track_count} fresh tracks"
                }
            }
            
        except Exception as e:
            logger.error(f"Curation failed: {e}")
            raise Exception(f"Failed to generate curated YouTube Music playlist: {str(e)}")
    
    async def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics for curation history."""
        usage_history = self._load_usage_history()
        
        if not usage_history:
            return {
                'total_curations': 0,
                'unique_tracks_used': 0,
                'most_used_tracks': [],
                'recent_activity': []
            }
        
        # Calculate statistics
        all_tracks = []
        curation_dates = []
        
        for date, data in usage_history.items():
            curation_dates.append(date)
            all_tracks.extend(data.get('tracks', []))
        
        # Count track usage
        track_counts = Counter()
        for track in all_tracks:
            track_key = f"{track.get('name', 'Unknown')} - {track.get('artist', 'Unknown')}"
            track_counts[track_key] += 1
        
        return {
            'total_curations': len(usage_history),
            'unique_tracks_used': len(set(f"{t.get('name')}-{t.get('artist')}" for t in all_tracks)),
            'most_used_tracks': [{'track': track, 'count': count} for track, count in track_counts.most_common(10)],
            'recent_activity': sorted(curation_dates, reverse=True)[:10]
        }
    
    async def _smart_select_with_history(self, tracks: List[TrackInfo], history: Dict, target_size: int, reference_playlist_id: str = None) -> List[TrackInfo]:
        """Smart track selection considering usage history and variety."""
        if len(tracks) <= target_size:
            return tracks
        
        # Score each track based on history and variety factors
        scored_tracks = []
        
        for track in tracks:
            score = self._calculate_track_score(track, history)
            scored_tracks.append((track, score))
        
        # Sort by score (higher is better)
        scored_tracks.sort(key=lambda x: x[1], reverse=True)
        
        # Select tracks with artist diversity
        selected_tracks = self._ensure_artist_diversity(scored_tracks, target_size)
        
        # Add some randomness to avoid predictability
        if len(selected_tracks) >= target_size:
            # Shuffle the bottom 30% to add variety
            stable_count = int(len(selected_tracks) * 0.7)
            stable_tracks = selected_tracks[:stable_count]
            random_tracks = selected_tracks[stable_count:]
            random.shuffle(random_tracks)
            selected_tracks = stable_tracks + random_tracks
        
        # If we don't have enough tracks, discover new ones from the internet
        if len(selected_tracks) < target_size and reference_playlist_id:
            logger.info(f"🔍 Only found {len(selected_tracks)} tracks from reference. Discovering fresh tracks...")
            
            try:
                from .youtube_discovery import YouTubeDiscoveryEngine
                discovery_engine = YouTubeDiscoveryEngine(self.youtube)
                
                # Analyze the reference playlist to learn taste
                logger.info("🔍 Analyzing your YouTube reference playlist...")
                taste_profile = await discovery_engine.analyze_taste_profile(reference_playlist_id)
                
                logger.info(f"📊 Found artists: {', '.join(taste_profile['artists'][:5])}")
                logger.info(f"🎤 Found {len(taste_profile['artists'])} artists to search")
                
                # Discover fresh tracks based on analyzed taste
                needed = target_size - len(selected_tracks)
                logger.info(f"🎵 Discovering {needed} fresh tracks based on YOUR taste...")
                
                # Get existing track IDs to avoid duplicates
                existing_ids = {track.id for track in selected_tracks}
                existing_ids.update(track.id for track in tracks)
                
                # Discover tracks
                discovered = await discovery_engine.discover_tracks(reference_playlist_id, needed * 2)
                fresh_tracks = discovered.get('tracks', [])
                
                # Filter out duplicates and slow tracks
                slow_words = {'interview', 'interlude', 'ballad', 'acoustic', 'unplugged', 
                             'slow', 'soft', 'quiet', 'gentle', 'mellow', 'calm', 'peaceful'}
                
                truly_fresh = []
                for track in fresh_tracks:
                    track_name_lower = track.name.lower()
                    has_slow_words = any(word in track_name_lower for word in slow_words)
                    
                    if track.id not in existing_ids and not has_slow_words:
                        truly_fresh.append(track)
                        if len(truly_fresh) >= needed:
                            break
                
                logger.info(f"✨ Found {len(truly_fresh)} fresh tracks from YouTube discovery")
                selected_tracks.extend(truly_fresh)
                
            except Exception as e:
                logger.error(f"Failed to discover fresh tracks: {e}")
        
        return selected_tracks[:target_size]
    
    def _calculate_track_score(self, track: TrackInfo, history: Dict) -> float:
        """Calculate a score for track selection based on usage history."""
        base_score = 100.0
        
        # Check usage history by BOTH ID and name/artist (YouTube IDs can be unreliable)
        track_id = track.id
        track_name_lower = track.name.lower().strip()
        track_artist_lower = track.artist.lower().strip() if track.artist else ""
        
        usage_penalty = 0
        recency_penalty = 0
        times_used = 0
        
        # Calculate penalties based on recent usage
        current_date = datetime.now()
        
        for date_str, data in history.items():
            try:
                usage_date = datetime.strptime(date_str, '%Y-%m-%d')
                days_ago = (current_date - usage_date).days
                
                # Check if this track was used (by ID OR by name+artist match)
                used_tracks = data.get('tracks', [])
                track_used = False
                
                for used_track in used_tracks:
                    # Check by ID
                    if used_track.get('id') == track_id:
                        track_used = True
                        break
                    # Also check by name+artist (case insensitive)
                    used_name = used_track.get('name', '').lower().strip()
                    used_artist = used_track.get('artist', '').lower().strip()
                    if track_name_lower and used_name and track_name_lower == used_name:
                        if track_artist_lower == used_artist or not track_artist_lower or not used_artist:
                            track_used = True
                            break
                
                if track_used:
                    times_used += 1
                    # MASSIVE penalties for ANY recent use
                    if days_ago == 0:  # Used TODAY
                        recency_penalty += 1000  # Essentially block it
                    elif days_ago < 7:  # Used within a week
                        recency_penalty += 500
                    elif days_ago < 30:  # Used within a month
                        recency_penalty += 100
                    else:  # Used more than a month ago
                        recency_penalty += 25
                    
                    usage_penalty += 50 * times_used  # Multiply penalty by usage count
                    
            except ValueError:
                continue  # Skip invalid date entries
        
        # Apply penalties
        final_score = base_score - usage_penalty - recency_penalty
        
        # Log if track was heavily penalized
        if times_used > 0:
            logger.debug(f"Track '{track.name}' used {times_used} times, score: {final_score} (penalties: usage={usage_penalty}, recency={recency_penalty})")
        
        # Add small random factor for variety
        final_score += random.uniform(-5, 5)
        
        # Ensure minimum score
        final_score = max(final_score, 1.0)
        
        return final_score
    
    def _ensure_artist_diversity(self, scored_tracks: List[tuple], target_size: int) -> List[TrackInfo]:
        """Ensure artist diversity in the final selection."""
        selected = []
        artist_counts = Counter()
        max_per_artist = max(1, target_size // 10)  # Limit tracks per artist
        
        # First pass: select high-scoring tracks with artist limits
        for track, score in scored_tracks:
            artist = track.artist if track.artist else 'Unknown'
            
            if artist_counts[artist] < max_per_artist:
                selected.append(track)
                artist_counts[artist] += 1
                
                if len(selected) >= target_size:
                    break
        
        # Second pass: fill remaining slots if needed
        if len(selected) < target_size:
            remaining_tracks = [track for track, _ in scored_tracks if track not in selected]
            random.shuffle(remaining_tracks)
            
            for track in remaining_tracks:
                selected.append(track)
                if len(selected) >= target_size:
                    break
        
        return selected
    
    def _load_usage_history(self) -> Dict:
        """Load usage history from file."""
        try:
            if self.history_file.exists():
                with open(self.history_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load usage history: {e}")
        
        return {}
    
    def _update_usage_history(self, selected_tracks: List[TrackInfo], history: Dict) -> None:
        """Update usage history with selected tracks."""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Convert tracks to serializable format
            track_data = []
            for track in selected_tracks:
                track_data.append({
                    'id': track.id,
                    'name': track.name,
                    'artist': track.artist,
                    'album': track.album,
                    'uri': track.uri
                })
            
            # Update history
            history[today] = {
                'tracks': track_data,
                'track_count': len(selected_tracks),
                'timestamp': datetime.now().isoformat()
            }
            
            # Keep only last 60 days of history
            sorted_dates = sorted(history.keys(), reverse=True)
            if len(sorted_dates) > 60:
                for old_date in sorted_dates[60:]:
                    del history[old_date]
            
            # Save to file
            with open(self.history_file, 'w') as f:
                json.dump(history, f, indent=2)
                
            logger.info(f"Updated usage history for {today}")
            
        except Exception as e:
            logger.error(f"Failed to update usage history: {e}")
    
    def _get_selection_stats(self, selected_tracks: List[TrackInfo], all_tracks: List[TrackInfo], history: Dict) -> Dict[str, Any]:
        """Get statistics about the selection process."""
        # Artist diversity
        selected_artists = [track.artist for track in selected_tracks if track.artist]
        artist_counts = Counter(selected_artists)
        
        # History stats
        previously_used = 0
        for track in selected_tracks:
            for date_data in history.values():
                if any(t.get('id') == track.id for t in date_data.get('tracks', [])):
                    previously_used += 1
                    break
        
        return {
            'total_available': len(all_tracks),
            'selected': len(selected_tracks),
            'unique_artists': len(set(selected_artists)),
            'artist_distribution': dict(artist_counts.most_common(10)),
            'previously_used_count': previously_used,
            'freshness_ratio': round((len(selected_tracks) - previously_used) / len(selected_tracks) * 100, 1) if selected_tracks else 0
        } 