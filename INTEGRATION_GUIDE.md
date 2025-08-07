# 🛠️ Service Integration Guide

This guide provides detailed steps for integrating YouTube Music and Amazon Music into the Multi-Service Music Playlist Generator.

## 📋 **Prerequisites**

Before starting any integration:
1. ✅ **Working Spotify Integration** - Ensure the base system works
2. ✅ **Python 3.8+** and all dependencies installed
3. ✅ **Developer Account** for the target music service
4. ✅ **API Access** and credentials for the service

## 🎬 **YouTube Music Integration**

### **Phase 1: Setup Developer Access**

1. **Create Google Cloud Project**
   ```bash
   # Visit: https://console.developers.google.com/
   # 1. Create new project or select existing
   # 2. Enable YouTube Data API v3
   # 3. Create OAuth 2.0 credentials
   # 4. Download credentials.json
   ```

2. **Install YouTube Music Dependencies**
   ```bash
   pip3 install ytmusicapi google-auth google-auth-oauthlib google-auth-httplib2
   ```

3. **Update Requirements**
   ```bash
   # Add to requirements.txt:
   echo "ytmusicapi==1.3.2" >> requirements.txt
   echo "google-auth==2.17.3" >> requirements.txt
   echo "google-auth-oauthlib==1.0.0" >> requirements.txt
   echo "google-auth-httplib2==0.1.0" >> requirements.txt
   ```

### **Phase 2: Implement Service Classes**

1. **Create YouTube Music Service**
   ```python
   # File: services/youtube_service.py
   from typing import Dict, List, Any, Optional, Tuple
   from ytmusicapi import YTMusic
   from google.auth.transport.requests import Request
   from google_auth_oauthlib.flow import Flow
   
   from base_music_service import BaseMusicService, MusicServiceType, TrackInfo, PlaylistInfo, ArtistInfo
   
   class YouTubeMusicService(BaseMusicService):
       def __init__(self, config: Dict[str, Any]):
           super().__init__(config)
           self.ytmusic: Optional[YTMusic] = None
       
       @property
       def service_type(self) -> MusicServiceType:
           return MusicServiceType.YOUTUBE_MUSIC
       
       @property
       def service_name(self) -> str:
           return "YouTube Music"
       
       def validate_config(self) -> Tuple[bool, List[str]]:
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
           
           return len(errors) == 0, errors
       
       async def authenticate(self) -> bool:
           try:
               # YouTube Music OAuth flow
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
                   scopes=['https://www.googleapis.com/auth/youtube']
               )
               flow.redirect_uri = self.config['YOUTUBE_REDIRECT_URI']
               
               # Setup YTMusic with OAuth
               self.ytmusic = YTMusic()  # Will need proper OAuth setup
               self.authenticated = True
               return True
               
           except Exception as e:
               logger.error(f"YouTube Music authentication failed: {e}")
               return False
       
       async def get_current_user(self) -> Dict[str, Any]:
           # Implement user info retrieval
           pass
       
       async def get_playlist_tracks(self, playlist_id: str) -> List[TrackInfo]:
           if not self.authenticated or not self.ytmusic:
               raise Exception("Not authenticated with YouTube Music")
           
           tracks = []
           playlist = self.ytmusic.get_playlist(playlist_id)
           
           for track in playlist['tracks']:
               track_info = TrackInfo(
                   id=track['videoId'],
                   name=track['title'],
                   artist=', '.join([artist['name'] for artist in track['artists']]),
                   album=track.get('album', {}).get('name', 'Unknown'),
                   uri=f"https://music.youtube.com/watch?v={track['videoId']}",
                   external_url=f"https://music.youtube.com/watch?v={track['videoId']}",
                   duration_ms=track.get('duration_seconds', 0) * 1000,
                   explicit=False,  # YouTube Music doesn't expose this easily
                   popularity=None  # Not available
               )
               tracks.append(track_info)
           
           return tracks
       
       # Implement all other required methods...
       async def create_playlist(self, name: str, description: str = "", public: bool = True) -> PlaylistInfo:
           # Implementation here
           pass
       
       async def search_tracks(self, query: str, limit: int = 20) -> List[TrackInfo]:
           # Implementation here
           pass
       
       # ... other methods
   ```

