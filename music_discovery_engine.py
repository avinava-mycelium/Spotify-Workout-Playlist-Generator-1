"""Music Discovery Engine - Find new tracks from similar artists and genres."""

import random
from datetime import datetime
from typing import Dict, List, Any, Set

from loguru import logger

from config import get_settings
from spotify_client import SpotifyClient


class MusicDiscoveryEngine:
    """Discover new music based on your taste profile using available Spotify APIs."""
    
    def __init__(self):
        """Initialize the discovery engine."""
        self.settings = get_settings()
        self.spotify_client = SpotifyClient(self.settings)
    
    def discover_new_playlist(self) -> Dict[str, Any]:
        """Discover a playlist of completely new tracks based on your taste."""
        try:
            logger.info("Starting music discovery process")
            
            # Step 1: Analyze your taste profile
            taste_profile = self._analyze_taste_profile()
            logger.info(f"Analyzed taste profile: {len(taste_profile['artists'])} artists, {len(taste_profile['genres'])} genres")
            
            # Step 2: Find related artists and new tracks
            new_tracks = self._discover_tracks(taste_profile)
            logger.info(f"Discovered {len(new_tracks)} potential new tracks")
            
            # Step 3: Filter out known tracks
            filtered_tracks = self._filter_unknown_tracks(new_tracks, taste_profile['known_track_ids'])
            logger.info(f"After filtering known tracks: {len(filtered_tracks)} truly new tracks")
            
            if not filtered_tracks:
                raise ValueError("No new tracks discovered. Try expanding your reference playlist or check back later.")
            
            # Step 4: Select best tracks for playlist
            selected_tracks = self._select_best_tracks(filtered_tracks)
            
            # Step 5: Create discovery playlist
            result = self._create_discovery_playlist(selected_tracks, taste_profile)
            
            logger.info(f"Successfully created discovery playlist with {len(selected_tracks)} new tracks")
            return result
            
        except Exception as e:
            logger.error(f"Failed to discover new music: {e}")
            raise
    
    def _analyze_taste_profile(self) -> Dict[str, Any]:
        """Analyze user's reference playlist to understand their taste."""
        # Get reference playlist
        reference_tracks = self.spotify_client.get_playlist_tracks(self.settings.reference_playlist_id)
        
        # Extract artists and track IDs
        artists = set()
        known_track_ids = set()
        
        for track in reference_tracks:
            known_track_ids.add(track['id'])
            for artist in track['artists']:
                artists.add(artist)
        
        # Get genres from artists (sample a subset to avoid rate limits)
        sample_artists = list(artists)[:20]  # Sample 20 artists
        genres = set()
        
        for artist_name in sample_artists:
            try:
                # Search for artist to get their ID
                search_result = self.spotify_client.client.search(
                    q=f'artist:"{artist_name}"',
                    type='artist',
                    limit=1
                )
                
                if search_result['artists']['items']:
                    artist_data = search_result['artists']['items'][0]
                    artist_genres = artist_data.get('genres', [])
                    genres.update(artist_genres)
                    
            except Exception as e:
                logger.warning(f"Failed to get genres for artist {artist_name}: {e}")
                continue
        
        return {
            'artists': list(artists),
            'genres': list(genres),
            'known_track_ids': known_track_ids,
            'reference_tracks': reference_tracks
        }
    
    def _discover_tracks(self, taste_profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Discover new tracks using multiple strategies."""
        discovered_tracks = []
        
        # Strategy 1: Search by genres
        discovered_tracks.extend(self._search_by_genres(taste_profile['genres']))
        
        # Strategy 2: Find related artists
        discovered_tracks.extend(self._find_related_artists_tracks(taste_profile['artists']))
        
        # Strategy 3: Search for workout-specific terms in similar genres
        discovered_tracks.extend(self._search_workout_genres())
        
        # Remove duplicates
        unique_tracks = {}
        for track in discovered_tracks:
            if track['id'] not in unique_tracks:
                unique_tracks[track['id']] = track
        
        return list(unique_tracks.values())
    
    def _search_by_genres(self, genres: List[str]) -> List[Dict[str, Any]]:
        """Search for tracks by genre."""
        tracks = []
        
        # Focus on rock/metal genres that are workout-friendly
        workout_genres = [
            'metal', 'rock', 'hard rock', 'alternative rock', 'nu metal',
            'metalcore', 'post-grunge', 'alternative metal', 'punk rock'
        ]
        
        # Find intersection of user's genres with workout genres
        relevant_genres = []
        for genre in genres:
            for workout_genre in workout_genres:
                if workout_genre in genre.lower() or genre.lower() in workout_genre:
                    relevant_genres.append(genre)
        
        # If no relevant genres found, use the workout genres directly
        if not relevant_genres:
            relevant_genres = workout_genres[:3]
        
        logger.info(f"Searching for tracks in genres: {relevant_genres}")
        
        for genre in relevant_genres[:5]:  # Limit to prevent too many API calls
            try:
                # Search for tracks in this genre
                search_result = self.spotify_client.client.search(
                    q=f'genre:"{genre}"',
                    type='track',
                    limit=20
                )
                
                for track in search_result['tracks']['items']:
                    tracks.append({
                        'id': track['id'],
                        'name': track['name'],
                        'artists': [artist['name'] for artist in track['artists']],
                        'uri': track['uri'],
                        'popularity': track.get('popularity', 0),
                        'discovery_method': f'genre:{genre}'
                    })
                    
            except Exception as e:
                logger.warning(f"Failed to search for genre {genre}: {e}")
                continue
        
        return tracks
    
    def _find_related_artists_tracks(self, favorite_artists: List[str]) -> List[Dict[str, Any]]:
        """Find tracks from artists related to user's favorites."""
        tracks = []
        
        # Sample some favorite artists to avoid rate limits
        sample_artists = random.sample(favorite_artists, min(10, len(favorite_artists)))
        
        for artist_name in sample_artists:
            try:
                # Find the artist
                search_result = self.spotify_client.client.search(
                    q=f'artist:"{artist_name}"',
                    type='artist',
                    limit=1
                )
                
                if not search_result['artists']['items']:
                    continue
                
                artist_id = search_result['artists']['items'][0]['id']
                
                # Get related artists
                related_artists = self.spotify_client.client.artist_related_artists(artist_id)
                
                # Get top tracks from related artists
                for related_artist in related_artists['artists'][:5]:  # Limit to 5 related artists
                    try:
                        top_tracks = self.spotify_client.client.artist_top_tracks(
                            related_artist['id'],
                            country='US'
                        )
                        
                        for track in top_tracks['tracks'][:3]:  # Top 3 tracks per artist
                            tracks.append({
                                'id': track['id'],
                                'name': track['name'],
                                'artists': [artist['name'] for artist in track['artists']],
                                'uri': track['uri'],
                                'popularity': track.get('popularity', 0),
                                'discovery_method': f'related_to:{artist_name}'
                            })
                            
                    except Exception as e:
                        logger.warning(f"Failed to get tracks for related artist {related_artist['name']}: {e}")
                        continue
                        
            except Exception as e:
                logger.warning(f"Failed to find related artists for {artist_name}: {e}")
                continue
        
        return tracks
    
    def _search_workout_genres(self) -> List[Dict[str, Any]]:
        """Search for workout-friendly tracks using specific terms."""
        tracks = []
        
        # Workout-specific search terms that tend to yield high-energy tracks
        workout_terms = [
            'workout metal', 'gym rock', 'heavy metal', 'alternative metal',
            'post-grunge', 'nu metal', 'metalcore', 'hard rock'
        ]
        
        for term in workout_terms[:3]:  # Limit searches
            try:
                search_result = self.spotify_client.client.search(
                    q=term,
                    type='track',
                    limit=15
                )
                
                for track in search_result['tracks']['items']:
                    tracks.append({
                        'id': track['id'],
                        'name': track['name'],
                        'artists': [artist['name'] for artist in track['artists']],
                        'uri': track['uri'],
                        'popularity': track.get('popularity', 0),
                        'discovery_method': f'search:{term}'
                    })
                    
            except Exception as e:
                logger.warning(f"Failed to search for term '{term}': {e}")
                continue
        
        return tracks
    
    def _filter_unknown_tracks(self, tracks: List[Dict[str, Any]], known_track_ids: Set[str]) -> List[Dict[str, Any]]:
        """Filter out tracks that are already known to the user."""
        return [track for track in tracks if track['id'] not in known_track_ids]
    
    def _select_best_tracks(self, tracks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Select the best tracks for the playlist."""
        # Sort by popularity (but not too popular - we want discoveries)
        # Sweet spot: popularity 30-70 (known but not mainstream)
        filtered_tracks = [
            track for track in tracks 
            if 20 <= track.get('popularity', 0) <= 75
        ]
        
        # If not enough in sweet spot, include others
        if len(filtered_tracks) < self.settings.playlist_size:
            other_tracks = [track for track in tracks if track not in filtered_tracks]
            filtered_tracks.extend(other_tracks)
        
        # Randomize and select
        random.shuffle(filtered_tracks)
        return filtered_tracks[:self.settings.playlist_size]
    
    def _create_discovery_playlist(self, tracks: List[Dict[str, Any]], taste_profile: Dict[str, Any]) -> Dict[str, Any]:
        """Create the discovery playlist."""
        today = datetime.now()
        playlist_name = f"Music Discovery - {today.strftime('%Y-%m-%d')}"
        
        # Check if playlist exists
        existing_id = self.spotify_client.find_playlist_by_name(playlist_name)
        if existing_id:
            playlist_id = existing_id
            logger.info(f"Found existing discovery playlist: {playlist_name}")
        else:
            description = f"New music discoveries based on your taste, generated on {today.strftime('%B %d, %Y')}. Featuring artists and genres similar to your favorites."
            playlist_id = self.spotify_client.create_playlist(playlist_name, description)
            logger.info(f"Created new discovery playlist: {playlist_name}")
        
        # Update playlist
        track_uris = [track['uri'] for track in tracks]
        self.spotify_client.update_playlist(playlist_id, track_uris)
        
        # Create discovery stats
        discovery_methods = {}
        for track in tracks:
            method = track.get('discovery_method', 'unknown')
            discovery_methods[method] = discovery_methods.get(method, 0) + 1
        
        return {
            'playlist_id': playlist_id,
            'playlist_name': playlist_name,
            'track_count': len(tracks),
            'tracks': tracks,
            'created_at': today.isoformat(),
            'spotify_url': f"https://open.spotify.com/playlist/{playlist_id}",
            'discovery_methods': discovery_methods,
            'taste_profile': {
                'genres': taste_profile['genres'][:10],  # Top 10 genres
                'favorite_artists_count': len(taste_profile['artists'])
            }
        }


def main():
    """Main function for CLI usage."""
    import click
    
    @click.command()
    def discover():
        """Discover new music based on your taste profile."""
        try:
            engine = MusicDiscoveryEngine()
            result = engine.discover_new_playlist()
            
            click.echo("🎉 New music discovered successfully!")
            click.echo(f"📝 Discovery Playlist: {result['playlist_name']}")
            click.echo(f"🎵 New Tracks: {result['track_count']}")
            click.echo(f"🔗 Spotify URL: {result['spotify_url']}")
            
            click.echo(f"\n🎯 Your Taste Profile:")
            click.echo(f"🎸 Favorite Genres: {', '.join(result['taste_profile']['genres'])}")
            click.echo(f"👥 Artists Analyzed: {result['taste_profile']['favorite_artists_count']}")
            
            click.echo(f"\n🔍 Discovery Methods Used:")
            for method, count in result['discovery_methods'].items():
                click.echo(f"  • {method}: {count} tracks")
            
            click.echo(f"\n🎵 Your new discoveries:")
            for i, track in enumerate(result['tracks'][:10], 1):
                artists = ', '.join(track['artists'])
                method = track.get('discovery_method', 'unknown')
                click.echo(f"  {i}. {track['name']} - {artists} ({method})")
            
            if len(result['tracks']) > 10:
                click.echo(f"  ... and {len(result['tracks']) - 10} more new tracks to explore!")
                
        except Exception as e:
            click.echo(f"❌ Discovery failed: {e}")
    
    discover()


if __name__ == '__main__':
    main() 