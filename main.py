"""Multi-Service Music Playlist Generator - Main CLI Interface."""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import click
from loguru import logger

from base_music_service import MusicServiceType
from service_manager import ServiceManager, MusicServiceError


# Configure logger
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")


class CLIContext:
    """Context object for CLI commands."""
    
    def __init__(self):
        self.service_manager = ServiceManager()
        self._register_services()
    
    def _register_services(self):
        """Register all available services."""
        # Import and register services as they become available
        try:
            from services.spotify_service import SpotifyService
            from services.spotify_discovery import SpotifyDiscoveryEngine
            from services.spotify_curator import SpotifyCurator
            
            self.service_manager.register_service(
                MusicServiceType.SPOTIFY,
                SpotifyService,
                SpotifyDiscoveryEngine,
                SpotifyCurator
            )
        except ImportError:
            logger.warning("Spotify service not available")
        
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
            logger.warning("YouTube Music service not available")
        
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
            logger.info("Amazon Music service not yet implemented")


@click.group()
@click.pass_context
def cli(ctx):
    """🎵 Multi-Service Music Playlist Generator
    
    Discover new music and create smart playlists across multiple music services.
    
    Supported services: Spotify, YouTube Music, Amazon Music
    """
    ctx.ensure_object(CLIContext)


@cli.command()
@click.pass_obj
def status(ctx: CLIContext):
    """📊 Show status of all music services."""
    click.echo("🎵 Multi-Service Music Generator Status\n")
    
    available_services = ctx.service_manager.get_available_services()
    if not available_services:
        click.echo("❌ No music services are available!")
        click.echo("💡 Make sure service modules are properly installed.")
        return
    
    status_info = ctx.service_manager.get_service_status()
    
    for service_name, info in status_info.items():
        service_display = service_name.replace('_', ' ').title()
        
        # Service header
        if info['configured']:
            click.echo(f"✅ {service_display}")
        else:
            click.echo(f"❌ {service_display}")
        
        # Configuration status
        click.echo(f"   📁 Config: {info['config_file']}")
        
        if info['configured']:
            click.echo(f"   ✅ Configuration: Valid")
        else:
            click.echo(f"   ❌ Configuration: Invalid")
            for error in info['errors']:
                click.echo(f"      • {error}")
        
        # Available features
        features = []
        if info['has_discovery']:
            features.append("🔍 Discovery")
        if info['has_curator']:
            features.append("🎵 Curation")
        
        if features:
            click.echo(f"   🎯 Features: {', '.join(features)}")
        else:
            click.echo(f"   ⚠️  Features: None available")
        
        click.echo()
    
    # Show setup suggestions
    unconfigured = [name for name, info in status_info.items() if not info['configured']]
    if unconfigured:
        click.echo("💡 To get started:")
        for service in unconfigured:
            click.echo(f"   python main.py setup {service}")


@cli.command()
@click.argument('service', type=click.Choice(['spotify', 'youtube_music', 'amazon_music']))
@click.pass_obj
def setup(ctx: CLIContext, service: str):
    """⚙️ Setup configuration for a music service."""
    try:
        service_type = MusicServiceType(service)
    except ValueError:
        click.echo(f"❌ Unknown service: {service}")
        return
    
    click.echo(f"🎵 Setting up {service.replace('_', ' ').title()}")
    click.echo()
    
    # Create config template
    try:
        config_file = ctx.service_manager.create_service_config_template(service_type)
        click.echo(f"📁 Created configuration template: {config_file}")
        click.echo()
        
        # Show service-specific setup instructions
        if service_type == MusicServiceType.SPOTIFY:
            click.echo("🎯 Spotify Setup Instructions:")
            click.echo("1. Go to: https://developer.spotify.com/dashboard/")
            click.echo("2. Create a new app")
            click.echo("3. Add redirect URI: http://127.0.0.1:8080/callback")
            click.echo("4. Copy your Client ID and Client Secret")
            click.echo()
            click.echo("📋 Get your reference playlist ID:")
            click.echo("1. Open your workout playlist in Spotify")
            click.echo("2. Click Share → Copy Spotify URI")
            click.echo("3. Extract ID from: spotify:playlist:YOUR_PLAYLIST_ID")
        
        elif service_type == MusicServiceType.YOUTUBE_MUSIC:
            click.echo("🎯 YouTube Music Setup Instructions:")
            click.echo("1. Go to: https://console.developers.google.com/")
            click.echo("2. Create a new project or select existing")
            click.echo("3. Enable YouTube Data API v3")
            click.echo("4. Create OAuth 2.0 credentials")
            click.echo("5. Add redirect URI: http://localhost:8080/callback")
            click.echo()
            click.echo("⚠️  Note: YouTube Music API access may require approval")
        
        elif service_type == MusicServiceType.AMAZON_MUSIC:
            click.echo("🎯 Amazon Music Setup Instructions:")
            click.echo("1. Go to: https://developer.amazon.com/")
            click.echo("2. Create a new app in your developer account")
            click.echo("3. Request Music API access (requires approval)")
            click.echo("4. Configure OAuth settings")
            click.echo()
            click.echo("⚠️  Note: Amazon Music API requires business approval")
        
        click.echo()
        click.echo(f"✏️  Edit the configuration file: {config_file}")
        click.echo(f"🧪 Test your setup: python main.py test {service}")
        
    except Exception as e:
        click.echo(f"❌ Failed to create setup: {e}")


