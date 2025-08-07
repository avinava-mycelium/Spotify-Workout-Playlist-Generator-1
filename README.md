# 🎵 Multi-Service Music Playlist Generator

A powerful, modular music discovery and playlist curation tool that works across multiple music streaming services. Discover new music and create smart playlists with advanced algorithms that bypass API restrictions and work with standard developer accounts.

## 🌟 **Currently Supported Services**
- ✅ **Spotify** - Fully implemented with Discovery & Curation
- 🔧 **YouTube Music** - Ready for implementation
- 🔧 **Amazon Music** - Ready for implementation

## 🎯 **Key Features**

### 🔍 **Music Discovery Engine**
- **Discovers completely NEW tracks** you've never heard before
- **Analyzes your taste profile** from your reference playlist
- **Multi-method discovery**: Genre search, related artists, workout-specific tracks
- **Smart filtering** to exclude tracks you already know
- **Bypasses API restrictions** using creative discovery methods

### 🎵 **Smart Curator**
- **Anti-repetition algorithm** with usage history tracking
- **Artist variety enforcement** to avoid repetitive playlists
- **Freshness scoring** to maximize playlist variety
- **Usage statistics** to track curation performance

### 🏗️ **Modular Architecture**
- **Service abstraction** for easy addition of new music platforms
- **Centralized configuration** with per-service settings
- **Interactive CLI** with guided setup and error handling
- **Health monitoring** and service validation

## 🚀 **Quick Start**

### **Prerequisites**
- **Python 3.8+**
- **Music service account** (Spotify Premium recommended)
- **Developer API credentials** for your chosen service

### **1. Installation**
```bash
# Clone the repository
git clone <your-repo-url>
cd Spotify_workout_playlist

# Install dependencies
pip3 install -r requirements.txt
```

### **2. Check System Status**
```bash
python3 main.py status
```

### **3. Setup Your First Service (Spotify)**
```bash
# Create configuration template
python3 main.py setup spotify

# Follow the setup instructions, then test
python3 main.py test spotify
```

### **4. Start Using!**
```bash
# Discover new music
python3 main.py discover --service spotify --size 10

# Create curated playlists
python3 main.py curate --service spotify --size 15
```

## 📋 **Complete Command Reference**

### **System Management**
```bash
python3 main.py status              # Show all services status
python3 main.py setup <service>     # Setup specific service
python3 main.py test <service>      # Test service connection  
python3 main.py health              # Health check all services
```

### **Music Generation**
```bash
# Interactive mode (auto-selects available service)
python3 main.py discover            # Find new music
python3 main.py curate             # Create smart playlist

# Explicit service selection
python3 main.py discover --service spotify --size 20
python3 main.py curate --service youtube_music --size 25
python3 main.py discover --reference-playlist PLAYLIST_ID
```

### **Get Help**
```bash
python3 main.py --help             # Main help
python3 main.py discover --help    # Command-specific help
```

## ⚙️ **Service Setup Guides**

### **🎵 Spotify Setup**

1. **Create Spotify Developer App**
   - Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/)
   - Create a new app
   - Add redirect URI: `http://127.0.0.1:8080/callback`
   - Note your **Client ID** and **Client Secret**

2. **Configure the Service**
   ```bash
   python3 main.py setup spotify
   # Edit: ~/.multi_music_generator/spotify.env
   ```

3. **Required Configuration**
   ```env
   SPOTIFY_CLIENT_ID=your_client_id_here
   SPOTIFY_CLIENT_SECRET=your_client_secret_here
   SPOTIFY_REDIRECT_URI=http://127.0.0.1:8080/callback
   REFERENCE_PLAYLIST_ID=your_playlist_id_here
   ```

4. **Get Reference Playlist ID**
   - Open your workout playlist in Spotify
   - Click "Share" → "Copy Spotify URI"
   - Extract ID from: `spotify:playlist:2dAT0EBXEe8KQt9FIyOsRP`
   - Use: `2dAT0EBXEe8KQt9FIyOsRP`

### **🎬 YouTube Music Setup** (Coming Soon)

