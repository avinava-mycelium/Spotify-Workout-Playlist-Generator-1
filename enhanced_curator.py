"""Enhanced playlist curator with history tracking to minimize repetition."""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any

from loguru import logger

from config import get_settings
from spotify_client import SpotifyClient


class EnhancedCurator:
    """Enhanced playlist curator with smart history tracking and variety optimization."""
    
    def __init__(self):
        """Initialize the enhanced curator."""
        self.settings = get_settings()
        self.spotify_client = SpotifyClient(self.settings)
        self.history_file = Path("playlist_history.json")
    
    def generate_workout_playlist(self) -> Dict[str, Any]:
        """Generate a workout playlist with maximum variety and minimal repetition."""
        try:
            logger.info("Generating workout playlist with enhanced variety algorithms")
            
            # Get reference playlist tracks
            reference_tracks = self.spotify_client.get_playlist_tracks(self.settings.reference_playlist_id)
            logger.info(f"Reference playlist has {len(reference_tracks)} tracks")
            
            if not reference_tracks:
                raise ValueError("Reference playlist is empty")
            
            # Load usage history
            usage_history = self._load_usage_history()
            
            # Smart selection with variety optimization
            selected_tracks = self._smart_select_with_history(reference_tracks, usage_history)
            
            # Update usage history
            self._update_usage_history(selected_tracks, usage_history)
            
            logger.info(f"Selected {len(selected_tracks)} tracks with optimized variety")
            
            # Create playlist
            today = datetime.now()
            playlist_name = f"{self.settings.target_playlist_name} - {today.strftime('%Y-%m-%d')}"
            
            # Check if playlist exists
            existing_id = self.spotify_client.find_playlist_by_name(playlist_name)
            if existing_id:
                playlist_id = existing_id
                logger.info(f"Found existing playlist: {playlist_name}")
            else:
                description = f"Daily workout playlist with maximum variety, curated on {today.strftime('%B %d, %Y')}."
                playlist_id = self.spotify_client.create_playlist(playlist_name, description)
                logger.info(f"Created new playlist: {playlist_name}")
            
            # Update playlist
            track_uris = [track['uri'] for track in selected_tracks]
            self.spotify_client.update_playlist(playlist_id, track_uris)
            
            # Also update main playlist
            main_playlist_id = self.spotify_client.find_playlist_by_name(self.settings.target_playlist_name)
            if not main_playlist_id:
                main_description = "Your daily workout playlist, enhanced with smart variety algorithms."
                main_playlist_id = self.spotify_client.create_playlist(self.settings.target_playlist_name, main_description)
            
            self.spotify_client.update_playlist(main_playlist_id, track_uris)
            
            # Calculate freshness stats
            stats = self._calculate_freshness_stats(selected_tracks, usage_history)
            
            result = {
                'playlist_id': playlist_id,
                'playlist_name': playlist_name,
                'main_playlist_id': main_playlist_id,
                'track_count': len(selected_tracks),
                'tracks': selected_tracks,
                'created_at': datetime.now().isoformat(),
                'spotify_url': f"https://open.spotify.com/playlist/{playlist_id}",
                'main_spotify_url': f"https://open.spotify.com/playlist/{main_playlist_id}",
                'curation_method': 'Enhanced variety with history tracking',
                'freshness_stats': stats
            }
            
            logger.info(f"Successfully created playlist with {len(selected_tracks)} tracks (Freshness: {stats['freshness_score']:.1%})")
            return result
            
        except Exception as e:
            logger.error(f"Failed to generate playlist: {e}")
            raise
    
    def _smart_select_with_history(self, reference_tracks: List[Dict[str, Any]], usage_history: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Smart selection with history tracking to maximize variety."""
        
        target_size = min(self.settings.playlist_size, len(reference_tracks))
        
        # Score tracks based on usage recency and frequency
        track_scores = {}
        current_time = datetime.now()
        
        for track in reference_tracks:
            track_id = track['id']
            
            # Base score starts at 1.0
            score = 1.0
            
            if track_id in usage_history['tracks']:
                track_history = usage_history['tracks'][track_id]
                
                # Reduce score based on usage frequency (more used = lower score)
                usage_count = track_history['count']
                score *= (1.0 / (1.0 + usage_count * 0.3))  # Diminishing returns
                
                # Boost score based on time since last use (older = higher score)
                if track_history['last_used']:
                    last_used = datetime.fromisoformat(track_history['last_used'])
                    days_since = (current_time - last_used).days
                    
                    # Boost tracks not used in the last 7 days
                    if days_since >= 7:
                        score *= 1.5
                    elif days_since >= 3:
                        score *= 1.2
                    elif days_since == 0:  # Used today
                        score *= 0.1  # Heavy penalty
                    elif days_since <= 2:  # Used recently
                        score *= 0.5
            else:
                # Never used tracks get a bonus
                score *= 1.8
            
            track_scores[track_id] = score
        
        # Sort tracks by score (higher is better)
        sorted_tracks = sorted(reference_tracks, key=lambda t: track_scores[t['id']], reverse=True)
        
        # Select tracks with artist variety
        selected_tracks = []
        used_artists = set()
        
        # First pass: Select highest scoring tracks with unique artists
        for track in sorted_tracks:
            if len(selected_tracks) >= target_size:
                break
                
            main_artist = track['artists'][0] if track['artists'] else 'Unknown'
            if main_artist not in used_artists:
                selected_tracks.append(track)
                used_artists.add(main_artist)
        
        # Second pass: Fill remaining slots with best available tracks
        for track in sorted_tracks:
            if len(selected_tracks) >= target_size:
                break
            if track not in selected_tracks:
                selected_tracks.append(track)
        
        # Shuffle for listening variety
        random.shuffle(selected_tracks)
        
        return selected_tracks[:target_size]
    
    def _load_usage_history(self) -> Dict[str, Any]:
        """Load track usage history from file."""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load history file: {e}")
        
        # Return default history structure
        return {
            'tracks': {},  # track_id -> {count, last_used, first_used}
            'playlists': [],  # list of playlist creation dates
            'created_at': datetime.now().isoformat()
        }
    
    def _update_usage_history(self, selected_tracks: List[Dict[str, Any]], usage_history: Dict[str, Any]) -> None:
        """Update track usage history."""
        current_time = datetime.now().isoformat()
        
        # Update track usage
        for track in selected_tracks:
            track_id = track['id']
            if track_id not in usage_history['tracks']:
                usage_history['tracks'][track_id] = {
                    'count': 0,
                    'last_used': None,
                    'first_used': current_time,
                    'name': track['name'],
                    'artists': track['artists']
                }
            
            usage_history['tracks'][track_id]['count'] += 1
            usage_history['tracks'][track_id]['last_used'] = current_time
        
        # Record playlist creation
        usage_history['playlists'].append({
            'date': current_time,
            'track_count': len(selected_tracks),
            'track_ids': [t['id'] for t in selected_tracks]
        })
        
        # Clean old history (keep last 90 days)
        cutoff_date = datetime.now() - timedelta(days=90)
        usage_history['playlists'] = [
            p for p in usage_history['playlists']
            if datetime.fromisoformat(p['date']) > cutoff_date
        ]
        
        # Save updated history
        try:
            with open(self.history_file, 'w') as f:
                json.dump(usage_history, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save history file: {e}")
    
    def _calculate_freshness_stats(self, selected_tracks: List[Dict[str, Any]], usage_history: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate freshness statistics for the playlist."""
        never_used = 0
        rarely_used = 0  # Used 1-2 times
        frequently_used = 0  # Used 3+ times
        
        for track in selected_tracks:
            track_id = track['id']
            if track_id not in usage_history['tracks']:
                never_used += 1
            else:
                count = usage_history['tracks'][track_id]['count']
                if count <= 2:
                    rarely_used += 1
                else:
                    frequently_used += 1
        
        total_tracks = len(selected_tracks)
        freshness_score = (never_used + rarely_used * 0.7) / total_tracks if total_tracks > 0 else 0
        
        return {
            'freshness_score': freshness_score,
            'never_used': never_used,
            'rarely_used': rarely_used,
            'frequently_used': frequently_used,
            'total_tracks': total_tracks
        }
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get detailed usage statistics."""
        usage_history = self._load_usage_history()
        
        if not usage_history['tracks']:
            return {'message': 'No usage history available yet'}
        
        track_counts = [data['count'] for data in usage_history['tracks'].values()]
        
        return {
            'total_unique_tracks_used': len(usage_history['tracks']),
            'total_playlists_created': len(usage_history['playlists']),
            'average_track_usage': sum(track_counts) / len(track_counts),
            'most_used_tracks': sorted(
                [
                    {
                        'name': data['name'],
                        'artists': data['artists'],
                        'count': data['count']
                    }
                    for data in usage_history['tracks'].values()
                ],
                key=lambda x: x['count'],
                reverse=True
            )[:10],
            'least_used_tracks': [
                {
                    'name': data['name'],
                    'artists': data['artists'],
                    'count': data['count']
                }
                for data in usage_history['tracks'].values()
                if data['count'] == 1
            ]
        }


def main():
    """Main function for CLI usage."""
    import click
    
    @click.group()
    def cli():
        """Enhanced Workout Playlist Curator with smart variety algorithms."""
        pass
    
    @cli.command()
    def generate():
        """Generate a new workout playlist with maximum variety."""
        try:
            curator = EnhancedCurator()
            result = curator.generate_workout_playlist()
            
            click.echo("🎉 Enhanced workout playlist generated successfully!")
            click.echo(f"📝 Playlist: {result['playlist_name']}")
            click.echo(f"🎵 Tracks: {result['track_count']}")
            click.echo(f"🔗 Spotify URL: {result['spotify_url']}")
            click.echo(f"🔗 Main Playlist: {result['main_spotify_url']}")
            click.echo(f"🧠 Method: {result['curation_method']}")
            
            stats = result['freshness_stats']
            click.echo(f"\n📊 Freshness Score: {stats['freshness_score']:.1%}")
            click.echo(f"🆕 Never used: {stats['never_used']} tracks")
            click.echo(f"🔄 Rarely used: {stats['rarely_used']} tracks")
            click.echo(f"♻️  Frequently used: {stats['frequently_used']} tracks")
            
            click.echo(f"\n🎵 Your enhanced workout mix:")
            for i, track in enumerate(result['tracks'][:8], 1):
                artists = ', '.join(track['artists'])
                click.echo(f"  {i}. {track['name']} - {artists}")
            
            if len(result['tracks']) > 8:
                click.echo(f"  ... and {len(result['tracks']) - 8} more tracks")
                
        except Exception as e:
            click.echo(f"❌ Failed to generate playlist: {e}")
    
    @cli.command()
    def stats():
        """Show usage statistics."""
        try:
            curator = EnhancedCurator()
            stats = curator.get_usage_stats()
            
            if 'message' in stats:
                click.echo(stats['message'])
                return
            
            click.echo("📊 Usage Statistics:")
            click.echo(f"🎵 Total unique tracks used: {stats['total_unique_tracks_used']}")
            click.echo(f"📝 Total playlists created: {stats['total_playlists_created']}")
            click.echo(f"📈 Average track usage: {stats['average_track_usage']:.1f}")
            
            if stats['most_used_tracks']:
                click.echo(f"\n🔥 Most used tracks:")
                for i, track in enumerate(stats['most_used_tracks'][:5], 1):
                    artists = ', '.join(track['artists'])
                    click.echo(f"  {i}. {track['name']} - {artists} ({track['count']} times)")
            
            if stats['least_used_tracks']:
                click.echo(f"\n🆕 Fresh tracks (used only once): {len(stats['least_used_tracks'])}")
                
        except Exception as e:
            click.echo(f"❌ Failed to get stats: {e}")
    
    cli()


if __name__ == '__main__':
    main() 