2. **Create YouTube Discovery Engine**
   ```python
   # File: services/youtube_discovery.py
   from base_music_service import BaseDiscoveryEngine
   from services.youtube_service import YouTubeMusicService
   
   class YouTubeDiscoveryEngine(BaseDiscoveryEngine):
       def __init__(self, music_service: YouTubeMusicService):
           super().__init__(music_service)
           self.youtube = music_service
       
       async def discover_new_playlist(self, reference_playlist_id: str, target_size: int = 30) -> Dict[str, Any]:
           # Implement YouTube-specific discovery logic
           try:
               # 1. Analyze taste profile from reference playlist
               taste_profile = await self.analyze_taste_profile(reference_playlist_id)
               
               # 2. Use YouTube Music search to find new tracks
               discovered_tracks = await self._discover_tracks(taste_profile, target_size * 2)
               
               # 3. Filter and select best tracks
               selected_tracks = self._select_best_tracks(discovered_tracks, target_size)
               
               # 4. Create playlist
               result = await self._create_discovery_playlist(selected_tracks, taste_profile)
               
               return result
               
           except Exception as e:
               logger.error(f"YouTube discovery failed: {e}")
               raise
       
       async def analyze_taste_profile(self, reference_playlist_id: str) -> Dict[str, Any]:
           # Implement taste analysis for YouTube Music
           pass
       
       async def _discover_tracks(self, taste_profile: Dict[str, Any], target_count: int) -> List[TrackInfo]:
           # Use YouTube Music search APIs
           pass
   ```

3. **Create YouTube Curator**
   ```python
   # File: services/youtube_curator.py
   from base_music_service import BaseCurator
   from services.youtube_service import YouTubeMusicService
   
   class YouTubeCurator(BaseCurator):
       def __init__(self, music_service: YouTubeMusicService):
           super().__init__(music_service)
           self.youtube = music_service
       
       async def generate_curated_playlist(self, reference_playlist_id: str, target_size: int = 30) -> Dict[str, Any]:
           # Implement YouTube-specific curation logic
           pass
       
       async def get_usage_stats(self) -> Dict[str, Any]:
           # Implement usage statistics
           pass
   ```

### **Phase 3: Register YouTube Music Service**

1. **Update Service Type Enum**
   ```python
   # In base_music_service.py - already done!
   class MusicServiceType(Enum):
       SPOTIFY = "spotify"
       YOUTUBE_MUSIC = "youtube_music"  # ✅ Already added
       AMAZON_MUSIC = "amazon_music"
   ```

2. **Register in Main CLI**
   ```python
   # In main.py CLIContext._register_services()
   try:
       from services.youtube_service import YouTubeMusicService
       from services.youtube_discovery import YouTubeDiscoveryEngine
       from services.youtube_curator import YouTubeCurator
       
       self.service_manager.register_service(
           MusicServiceType.YOUTUBE_MUSIC,
           YouTubeMusicService,
           YouTubeDiscoveryEngine,
           YouTubeCurator
       )
   except ImportError:
       logger.info("YouTube Music service not yet implemented")  # Remove this line
   ```

3. **Update Service Manager Template**
   ```python
   # In service_manager.py create_service_config_template()
   # Already implemented! The template is ready.
   ```

### **Phase 4: Test Integration**

```bash
# Test the integration
python3 main.py status                      # Should show YouTube Music
python3 main.py setup youtube_music         # Create config template
# Edit ~/.multi_music_generator/youtube_music.env with your credentials
python3 main.py test youtube_music          # Test connection
python3 main.py discover --service youtube_music --size 5
```

## 🛒 **Amazon Music Integration**

### **Phase 1: Setup Developer Access**

1. **Create Amazon Developer Account**
   ```bash
   # Visit: https://developer.amazon.com/
   # 1. Sign up for developer account
   # 2. Create new app
   # 3. Request Amazon Music API access (requires approval)
   # 4. Get client credentials
   ```

2. **Install Amazon Music Dependencies**
   ```bash
   pip3 install boto3 requests-oauthlib
   ```

3. **Update Requirements**
   ```bash
   # Add to requirements.txt:
   echo "boto3==1.34.0" >> requirements.txt
   echo "requests-oauthlib==1.3.1" >> requirements.txt
   ```

### **Phase 2: Implement Amazon Music Service**

1. **Create Amazon Music Service**
   ```python
   # File: services/amazon_service.py
   import boto3
   from typing import Dict, List, Any, Optional, Tuple
   
   from base_music_service import BaseMusicService, MusicServiceType, TrackInfo, PlaylistInfo, ArtistInfo
   
   class AmazonMusicService(BaseMusicService):
       def __init__(self, config: Dict[str, Any]):
           super().__init__(config)
           self.client = None
       
       @property
       def service_type(self) -> MusicServiceType:
           return MusicServiceType.AMAZON_MUSIC
       
       @property
       def service_name(self) -> str:
           return "Amazon Music"
       
       def validate_config(self) -> Tuple[bool, List[str]]:
           errors = []
           required_keys = [
               'AMAZON_CLIENT_ID',
               'AMAZON_CLIENT_SECRET',
               'AMAZON_REDIRECT_URI',
               'REFERENCE_PLAYLIST_ID'
           ]
           
           for key in required_keys:
               if not self.config.get(key):
                   errors.append(f"Missing required configuration: {key}")
           
           return len(errors) == 0, errors
       
       async def authenticate(self) -> bool:
           try:
               # Amazon Music OAuth implementation
               # Note: Amazon Music API is restrictive and requires business approval
               self.authenticated = True
               return True
           except Exception as e:
               logger.error(f"Amazon Music authentication failed: {e}")
               return False
       
       # Implement all required methods...
   ```