@cli.command()
@click.argument('service', type=click.Choice(['spotify', 'youtube_music', 'amazon_music']))
@click.pass_obj
def test(ctx: CLIContext, service: str):
    """🧪 Test connection to a music service."""
    async def test_service():
        try:
            service_type = MusicServiceType(service)
            service_obj = await ctx.service_manager.initialize_service(service_type)
            
            click.echo(f"✅ Successfully connected to {service.replace('_', ' ').title()}!")
            
            # Get user info
            user = await service_obj.get_current_user()
            if user:
                click.echo(f"👤 Logged in as: {user.get('display_name', user.get('name', 'Unknown'))}")
            
            return True
            
        except MusicServiceError as e:
            click.echo(e.get_formatted_error())
            return False
        except Exception as e:
            click.echo(f"❌ Unexpected error: {e}")
            return False
    
    success = asyncio.run(test_service())
    if success:
        click.echo(f"🎉 {service.replace('_', ' ').title()} is ready to use!")


@cli.command()
@click.option('--service', type=click.Choice(['spotify', 'youtube_music', 'amazon_music']), 
              help='Music service to use (will prompt if not specified)')
@click.option('--reference-playlist', help='Reference playlist ID (will use config if not specified)')
@click.option('--size', default=30, help='Number of tracks to discover')
@click.pass_obj
def discover(ctx: CLIContext, service: Optional[str], reference_playlist: Optional[str], size: int):
    """🔍 Discover new music based on your taste profile."""
    async def run_discovery():
        nonlocal reference_playlist  # Allow modification of outer scope variable
        try:
            # Select service
            if not service:
                service_type = await _interactive_service_selection(ctx, require_discovery=True)
            else:
                service_type = MusicServiceType(service)
            
            click.echo(f"🔍 Discovering new music with {service_type.value.replace('_', ' ').title()}")
            
            # Initialize service
            await ctx.service_manager.initialize_service(service_type)
            discovery_engine = ctx.service_manager.get_discovery_engine(service_type)
            
            # Get reference playlist
            if reference_playlist is None:
                config = ctx.service_manager._load_service_config(service_type)
                reference_playlist = config.get('REFERENCE_PLAYLIST_ID')
            
            if not reference_playlist or reference_playlist == 'your_playlist_id_here':
                raise MusicServiceError(
                    "No reference playlist specified",
                    suggestions=[
                        "Add --reference-playlist PLAYLIST_ID to the command",
                        f"Configure REFERENCE_PLAYLIST_ID in your {service_type.value}.env file",
                        f"Run: python main.py setup {service_type.value}"
                    ]
                )
            
            # Discover music
            click.echo(f"🎵 Analyzing your taste from playlist: {reference_playlist}")
            result = await discovery_engine.discover_new_playlist(reference_playlist, size)
            
            # Display results
            click.echo(f"\n🎉 Discovery completed!")
            playlist_name = result.get('playlist_name') or result.get('name', 'Unknown')
            playlist_url = result.get('playlist_url') or result.get('external_url', 'N/A')
            track_count = len(result.get('tracks', []))
            
            click.echo(f"📝 New Playlist: {playlist_name}")
            click.echo(f"🎵 Tracks Discovered: {track_count}")
            click.echo(f"🔗 Listen: {playlist_url}")
            
            if 'taste_profile' in result:
                profile = result['taste_profile']
                click.echo(f"\n🎯 Your Taste Profile:")
                if 'genres' in profile:
                    click.echo(f"🎸 Genres: {', '.join(profile['genres'][:5])}")
                if 'artists_analyzed' in profile:
                    click.echo(f"👥 Artists Analyzed: {profile['artists_analyzed']}")
            
        except MusicServiceError as e:
            click.echo(e.get_formatted_error())
        except Exception as e:
            click.echo(f"❌ Discovery failed: {e}")
            logger.exception("Discovery error")
    
    asyncio.run(run_discovery())


@cli.command()
@click.option('--service', type=click.Choice(['spotify', 'youtube_music', 'amazon_music']), 
              help='Music service to use (will prompt if not specified)')