1. **Create Google Developer Project**
   - Go to [Google Cloud Console](https://console.developers.google.com/)
   - Create new project or select existing
   - Enable YouTube Data API v3
   - Create OAuth 2.0 credentials

2. **Configure the Service**
   ```bash
   python3 main.py setup youtube_music
   # Edit: ~/.multi_music_generator/youtube_music.env
   ```

3. **Required Configuration**
   ```env
   YOUTUBE_CLIENT_ID=your_client_id_here
   YOUTUBE_CLIENT_SECRET=your_client_secret_here
   YOUTUBE_REDIRECT_URI=http://localhost:8080/callback
   REFERENCE_PLAYLIST_ID=your_playlist_id_here
   ```

### **🛒 Amazon Music Setup** (Coming Soon)

1. **Create Amazon Developer Account**
   - Go to [Amazon Developer Portal](https://developer.amazon.com/)
   - Create new app in your developer account
   - Request Music API access (requires approval)

2. **Configure the Service**
   ```bash
   python3 main.py setup amazon_music
   # Edit: ~/.multi_music_generator/amazon_music.env
   ```

## 🛠️ **Adding New Music Services**

### **Step-by-Step Integration Guide**

**1. Create Service Implementation**
```bash
# Create service files in the services/ directory
touch services/SERVICE_service.py
touch services/SERVICE_discovery.py
touch services/SERVICE_curator.py
```

**2. Implement Base Classes**
```python
# services/SERVICE_service.py
from base_music_service import BaseMusicService, MusicServiceType, TrackInfo, PlaylistInfo, ArtistInfo

class YourMusicService(BaseMusicService):
    @property
    def service_type(self) -> MusicServiceType:
        return MusicServiceType.YOUR_SERVICE
    
    @property  
    def service_name(self) -> str:
        return "Your Service Name"
    
    # Implement all abstract methods...
    async def authenticate(self) -> bool:
        # Your authentication logic
        pass
    
    async def get_playlist_tracks(self, playlist_id: str) -> List[TrackInfo]:
        # Your playlist fetching logic
        pass
    
    # ... implement all other required methods
```

**3. Implement Discovery Engine**
```python
# services/SERVICE_discovery.py
from base_music_service import BaseDiscoveryEngine

class YourDiscoveryEngine(BaseDiscoveryEngine):
    async def discover_new_playlist(self, reference_playlist_id: str, target_size: int = 30) -> Dict[str, Any]:
        # Your discovery logic
        pass
    
    async def analyze_taste_profile(self, reference_playlist_id: str) -> Dict[str, Any]:
        # Your taste analysis logic
        pass
```

**4. Implement Curator**
```python
# services/SERVICE_curator.py
from base_music_service import BaseCurator

class YourCurator(BaseCurator):
    async def generate_curated_playlist(self, reference_playlist_id: str, target_size: int = 30) -> Dict[str, Any]:
        # Your curation logic
        pass
    
    async def get_usage_stats(self) -> Dict[str, Any]:
        # Your statistics logic
        pass
```

**5. Register the Service**
```python
# Add to main.py in CLIContext._register_services()
try:
    from services.your_service import YourMusicService
    from services.your_discovery import YourDiscoveryEngine  
    from services.your_curator import YourCurator
    
    self.service_manager.register_service(
        MusicServiceType.YOUR_SERVICE,
        YourMusicService,
        YourDiscoveryEngine,
        YourCurator
    )
except ImportError:
    logger.info("Your service not yet implemented")
```

**6. Add Service Type**
```python
# Add to base_music_service.py in MusicServiceType enum
class MusicServiceType(Enum):
    SPOTIFY = "spotify"
    YOUTUBE_MUSIC = "youtube_music"
    AMAZON_MUSIC = "amazon_music"
    YOUR_SERVICE = "your_service"  # Add this line
```

**7. Update Service Manager Templates**
```python
# Add configuration template in service_manager.py
elif service_type == MusicServiceType.YOUR_SERVICE:
    template = """# Your Service Configuration
# Your setup instructions here

YOUR_CLIENT_ID=your_client_id_here
YOUR_CLIENT_SECRET=your_client_secret_here
# ... other config options
"""
```

**8. Test Your Integration**
```bash
python3 main.py status              # Should show your service
python3 main.py setup your_service  # Should create config template
python3 main.py test your_service   # Should test connection
```

## 📁 **Project Structure**

```
Spotify_workout_playlist/
├── main.py                          # 🚀 Main CLI interface
├── base_music_service.py            # 🏗️  Abstract base classes
├── service_manager.py               # 🔧 Service management & validation
├── services/                        # 📂 Service implementations
│   ├── __init__.py
│   ├── spotify_service.py           # 🎵 Spotify API integration
│   ├── spotify_discovery.py         # 🔍 Spotify discovery engine
│   ├── spotify_curator.py           # 🎵 Spotify curation engine
│   ├── youtube_service.py           # 🎬 YouTube Music (template ready)
│   └── amazon_service.py            # 🛒 Amazon Music (template ready)
├── requirements.txt                 # 📦 Python dependencies
├── .env.example                     # 📝 Environment template (legacy)
└── README.md                        # 📚 This documentation
```

## 💡 **Usage Examples**

### **🔍 Music Discovery**
```bash
# Discover 20 new tracks
python3 main.py discover --service spotify --size 20

# Use specific reference playlist  
python3 main.py discover --reference-playlist 2dAT0EBXEe8KQt9FIyOsRP --size 15

# Interactive mode (auto-selects service)
python3 main.py discover
```

**Example Output:**
```
🎉 Discovery completed!
📝 New Playlist: Music Discovery - 2025-07-28
🎵 Tracks Discovered: 20
🔗 Listen: https://open.spotify.com/playlist/...

🎯 Your Taste Profile:
🎸 Genres: alternative metal, post-grunge, metalcore, rap metal, nu metal
👥 Artists Analyzed: 50
```

### **🎵 Smart Curation**
```bash
# Create curated playlist
python3 main.py curate --service spotify --size 25

# Interactive mode
python3 main.py curate
```

**Example Output:**
```
🎉 Curation completed!
📝 Playlist: Daily Workout Mix - 2025-07-28
🎵 Tracks: 25
🔗 Listen: https://open.spotify.com/playlist/...
📊 Freshness Score: 75.5%
```

## 🔧 **Configuration**

### **Per-Service Configuration**
Each service gets its own configuration file:
- **Spotify**: `~/.multi_music_generator/spotify.env`
- **YouTube Music**: `~/.multi_music_generator/youtube_music.env`
- **Amazon Music**: `~/.multi_music_generator/amazon_music.env`

### **Common Options**
```env
# Playlist settings
TARGET_PLAYLIST_NAME=Daily Workout Mix
PLAYLIST_SIZE=30

# Optional customization
UPDATE_TIME=07:00
TARGET_ENERGY=0.8
TARGET_DANCEABILITY=0.7
```

## 🛠️ **Troubleshooting**

### **Service Issues**
```bash
python3 main.py status    # Check service configuration
python3 main.py health    # Test service connections
```

### **Common Problems**
- **Authentication errors**: Check API credentials and redirect URIs
- **No tracks found**: Expand reference playlist or try different genres
- **Rate limiting**: Wait a few minutes and retry
- **Service not found**: Ensure service module is properly imported

### **Getting Help**
- Use `--help` with any command for detailed options
- Check service-specific error messages for troubleshooting steps
- Review configuration files for missing or incorrect values

## 🎯 **Why This Approach Works**

### **✅ Advantages**
- **🔓 No API Restrictions**: Bypasses recommendation API limitations
- **🎯 Better Control**: Discover exactly the genres you want
- **🔄 Infinite Variety**: Never runs out of new music to find
- **⚡ Works Immediately**: No business approval or extended quotas needed
- **🏗️ Modular Design**: Easy to add new music services
- **💡 User-Friendly**: Clear error messages and setup guidance

### **🎵 Perfect For**
- **🏋️ Workout enthusiasts** looking for high-energy tracks
- **🎸 Genre-specific listeners** (rock, metal, electronic, etc.)
- **🔍 Music discoverers** wanting to expand their library
- **📱 Playlist curators** needing variety without repetition
- **🛠️ Developers** wanting to add music service integrations

## 📄 **License**

This project is for personal use. Ensure compliance with each music service's Developer Terms of Service.

---

**🎵 Start discovering your next favorite tracks across multiple music services!** 🚀

### **Quick Commands to Get Started:**
```bash
python3 main.py setup spotify      # Setup Spotify
python3 main.py test spotify       # Test connection  
python3 main.py discover --size 10 # Find 10 new tracks
python3 main.py curate --size 15   # Create smart playlist
``` 