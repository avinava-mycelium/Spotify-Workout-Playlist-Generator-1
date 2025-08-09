"""YouTube Music service implementation."""

import os
import json
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

from ytmusicapi import YTMusic
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import googleapiclient.errors
from loguru import logger

from base_music_service import BaseMusicService, MusicServiceType, TrackInfo, PlaylistInfo, ArtistInfo


class YouTubeMusicService(BaseMusicService):
    """YouTube Music implementation of the music service interface."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize YouTube Music service."""
        super().__init__(config)
        self.ytmusic: Optional[YTMusic] = None
        self.youtube_api = None  # YouTube Data API v3 client
        self.credentials: Optional[Credentials] = None
        self.token_file = Path.cwd() / "youtube_token.json"
    
    @property
    def service_type(self) -> MusicServiceType:
        """Get the service type."""
        return MusicServiceType.YOUTUBE_MUSIC
    
    @property
    def service_name(self) -> str:
        """Get the human-readable service name."""
        return "YouTube Music"
    
    def validate_config(self) -> Tuple[bool, List[str]]:
        """Validate YouTube Music configuration."""
        errors = []
        
        required_keys = [
            'YOUTUBE_CLIENT_ID',
            'YOUTUBE_CLIENT_SECRET',
            'YOUTUBE_REDIRECT_URI',
            'REFERENCE_PLAYLIST_ID'
        ]
        
        for key in required_keys:
            if not self.config.get(key):
                errors.append(f"Missing required configuration: {key}")
            elif self.config.get(key) in ['your_client_id_here', 'your_client_secret_here', 'your_playlist_id_here']:
                errors.append(f"Please set a real value for {key}")
        
        # Validate redirect URI format
        redirect_uri = self.config.get('YOUTUBE_REDIRECT_URI', '')
        if redirect_uri and not (redirect_uri.startswith('http://') or redirect_uri.startswith('https://')):
            errors.append("YOUTUBE_REDIRECT_URI must be a valid HTTP/HTTPS URL")
        
        return len(errors) == 0, errors
    
    async def authenticate(self) -> bool:
        """Authenticate with YouTube Music."""
        try:
            # Allow HTTP for localhost development
            import os
            os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
            # Check if we have saved credentials
            if self.token_file.exists():
                logger.info("Loading saved YouTube Music credentials")
                with open(self.token_file, 'r') as f:
                    token_data = json.load(f)
                
                self.credentials = Credentials.from_authorized_user_info(token_data)
                
                # Refresh if expired
                if self.credentials.expired and self.credentials.refresh_token:
                    logger.info("Refreshing YouTube Music credentials")
                    self.credentials.refresh(Request())
                    self._save_credentials()
            
            # If no valid credentials, start OAuth flow
            if not self.credentials or not self.credentials.valid:
                logger.info("Starting YouTube Music OAuth flow")
                await self._oauth_flow()
            
            # Initialize both YTMusic and YouTube Data API
            if self.credentials and self.credentials.valid:
                try:
                    # Initialize YouTube Data API v3 with OAuth credentials
                    self.youtube_api = build('youtube', 'v3', credentials=self.credentials)
                    
                    # Initialize YTMusic
                    # If headers file is provided, use it to enable access to likes/library
                    headers_file = self.config.get('YTMUSIC_HEADERS_FILE') or self.config.get('YT_HEADERS_FILE')
                    try:
                        if headers_file and Path(headers_file).exists():
                            logger.info(f"Initializing YTMusic with headers file: {headers_file}")
                            self.ytmusic = YTMusic(headers_file)
                        else:
                            # Fallback to limited mode
                            self.ytmusic = YTMusic()
                    except Exception as e_init:
                        logger.warning(f"YTMusic headers init failed, using limited mode: {e_init}")
                        self.ytmusic = YTMusic()
                    
                    self.authenticated = True
                    logger.info("Successfully authenticated with YouTube Music")
                    return True
                except Exception as e:
                    logger.warning(f"YouTube API initialization failed: {e}")
                    # Fall back to basic functionality
                    try:
                        self.ytmusic = YTMusic()
                        self.authenticated = True
                        logger.info("YouTube Music initialized with limited functionality")
                        return True
                    except Exception as e2:
                        logger.error(f"Failed to initialize YouTube Music: {e2}")
                        return False
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to authenticate with YouTube Music: {e}")
            return False
    
    async def _oauth_flow(self) -> None:
        """Perform OAuth 2.0 flow for YouTube Music."""
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.config['YOUTUBE_CLIENT_ID'],
                    "client_secret": self.config['YOUTUBE_CLIENT_SECRET'],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.config['YOUTUBE_REDIRECT_URI']]
                }
            },
            scopes=[
                'https://www.googleapis.com/auth/youtube',
                'https://www.googleapis.com/auth/youtube.readonly',
                'https://www.googleapis.com/auth/youtubepartner'
            ]
        )
        flow.redirect_uri = self.config['YOUTUBE_REDIRECT_URI']
        
        # Generate authorization URL
        auth_url, _ = flow.authorization_url(prompt='consent')
        
        print(f"\n🔐 YouTube Music Authentication Required!")
        print(f"🌐 Please visit this URL to authorize the application:")
        print(f"🔗 {auth_url}")
        print(f"\n📋 After authorization, copy the full redirect URL from your browser")
        print(f"    (it should start with {self.config['YOUTUBE_REDIRECT_URI']})")
        
        # Get authorization code from user
        redirect_response = input("\n✏️  Paste the full redirect URL here: ").strip()
        
        # Complete the flow
        flow.fetch_token(authorization_response=redirect_response)
        self.credentials = flow.credentials
        
        # Save credentials
        self._save_credentials()
    
    async def _setup_browser_auth(self) -> bool:
        """Setup YTMusic with browser-based authentication."""
        try:
            print(f"\n🎵 YouTube Music Browser Authentication")
            print(f"📱 We need to set up browser-based authentication for YouTube Music")
            print(f"🔗 Please go to: https://music.youtube.com/")
            print(f"🍪 Open browser developer tools (F12) and go to Network tab")
            print(f"📝 Look for any request and copy the 'Cookie' header")
            
            # For now, we'll try without authentication to test basic functionality
            self.ytmusic = YTMusic()
            self.authenticated = True
            logger.info("YouTube Music initialized without authentication (limited functionality)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup YouTube Music: {e}")
            return False
    
    def _save_credentials(self) -> None:
        """Save OAuth credentials to file."""
        if self.credentials:
            with open(self.token_file, 'w') as f:
                json.dump({
                    'token': self.credentials.token,
                    'refresh_token': self.credentials.refresh_token,
                    'token_uri': self.credentials.token_uri,
                    'client_id': self.credentials.client_id,
                    'client_secret': self.credentials.client_secret,
                    'scopes': self.credentials.scopes
                }, f)
    
    async def get_current_user(self) -> Dict[str, Any]:
        """Get current authenticated user information."""
        if not self.authenticated:
            raise Exception("Not authenticated with YouTube Music")
        
        # YouTube Music API doesn't have a direct user info endpoint
        # Return basic info
        return {
            'id': 'youtube_user',
            'name': 'YouTube Music User',
            'followers': 0,
            'country': 'Unknown',
            'external_url': 'https://music.youtube.com'
        }
    
    async def get_playlist_tracks(self, playlist_id: str) -> List[TrackInfo]:
        """Get all tracks from a YouTube Music playlist."""
        if not self.authenticated or not self.ytmusic:
            raise Exception("Not authenticated with YouTube Music")
        
        tracks = []
        try:
            # Get playlist details
            playlist = self.ytmusic.get_playlist(playlist_id, limit=None)
            
            for track in playlist.get('tracks', []):
                if track and track.get('videoId'):
                    # Extract artist names
                    artists = []
                    if track.get('artists'):
                        artists = [artist['name'] for artist in track['artists'] if artist.get('name')]
                    
                    # Extract album name
                    album = 'Unknown'
                    if track.get('album') and track['album'].get('name'):
                        album = track['album']['name']
                    
                    track_info = TrackInfo(
                        id=track['videoId'],
                        name=track.get('title', 'Unknown'),
                        artist=', '.join(artists) if artists else 'Unknown Artist',
                        album=album,
                        uri=f"https://music.youtube.com/watch?v={track['videoId']}",
                        external_url=f"https://music.youtube.com/watch?v={track['videoId']}",
                        duration_ms=self._parse_duration(track.get('duration', '0:00')) * 1000,
                        explicit=False,  # YouTube Music doesn't expose explicit flag easily
                        popularity=None  # Not available in YouTube Music API
                    )
                    tracks.append(track_info)
            
            logger.info(f"Retrieved {len(tracks)} tracks from YouTube Music playlist {playlist_id}")
            return tracks
            
        except Exception as e:
            logger.error(f"Failed to get playlist tracks: {e}")
            raise Exception(f"Could not retrieve playlist {playlist_id}: {str(e)}")
    
    def _parse_duration(self, duration_str: str) -> int:
        """Parse YouTube duration string to seconds."""
        try:
            if ':' not in duration_str:
                return 0
            
            parts = duration_str.split(':')
            if len(parts) == 2:  # MM:SS
                return int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:  # HH:MM:SS
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            else:
                return 0
        except:
            return 0
    
    async def create_playlist(self, name: str, description: str = "", public: bool = True) -> PlaylistInfo:
        """Create a new YouTube Music playlist."""
        if not self.authenticated or not self.youtube_api:
            raise Exception("Not authenticated with YouTube Music")
        
        try:
            # Create playlist using YouTube Data API v3
            request = self.youtube_api.playlists().insert(
                part="snippet,status",
                body={
                    "snippet": {
                        "title": name,
                        "description": description
                    },
                    "status": {
                        "privacyStatus": "public" if public else "private"
                    }
                }
            )
            response = request.execute()
            playlist_id = response['id']
            
            playlist_info = PlaylistInfo(
                id=playlist_id,
                name=name,
                description=description,
                track_count=0,
                external_url=f"https://music.youtube.com/playlist?list={playlist_id}",
                public=public
            )
            
            logger.info(f"Created YouTube Music playlist: {name} ({playlist_id})")
            return playlist_info
            
        except Exception as e:
            logger.error(f"Failed to create playlist: {e}")
            raise Exception(f"Could not create playlist '{name}': {str(e)}")
    
    async def update_playlist_tracks(self, playlist_id: str, track_uris: List[str]) -> tuple[bool, int]:
        """Update YouTube Music playlist with new tracks."""
        if not self.authenticated or not self.youtube_api:
            raise Exception("Not authenticated with YouTube Music")
        
        try:
            # Extract video IDs from URIs
            video_ids = []
            for uri in track_uris:
                if 'watch?v=' in uri:
                    video_id = uri.split('watch?v=')[1].split('&')[0]
                    video_ids.append(video_id)
                elif uri.startswith('http'):
                    # Skip URIs we can't parse
                    continue
                else:
                    # Assume it's already a video ID
                    video_ids.append(uri)
            
            if not video_ids:
                logger.warning("No valid video IDs found in track URIs")
                return False
            
            # First, clear existing playlist items (skip if new playlist)
            try:
                # Get current playlist items
                request = self.youtube_api.playlistItems().list(
                    part="id",
                    playlistId=playlist_id,
                    maxResults=50
                )
                response = request.execute()
                
                # Delete existing items
                for item in response.get('items', []):
                    self.youtube_api.playlistItems().delete(id=item['id']).execute()
                    
            except googleapiclient.errors.HttpError as e:
                if e.resp.status == 404:
                    logger.info("New playlist - skipping clear step")
                else:
                    logger.warning(f"Could not clear playlist: {e}")
            except Exception as e:
                logger.warning(f"Could not clear playlist: {e}")
            
            # Add new tracks using YouTube Data API v3
            successful_adds = 0
            for video_id in video_ids:
                try:
                    request = self.youtube_api.playlistItems().insert(
                        part="snippet",
                        body={
                            "snippet": {
                                "playlistId": playlist_id,
                                "resourceId": {
                                    "kind": "youtube#video",
                                    "videoId": video_id
                                }
                            }
                        }
                    )
                    request.execute()
                    successful_adds += 1
                except googleapiclient.errors.HttpError as e:
                    if e.resp.status == 409:
                        logger.debug(f"Skipping unavailable video {video_id} (region restricted or private)")
                    elif e.resp.status == 404:
                        logger.debug(f"Skipping non-existent video {video_id} (not found)")
                    else:
                        logger.warning(f"Failed to add video {video_id}: {e}")
                    continue
                except Exception as e:
                    logger.warning(f"Failed to add video {video_id}: {e}")
                    continue
            
            logger.info(f"Updated YouTube Music playlist {playlist_id} with {successful_adds}/{len(video_ids)} tracks")
            # Return tuple: (success_boolean, successful_count)
            return (successful_adds > 0, successful_adds)
            
        except Exception as e:
            logger.error(f"Failed to update playlist {playlist_id}: {e}")
            return (False, 0)
    
    async def find_playlist_by_name(self, name: str) -> Optional[PlaylistInfo]:
        """Find a YouTube Music playlist by name."""
        if not self.authenticated or not self.youtube_api:
            raise Exception("Not authenticated with YouTube Music")
        
        try:
            # Get user's playlists using YouTube Data API v3
            request = self.youtube_api.playlists().list(
                part="snippet,status,contentDetails",
                mine=True,
                maxResults=50
            )
            response = request.execute()
            
            for playlist in response.get('items', []):
                if playlist['snippet']['title'] == name:
                    return PlaylistInfo(
                        id=playlist['id'],
                        name=playlist['snippet']['title'],
                        description=playlist['snippet'].get('description', ''),
                        track_count=playlist['contentDetails'].get('itemCount', 0),
                        external_url=f"https://music.youtube.com/playlist?list={playlist['id']}",
                        public=playlist['status']['privacyStatus'] == 'public'
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to search playlists: {e}")
            return None
    
    async def search_tracks(self, query: str, limit: int = 20) -> List[TrackInfo]:
        """Search for tracks on YouTube Music."""
        if not self.authenticated or not self.ytmusic:
            raise Exception("Not authenticated with YouTube Music")
        
        try:
            # Search for songs
            results = self.ytmusic.search(query, filter='songs', limit=limit)
            tracks = []
            
            for result in results:
                if result.get('videoId'):
                    # Extract artist names
                    artists = []
                    if result.get('artists'):
                        artists = [artist['name'] for artist in result['artists'] if artist.get('name')]
                    
                    # Extract album name
                    album = 'Unknown'
                    if result.get('album') and result['album'].get('name'):
                        album = result['album']['name']
                    
                    track_info = TrackInfo(
                        id=result['videoId'],
                        name=result.get('title', 'Unknown'),
                        artist=', '.join(artists) if artists else 'Unknown Artist',
                        album=album,
                        uri=f"https://music.youtube.com/watch?v={result['videoId']}",
                        external_url=f"https://music.youtube.com/watch?v={result['videoId']}",
                        duration_ms=self._parse_duration(result.get('duration', '0:00')) * 1000,
                        explicit=False,  # Not easily available
                        popularity=None  # Not available
                    )
                    tracks.append(track_info)
            
            return tracks
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    async def search_recent_music(self, query: str, limit: int = 20, days: int = 365) -> List[TrackInfo]:
        """Search YouTube for recent music videos by publish date using Data API.

        This uses order=date and publishedAfter to bias toward fresh uploads.
        """
        if not self.authenticated or not self.youtube_api:
            raise Exception("Not authenticated with YouTube Music")

        try:
            from datetime import datetime, timedelta, timezone
            published_after = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            request = self.youtube_api.search().list(
                part="snippet",
                q=query,
                maxResults=min(limit, 50),
                type="video",
                order="date",
                publishedAfter=published_after,
                videoCategoryId="10"  # Music
            )
            response = request.execute()

            tracks: List[TrackInfo] = []
            for item in response.get('items', []):
                video_id = item['id'].get('videoId')
                snippet = item.get('snippet', {})
                title = snippet.get('title', 'Unknown')
                channel = snippet.get('channelTitle', 'Unknown Artist')
                if not video_id:
                    continue
                tracks.append(TrackInfo(
                    id=video_id,
                    name=title,
                    artist=channel,
                    album='Unknown',
                    uri=f"https://music.youtube.com/watch?v={video_id}",
                    external_url=f"https://www.youtube.com/watch?v={video_id}",
                    duration_ms=0,
                    explicit=False,
                    popularity=None
                ))

            return tracks
        except Exception as e:
            logger.error(f"Recent music search failed: {e}")
            return []
    
    async def get_artist_info(self, artist_id: str) -> ArtistInfo:
        """Get detailed YouTube Music artist information."""
        if not self.authenticated or not self.ytmusic:
            raise Exception("Not authenticated with YouTube Music")
        
        try:
            artist = self.ytmusic.get_artist(artist_id)
            
            return ArtistInfo(
                id=artist_id,
                name=artist.get('name', 'Unknown Artist'),
                genres=[],  # YouTube Music doesn't provide genre info easily
                popularity=None,  # Not available
                external_url=f"https://music.youtube.com/channel/{artist_id}"
            )
            
        except Exception as e:
            logger.error(f"Failed to get artist info: {e}")
            # Return basic info
            return ArtistInfo(
                id=artist_id,
                name='Unknown Artist',
                genres=[],
                popularity=None,
                external_url=f"https://music.youtube.com/channel/{artist_id}"
            )
    
    async def get_related_artists(self, artist_id: str) -> List[ArtistInfo]:
        """Get artists related to the given YouTube Music artist."""
        # YouTube Music API doesn't have a direct related artists endpoint
        # Return empty list for now
        return []
    
    async def get_artist_top_tracks(self, artist_id: str, limit: int = 10) -> List[TrackInfo]:
        """Get top tracks for a YouTube Music artist."""
        if not self.authenticated or not self.ytmusic:
            raise Exception("Not authenticated with YouTube Music")
        
        try:
            artist = self.ytmusic.get_artist(artist_id)
            songs = artist.get('songs', {}).get('results', [])
            
            tracks = []
            for song in songs[:limit]:
                if song.get('videoId'):
                    track_info = TrackInfo(
                        id=song['videoId'],
                        name=song.get('title', 'Unknown'),
                        artist=artist.get('name', 'Unknown Artist'),
                        album=song.get('album', {}).get('name', 'Unknown') if song.get('album') else 'Unknown',
                        uri=f"https://music.youtube.com/watch?v={song['videoId']}",
                        external_url=f"https://music.youtube.com/watch?v={song['videoId']}",
                        duration_ms=self._parse_duration(song.get('duration', '0:00')) * 1000,
                        explicit=False,
                        popularity=None
                    )
                    tracks.append(track_info)
            
            return tracks
            
        except Exception as e:
            logger.error(f"Failed to get artist top tracks: {e}")
            return []
    
    async def get_user_saved_tracks(self, limit: int = 50) -> List[TrackInfo]:
        """Get user's liked tracks from YouTube Music."""
        if not self.authenticated or not self.ytmusic:
            raise Exception("Not authenticated with YouTube Music")
        
        try:
            # Get liked songs playlist
            liked_songs = self.ytmusic.get_liked_songs(limit=limit)
            tracks = []
            
            for track in liked_songs.get('tracks', []):
                if track.get('videoId'):
                    artists = []
                    if track.get('artists'):
                        artists = [artist['name'] for artist in track['artists'] if artist.get('name')]
                    
                    track_info = TrackInfo(
                        id=track['videoId'],
                        name=track.get('title', 'Unknown'),
                        artist=', '.join(artists) if artists else 'Unknown Artist',
                        album=track.get('album', {}).get('name', 'Unknown') if track.get('album') else 'Unknown',
                        uri=f"https://music.youtube.com/watch?v={track['videoId']}",
                        external_url=f"https://music.youtube.com/watch?v={track['videoId']}",
                        duration_ms=self._parse_duration(track.get('duration', '0:00')) * 1000,
                        explicit=False,
                        popularity=None
                    )
                    tracks.append(track_info)
            
            return tracks
            
        except Exception as e:
            logger.error(f"Failed to get user saved tracks: {e}")
            return [] 