@click.option('--reference-playlist', help='Reference playlist ID (will use config if not specified)')
@click.option('--size', default=30, help='Number of tracks to curate')
@click.pass_obj
def curate(ctx: CLIContext, service: Optional[str], reference_playlist: Optional[str], size: int):
    """🎵 Create smart curated playlist from your existing favorites."""
    async def run_curation():
        nonlocal reference_playlist  # Allow modification of outer scope variable
        try:
            # Select service
            if not service:
                service_type = await _interactive_service_selection(ctx, require_curator=True)
            else:
                service_type = MusicServiceType(service)
            
            click.echo(f"🎵 Creating curated playlist with {service_type.value.replace('_', ' ').title()}")
            
            # Initialize service
            await ctx.service_manager.initialize_service(service_type)
            curator = ctx.service_manager.get_curator(service_type)
            
            # Get reference playlist
            if reference_playlist is None:
                config = ctx.service_manager._load_service_config(service_type)
                reference_playlist = config.get('REFERENCE_PLAYLIST_ID')
            
            if not reference_playlist or reference_playlist == 'your_playlist_id_here':
                raise MusicServiceError(
                    "No reference playlist specified",
                    suggestions=[
                        "Add --reference-playlist PLAYLIST_ID to the command",
                        f"Configure REFERENCE_PLAYLIST_ID in your {service_type.value}.env file",
                        f"Run: python main.py setup {service_type.value}"
                    ]
                )
            
            # Generate curated playlist
            click.echo(f"🎵 Curating from playlist: {reference_playlist}")
            result = await curator.generate_curated_playlist(reference_playlist, size)
            
            # Display results
            click.echo(f"\n🎉 Curation completed!")
            playlist_name = result.get('playlist_name') or result.get('name', 'Unknown')
            playlist_url = result.get('playlist_url') or result.get('external_url', 'N/A')
            track_count = len(result.get('tracks', []))
            
            click.echo(f"📝 Playlist: {playlist_name}")
            click.echo(f"🎵 Tracks Added: {track_count}")
            click.echo(f"🔗 Listen: {playlist_url}")
            
            if 'freshness_score' in result:
                freshness = result['freshness_score']
                click.echo(f"✨ Freshness Score: {freshness:.1f}%")
                
                # Show additional stats if available
                if 'stats' in result:
                    stats = result['stats']
                    if 'freshness_details' in stats:
                        click.echo(f"   └ {stats['freshness_details']}")
                    if 'unique_artists' in stats:
                        click.echo(f"🎤 Unique Artists: {stats['unique_artists']}")
            
        except MusicServiceError as e:
            click.echo(e.get_formatted_error())
        except Exception as e:
            click.echo(f"❌ Curation failed: {e}")
            logger.exception("Curation error")
    
    asyncio.run(run_curation())


@cli.command()
@click.pass_obj
def health(ctx: CLIContext):
    """🔧 Check health of all configured services."""
    async def check_health():
        click.echo("🔧 Checking service health...\n")
        
        results = await ctx.service_manager.health_check_all()
        
        if not results:
            click.echo("⚠️  No services are currently active")
            click.echo("💡 Run 'python main.py status' to see configuration status")
            return
        
        for service_name, (is_healthy, message) in results.items():
            service_display = service_name.replace('_', ' ').title()
            
            if is_healthy:
                click.echo(f"✅ {service_display}: {message}")
            else:
                click.echo(f"❌ {service_display}: {message}")
        
        # Summary
        healthy_count = sum(1 for is_healthy, _ in results.values() if is_healthy)
        total_count = len(results)
        
        click.echo(f"\n📊 Health Summary: {healthy_count}/{total_count} services healthy")
    
    asyncio.run(check_health())


async def _interactive_service_selection(ctx: CLIContext, require_discovery: bool = False, require_curator: bool = False) -> MusicServiceType:
    """Interactive service selection with validation."""
    available_services = ctx.service_manager.get_available_services()
    
    if not available_services:
        raise MusicServiceError(
            "No music services are available",
            suggestions=[
                "Install service dependencies",
                "Check that service modules are properly imported"
            ]
        )
    
    # Filter services based on requirements
    valid_services = []
    status_info = ctx.service_manager.get_service_status()
    
    for service_type in available_services:
        info = status_info[service_type.value]
        
        # Check configuration
        if not info['configured']:
            continue
        
        # Check feature requirements
        if require_discovery and not info['has_discovery']:
            continue
        if require_curator and not info['has_curator']:
            continue
        
        valid_services.append(service_type)
    
    if not valid_services:
        feature_name = "discovery" if require_discovery else "curation" if require_curator else "any features"
        raise MusicServiceError(
            f"No configured services support {feature_name}",
            suggestions=[
                "Run 'python main.py status' to see configuration status",
                "Setup a service: python main.py setup <service>"
            ]
        )
    
    if len(valid_services) == 1:
        return valid_services[0]
    
    # Interactive selection
    click.echo("🎵 Multiple services available. Please choose:")
    for i, service_type in enumerate(valid_services, 1):
        service_name = service_type.value.replace('_', ' ').title()
        click.echo(f"  {i}. {service_name}")
    
    while True:
        try:
            choice = click.prompt("Enter your choice", type=int)
            if 1 <= choice <= len(valid_services):
                return valid_services[choice - 1]
            else:
                click.echo(f"Please enter a number between 1 and {len(valid_services)}")
        except (ValueError, click.Abort):
            click.echo("Invalid choice. Please enter a number.")


if __name__ == '__main__':
    cli() 