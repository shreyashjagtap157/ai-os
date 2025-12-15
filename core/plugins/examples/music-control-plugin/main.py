"""
AI-OS Music Control Plugin
Control music playback via Spotify, MPRIS, or local player
"""

import json
import logging
import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
import subprocess

logger = logging.getLogger(__name__)


class PlayerState(Enum):
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPED = "stopped"
    UNKNOWN = "unknown"


@dataclass
class Track:
    title: str
    artist: str
    album: str
    duration_ms: int
    artwork_url: Optional[str] = None
    uri: Optional[str] = None


@dataclass
class PlaybackState:
    state: PlayerState
    current_track: Optional[Track]
    position_ms: int
    volume: int  # 0-100
    shuffle: bool
    repeat: bool


class MusicControlPlugin:
    """Music playback control plugin for AI-OS"""
    
    def __init__(self, config: Dict[str, Any]):
        self.default_player = config.get("default_player", "mpris")
        self.default_volume = config.get("default_volume", 50)
        self.spotify_client_id = config.get("spotify_client_id", "")
        self.spotify_client_secret = config.get("spotify_client_secret", "")
        self._current_volume = self.default_volume
        self._is_shuffling = False
        self._is_repeating = False
    
    async def initialize(self) -> bool:
        """Initialize music control"""
        logger.info(f"Music control plugin initialized with player: {self.default_player}")
        return True
    
    async def shutdown(self):
        """Cleanup resources"""
        pass
    
    # ==================== MPRIS Controls (Linux) ====================
    
    def _run_mpris_command(self, command: str) -> bool:
        """Run playerctl command for MPRIS players"""
        try:
            subprocess.run(
                ["playerctl", command],
                check=True,
                capture_output=True
            )
            return True
        except Exception as e:
            logger.error(f"MPRIS command failed: {e}")
            return False
    
    def _get_mpris_metadata(self) -> Optional[Track]:
        """Get current track info from MPRIS"""
        try:
            result = subprocess.run(
                ["playerctl", "metadata", "--format", 
                 "{{title}}|||{{artist}}|||{{album}}|||{{mpris:length}}"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split("|||")
                if len(parts) >= 3:
                    duration = int(parts[3]) // 1000 if len(parts) > 3 else 0
                    return Track(
                        title=parts[0],
                        artist=parts[1],
                        album=parts[2],
                        duration_ms=duration
                    )
        except Exception as e:
            logger.error(f"Failed to get metadata: {e}")
        return None
    
    def _get_playback_state(self) -> PlaybackState:
        """Get current playback state"""
        track = self._get_mpris_metadata()
        
        try:
            result = subprocess.run(
                ["playerctl", "status"],
                capture_output=True,
                text=True
            )
            status = result.stdout.strip().lower()
            state = {
                "playing": PlayerState.PLAYING,
                "paused": PlayerState.PAUSED,
                "stopped": PlayerState.STOPPED
            }.get(status, PlayerState.UNKNOWN)
        except:
            state = PlayerState.UNKNOWN
        
        return PlaybackState(
            state=state,
            current_track=track,
            position_ms=0,
            volume=self._current_volume,
            shuffle=self._is_shuffling,
            repeat=self._is_repeating
        )
    
    # ==================== Intent Handlers ====================
    
    async def handle_intent(self, intent: str, entities: Dict[str, str]) -> str:
        """Route intent to appropriate handler"""
        handlers = {
            "play_music": self._handle_play,
            "play_song": self._handle_play_song,
            "pause": self._handle_pause,
            "resume": self._handle_resume,
            "next_track": self._handle_next,
            "previous_track": self._handle_previous,
            "set_volume": self._handle_set_volume,
            "volume_up": self._handle_volume_up,
            "volume_down": self._handle_volume_down,
            "now_playing": self._handle_now_playing,
            "toggle_shuffle": self._handle_toggle_shuffle,
            "toggle_repeat": self._handle_toggle_repeat,
        }
        
        handler = handlers.get(intent)
        if handler:
            return await handler(entities)
        return "I don't know how to do that."
    
    async def _handle_play(self, entities: Dict[str, str]) -> str:
        if self._run_mpris_command("play"):
            return "Playing music"
        return "Unable to start playback"
    
    async def _handle_play_song(self, entities: Dict[str, str]) -> str:
        song = entities.get("song", "")
        artist = entities.get("artist", "")
        
        # For MPRIS, we can't directly play a specific song
        # This would need Spotify API integration for full functionality
        if song:
            query = f"{song}"
            if artist:
                query += f" by {artist}"
            return f"Searching for {query}... (full search requires Spotify integration)"
        
        return await self._handle_play(entities)
    
    async def _handle_pause(self, entities: Dict[str, str]) -> str:
        if self._run_mpris_command("pause"):
            return "Music paused"
        return "Unable to pause"
    
    async def _handle_resume(self, entities: Dict[str, str]) -> str:
        if self._run_mpris_command("play"):
            return "Resuming playback"
        return "Unable to resume"
    
    async def _handle_next(self, entities: Dict[str, str]) -> str:
        if self._run_mpris_command("next"):
            await asyncio.sleep(0.5)  # Wait for track change
            track = self._get_mpris_metadata()
            if track:
                return f"Now playing: {track.title} by {track.artist}"
            return "Skipped to next track"
        return "Unable to skip track"
    
    async def _handle_previous(self, entities: Dict[str, str]) -> str:
        if self._run_mpris_command("previous"):
            await asyncio.sleep(0.5)
            track = self._get_mpris_metadata()
            if track:
                return f"Now playing: {track.title} by {track.artist}"
            return "Went to previous track"
        return "Unable to go back"
    
    async def _handle_set_volume(self, entities: Dict[str, str]) -> str:
        value = entities.get("value", "50")
        try:
            volume = int(float(value))
            volume = max(0, min(100, volume))
            self._current_volume = volume
            
            # Set volume via pactl (PulseAudio)
            subprocess.run(
                ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{volume}%"],
                check=True
            )
            return f"Volume set to {volume}%"
        except Exception as e:
            logger.error(f"Failed to set volume: {e}")
            return "Unable to set volume"
    
    async def _handle_volume_up(self, entities: Dict[str, str]) -> str:
        self._current_volume = min(100, self._current_volume + 10)
        try:
            subprocess.run(
                ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+10%"],
                check=True
            )
            return f"Volume up to {self._current_volume}%"
        except:
            return "Unable to increase volume"
    
    async def _handle_volume_down(self, entities: Dict[str, str]) -> str:
        self._current_volume = max(0, self._current_volume - 10)
        try:
            subprocess.run(
                ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-10%"],
                check=True
            )
            return f"Volume down to {self._current_volume}%"
        except:
            return "Unable to decrease volume"
    
    async def _handle_now_playing(self, entities: Dict[str, str]) -> str:
        track = self._get_mpris_metadata()
        if track:
            return f"Now playing: {track.title} by {track.artist} from {track.album}"
        return "No music is currently playing"
    
    async def _handle_toggle_shuffle(self, entities: Dict[str, str]) -> str:
        self._is_shuffling = not self._is_shuffling
        self._run_mpris_command("shuffle toggle" if self._is_shuffling else "shuffle off")
        return f"Shuffle {'on' if self._is_shuffling else 'off'}"
    
    async def _handle_toggle_repeat(self, entities: Dict[str, str]) -> str:
        self._is_repeating = not self._is_repeating
        return f"Repeat {'on' if self._is_repeating else 'off'}"


# ==================== Plugin Entry Point ====================

plugin_instance: Optional[MusicControlPlugin] = None


async def initialize(config: Dict[str, Any]) -> bool:
    """Plugin initialization"""
    global plugin_instance
    plugin_instance = MusicControlPlugin(config)
    return await plugin_instance.initialize()


async def shutdown():
    """Plugin shutdown"""
    if plugin_instance:
        await plugin_instance.shutdown()


async def handle_intent(intent: str, entities: Dict[str, str]) -> str:
    """Handle incoming intent"""
    if plugin_instance:
        return await plugin_instance.handle_intent(intent, entities)
    return "Music control plugin not initialized"