2. **Create Amazon Discovery & Curator**
   ```python
   # File: services/amazon_discovery.py
   from base_music_service import BaseDiscoveryEngine
   from services.amazon_service import AmazonMusicService
   
   class AmazonDiscoveryEngine(BaseDiscoveryEngine):
       # Similar structure to YouTube implementation
       pass
   
   # File: services/amazon_curator.py  
   from base_music_service import BaseCurator
   from services.amazon_service import AmazonMusicService
   
   class AmazonCurator(BaseCurator):
       # Similar structure to YouTube implementation
       pass
   ```

### **Phase 3: Register Amazon Music**

```python
# In main.py CLIContext._register_services()
try:
    from services.amazon_service import AmazonMusicService
    from services.amazon_discovery import AmazonDiscoveryEngine
    from services.amazon_curator import AmazonCurator
    
    self.service_manager.register_service(
        MusicServiceType.AMAZON_MUSIC,
        AmazonMusicService,
        AmazonDiscoveryEngine,
        AmazonCurator
    )
except ImportError:
    logger.info("Amazon Music service not yet implemented")  # Remove this line
```

## 🧪 **Testing Your Integration**

### **Step-by-Step Testing**

1. **Test Service Registration**
   ```bash
   python3 main.py status
   # Should show your new service with ❌ Configuration: Invalid
   ```

2. **Test Configuration Template**
   ```bash
   python3 main.py setup your_service
   # Should create config template with instructions
   ```

3. **Test Configuration Validation**
   ```bash
   # After adding credentials to config file:
   python3 main.py status
   # Should show ✅ Configuration: Valid
   ```

4. **Test Authentication**
   ```bash
   python3 main.py test your_service
   # Should successfully connect and show user info
   ```

5. **Test Core Features**
   ```bash
   python3 main.py discover --service your_service --size 3
   python3 main.py curate --service your_service --size 5
   ```

## 🚨 **Common Integration Issues**

### **API Access Issues**
- **YouTube Music**: Requires OAuth setup, quota limitations
- **Amazon Music**: Very restrictive, requires business approval
- **Rate Limiting**: Implement proper throttling and retry logic

### **Authentication Problems**
```python
# Common OAuth flow pattern:
async def authenticate(self) -> bool:
    try:
        # 1. Setup OAuth flow
        # 2. Handle redirect and token exchange
        # 3. Store tokens securely
        # 4. Test API access
        return True
    except Exception as e:
        logger.error(f"Auth failed: {e}")
        return False
```

### **Data Mapping Issues**
```python
# Ensure consistent data mapping:
def _map_track_data(self, api_track) -> TrackInfo:
    return TrackInfo(
        id=self._safe_get(api_track, 'id'),
        name=self._safe_get(api_track, 'title', 'Unknown'),
        artist=self._extract_artists(api_track),
        album=self._safe_get(api_track, 'album', 'Unknown'),
        # ... map all fields safely
    )
```

## 📝 **Implementation Checklist**

### **For Each New Service:**

#### **✅ Phase 1: Setup**
- [ ] Create developer account
- [ ] Get API credentials
- [ ] Install dependencies
- [ ] Update requirements.txt

#### **✅ Phase 2: Core Implementation**
- [ ] Create `services/SERVICE_service.py`
- [ ] Implement `BaseMusicService` interface
- [ ] Add authentication logic
- [ ] Implement all required methods

#### **✅ Phase 3: Discovery & Curation**
- [ ] Create `services/SERVICE_discovery.py`
- [ ] Implement `BaseDiscoveryEngine` interface
- [ ] Create `services/SERVICE_curator.py`
- [ ] Implement `BaseCurator` interface

#### **✅ Phase 4: Integration**
- [ ] Register service in `main.py`
- [ ] Update service manager templates
- [ ] Add configuration validation
- [ ] Test all CLI commands

#### **✅ Phase 5: Testing**
- [ ] Test service registration
- [ ] Test configuration setup
- [ ] Test authentication
- [ ] Test discovery functionality
- [ ] Test curation functionality

## 💡 **Pro Tips**

1. **Start Simple**: Implement basic playlist operations first
2. **Copy Pattern**: Use Spotify implementation as a template
3. **Error Handling**: Add comprehensive error messages
4. **Rate Limiting**: Respect API quotas and add delays
5. **Caching**: Cache API responses when possible
6. **Testing**: Test with small playlists first

## 🎯 **API Documentation References**

- **YouTube Music**: [ytmusicapi docs](https://ytmusicapi.readthedocs.io/)
- **Amazon Music**: [Amazon Music API](https://developer.amazon.com/docs/amazon-music/)
- **Spotify**: [Spotify Web API](https://developer.spotify.com/documentation/web-api/) (reference)

---

**🚀 Ready to extend your music generator? Follow this guide step-by-step and you'll have multi-service support in no time!** 