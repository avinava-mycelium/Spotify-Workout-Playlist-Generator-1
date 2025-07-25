# Spotify Workout Playlist Generator

A smart music discovery and playlist curation tool that creates personalized workout playlists using Spotify's API. This tool bypasses Spotify's restricted Recommendations API (which requires business approval) by using creative discovery methods that work with standard developer accounts.

## 🎯 Features

### 🔍 **Music Discovery Engine**
- **Discovers completely NEW tracks** you've never heard
- **Analyzes your taste profile** from your reference playlist
- **Genre-based discovery** using your favorite genres
- **Related artist exploration** to find similar artists
- **Smart filtering** to exclude tracks you already know
- **Perfect for expanding your music library**

### 🎵 **Enhanced Curator** 
- **Smart playlist curation** from your existing favorites
- **Anti-repetition algorithm** with usage history tracking
- **Artist variety enforcement** to avoid repetitive playlists
- **Freshness scoring** to show how varied each playlist is
- **Perfect for creating fresh mixes from known favorites**

## 🚀 Quick Start

### Prerequisites
- **Spotify Premium account**
- **Python 3.8+**
- **Spotify Developer App** (free to create)

### 1. Setup Spotify Developer App
1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/)
2. Create a new app
3. Add redirect URI: `http://127.0.0.1:8080/callback`
4. Note your **Client ID** and **Client Secret**

### 2. Installation
```bash
# Clone the repository
git clone <your-repo-url>
cd Spotify_workout_playlist

# Install dependencies
pip3 install -r requirements.txt

# Setup environment variables
cp .env.example .env
# Edit .env with your Spotify credentials
```

### 3. Configuration
Edit `.env` with your credentials:
```env
SPOTIFY_CLIENT_ID=your_client_id_here
SPOTIFY_CLIENT_SECRET=your_client_secret_here
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8080/callback
REFERENCE_PLAYLIST_ID=your_reference_playlist_id
```

**Getting your Reference Playlist ID:**
1. Open your workout playlist in Spotify
2. Click "Share" → "Copy Spotify URI"
3. Extract the ID from: `spotify:playlist:2dAT0EBXEe8KQt9FIyOsRP`
4. Use: `2dAT0EBXEe8KQt9FIyOsRP`

## 💡 Usage

### 🔍 Discover New Music
Find completely new tracks based on your taste:
```bash
python3 music_discovery_engine.py
```

**What it does:**
- Analyzes your reference playlist to understand your taste
- Searches for new tracks in your favorite genres (metalcore, post-grunge, hard rock, etc.)
- Finds tracks from artists related to your favorites
- Creates a "Music Discovery" playlist with 30 new tracks
- Filters out anything you already know

**Example output:**
```
🎉 New music discovered successfully!
📝 Discovery Playlist: Music Discovery - 2025-07-25
🎵 New Tracks: 30
🔗 Spotify URL: https://open.spotify.com/playlist/...

🎯 Your Taste Profile:
🎸 Favorite Genres: post-grunge, metalcore, hard rock, alternative metal
👥 Artists Analyzed: 77

🎵 Your new discoveries:
  1. Walk - Pantera (search:heavy metal)
  2. Second Chance - Shinedown (genre:post-grunge)
  3. Don't Look Down - The Treatment (genre:hard rock)
  ...
```

### 🎵 Create Smart Curated Playlists
Generate variety from your existing favorites:
```bash
python3 enhanced_curator.py generate
```

**What it does:**
- Selects 30 tracks from your 72-track reference playlist
- Uses anti-repetition algorithm to avoid recently used tracks
- Ensures artist variety and freshness
- Tracks usage history to maximize variety over time
- Creates both daily and main workout playlists

**Example output:**
```
🎉 Enhanced workout playlist generated successfully!
📝 Playlist: Daily Workout Mix - 2025-07-25
🎵 Tracks: 30

📊 Freshness Score: 70.0%
🆕 Never used: 0 tracks
🔄 Rarely used: 30 tracks
♻️  Frequently used: 0 tracks
```

### 📊 Check Usage Statistics
See how the curator is managing variety:
```bash
python3 enhanced_curator.py stats
```

## 🔧 Configuration Options

Edit `config.py` or `.env` to customize:

```env
# Playlist settings
TARGET_PLAYLIST_NAME="Daily Workout Mix"
PLAYLIST_SIZE=30

# Discovery settings  
DAILY_GENERATION_TIME="08:00"
CLEANUP_OLDER_THAN_DAYS=30
```

## 📁 Project Structure

```
Spotify_workout_playlist/
├── music_discovery_engine.py    # 🔍 NEW music discovery
├── enhanced_curator.py          # 🎵 Smart curation with history
├── spotify_client.py            # 🎧 Spotify API integration
├── config.py                    # ⚙️  Configuration management
├── requirements.txt             # 📦 Python dependencies
├── .env.example                 # 📝 Environment template
└── README.md                    # 📚 Documentation
```

## 🤔 Why This Approach Works Better

### ❌ Spotify's Limitations
- **Recommendations API**: Requires business approval (250k+ users)
- **Audio Features API**: Limited for development apps
- **Extended Quota**: Only for established companies

### ✅ Our Solution Benefits
- **🎯 Better Quality Control**: Every discovery is in your favorite genres
- **🔄 Infinite Variety**: Genre-based discovery never runs out
- **⚡ Zero Dependencies**: No approval needed, works immediately
- **🎵 Taste-Focused**: Based on YOUR actual preferences

## 🛠️ Troubleshooting

### Authentication Issues
- Ensure redirect URI matches exactly: `http://127.0.0.1:8080/callback`
- Check Client ID and Secret are correct
- Try different redirect URI options in `.env.example`

### No New Tracks Found
- Expand your reference playlist (add more varied artists)
- Check if your genres are too niche
- Try running discovery multiple times

### Rate Limiting
- The tool respects Spotify's rate limits
- If you hit limits, wait a few minutes and retry

## 🎵 Perfect For

- **🏋️ Workout Enthusiasts**: High-energy track discovery
- **🎸 Rock/Metal Fans**: Excellent genre coverage for heavy music
- **🔍 Music Discoverers**: Finding hidden gems in your favorite styles
- **📱 Playlist Curators**: Creating fresh mixes without repetition

## 📄 License

This project is for personal use. Ensure compliance with Spotify's Developer Terms of Service.

---

**🎵 Start discovering your next favorite workout tracks!** 💪 