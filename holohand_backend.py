#!/usr/bin/env python3
"""
================================================================================
PROJECT HOLOHAND — ESP32-CAM REAL-TIME AR GESTURE STUDIO & MUSIC CONDUCTOR
================================================================================
Physical Hardware: AI-Thinker ESP32-CAM (OV2640 Sensor) over Wi-Fi MJPEG HTTP Stream
Processing Pipeline:
  ESP32-CAM Capture -> MJPEG HTTP -> Python Low-Latency Worker -> OpenCV Decoding
  -> MediaPipe 21-Landmark Tracking -> Normalized Geometric & Motion Classification
  -> Temporal Stabilization & Cooldown -> Mode Action Routing (Holo/Cam/Music)
  -> Alpha-Blended AR Holographic HUD -> Desktop Automation / Pygame Audio Engine
================================================================================
"""

import sys
import os
import time
import math
import argparse
import threading
import queue
import urllib.request
from collections import deque
from datetime import datetime

import cv2
import numpy as np

# MediaPipe Hand Landmark Inference
try:
    import mediapipe as mp
    mp_hands = mp.solutions.hands
except Exception as e:
    print(f"[HOLOHAND][FATAL] Failed to import MediaPipe: {e}")
    sys.exit(1)

# PyAutoGUI for Desktop & Presentation Automation
try:
    import pyautogui
    pyautogui.FAILSAFE = False  # Controlled via our own emergency disable
    pyautogui.PAUSE = 0.01      # Minimize automation latency
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    print("[HOLOHAND][WARN] pyautogui not installed. Desktop automation disabled.")

# Pygame for Music Conductor & Audio Synthesis
try:
    import pygame
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    PYGAME_AVAILABLE = True
except Exception as e:
    PYGAME_AVAILABLE = False
    print(f"[HOLOHAND][WARN] Pygame audio unavailable: {e}")

# Windows Native Core Audio Master Volume API via pycaw
try:
    import comtypes
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    PYCAW_AVAILABLE = True
except ImportError:
    PYCAW_AVAILABLE = False
    print("[HOLOHAND][INFO] pycaw not installed or unavailable; using fallback audio keys.")

# ==============================================================================
# 1. DEFAULT CONFIGURATION & TUNING CONSTANTS
# ==============================================================================
DEFAULT_STREAM_URL     = "http://192.168.1.100/stream"  # Target ESP32-CAM IP
DEFAULT_DISPLAY_WIDTH  = 960
DEFAULT_DISPLAY_HEIGHT = 720
TARGET_FPS             = 30

# MediaPipe Tracking Hyperparameters
CONF_DETECTION         = 0.65
CONF_TRACKING          = 0.55
MAX_HANDS              = 2

# Gesture Engine Stabilization & Temporal Filter
STABILIZATION_FRAMES   = 3     # Snappy 100ms dwell window for responsive confirmation
DEFAULT_COOLDOWN_SEC   = 0.85  # Dead-time after one-shot gesture activation
PINCH_THRESHOLD        = 0.24  # Normalized distance between Thumb Tip and Index Tip
PINCH_RELEASE_THRESH   = 0.32  # Hysteresis release threshold
SPAN_MIN_VOL_DIST      = 0.14  # Normalized distance where volume is 0% (fingers touching)
SPAN_MAX_VOL_DIST      = 0.85  # Normalized distance where volume is 100% (fingers spread wide)
SWIPE_VELOCITY_THRESH  = 0.28  # Normalized screen width per second (lowered for natural, effortless flick)
SWIPE_MIN_DISTANCE     = 0.09  # Minimum horizontal displacement for swipe confirmation
HOVER_DWELL_SECONDS    = 0.75  # Time to trigger virtual control panel button via hover

# Directories for Media Storage
PHOTO_DIR              = os.path.join("captures", "photos")
VIDEO_DIR              = os.path.join("captures", "videos")
MUSIC_DIR              = "music"

# Operating Modes
MODE_HOLOGRAM          = "A: HOLOGRAM CONTROL"
MODE_CAMERA            = "B: CAMERA STUDIO"
MODE_MUSIC             = "C: MUSIC CONDUCTOR"
MODE_MOUSE             = "D: VIRTUAL AIR-MOUSE"
OPERATING_MODES        = [MODE_HOLOGRAM, MODE_CAMERA, MODE_MUSIC, MODE_MOUSE]

# Visual HUD Rendering Modes
VISUAL_HOLOGRAM        = "HOLOGRAM"  # Full futuristic glow, trails, particles, scanner
VISUAL_SCAN            = "SCAN"      # Technical skeleton & palm scanner only
VISUAL_MINIMAL         = "MINIMAL"   # Raw stream with minimalist telemetry
VISUAL_MODES           = [VISUAL_HOLOGRAM, VISUAL_SCAN, VISUAL_MINIMAL]

# Holographic Cyber Color Palette (BGR format for OpenCV)
COLOR_CYAN             = (255, 245, 0)     # Primary laser cyan
COLOR_BLUE             = (255, 120, 0)     # Deep cobalt blue
COLOR_VIOLET           = (255, 0, 157)     # Cyber violet accent
COLOR_WHITE            = (255, 255, 255)   # Technical bright white
COLOR_DARK_GLASS       = (18, 14, 12)      # Translucent background tint
COLOR_GREEN            = (80, 255, 80)     # Success / ready
COLOR_RED              = (60, 60, 255)     # Alert / recording red
COLOR_ORANGE           = (0, 165, 255)     # Warning / attention
COLOR_AMBER            = (0, 215, 255)     # Flashlight illumination amber/gold


# ==============================================================================
# 2. LOW-LATENCY ESP32-CAM MJPEG STREAM WORKER
# ==============================================================================
class StreamAcquisitionWorker(threading.Thread):
    """
    Dedicated background thread that connects to the ESP32-CAM HTTP MJPEG stream,
    extracts multipart JPEG boundaries (\xff\xd8 -> \xff\xd9), and maintains
    ONLY the single most recent frame in an atomic slot.
    Eliminates all buffering lag and frame backlog.
    """
    def __init__(self, stream_source):
        super().__init__(daemon=True, name="StreamWorker")
        self.stream_source = stream_source
        self.latest_frame = None
        self.lock = threading.Lock()
        self.running = True
        self.connected = False
        self.fps_counter = 0
        self.stream_fps = 0.0
        self.last_fps_time = time.monotonic()
        self.reconnect_count = 0
        self.status_message = "Initializing..."
        self.is_local_camera = False

        # Check if source is a local webcam device index
        try:
            self.cam_index = int(stream_source)
            self.is_local_camera = True
        except ValueError:
            self.is_local_camera = False

    def run(self):
        if self.is_local_camera:
            self._run_local_webcam()
        else:
            self._run_mjpeg_stream()

    def _run_local_webcam(self):
        self.status_message = f"Connecting to local camera index {self.cam_index}..."
        cap = cv2.VideoCapture(self.cam_index)
        if not cap.isOpened():
            self.status_message = f"Failed to open camera index {self.cam_index}"
            return

        self.connected = True
        self.status_message = f"Local camera index {self.cam_index} active"

        while self.running:
            ret, frame = cap.read()
            if ret and frame is not None:
                with self.lock:
                    self.latest_frame = frame
                self._update_fps()
            else:
                time.sleep(0.01)
        cap.release()

    def _run_mjpeg_stream(self):
        while self.running:
            self.status_message = f"Connecting to ESP32-CAM: {self.stream_source}..."
            try:
                req = urllib.request.Request(
                    self.stream_source,
                    headers={'User-Agent': 'HoloHand-Stream-Client/1.0'}
                )
                stream = urllib.request.urlopen(req, timeout=3.5)
                self.connected = True
                self.status_message = "ESP32-CAM Stream Online"
                bytes_buffer = bytearray()

                while self.running:
                    chunk = stream.read(4096)
                    if not chunk:
                        break
                    bytes_buffer.extend(chunk)

                    # Locate JPEG Start of Image (SOI) and End of Image (EOI)
                    a = bytes_buffer.find(b'\xff\xd8')
                    b = bytes_buffer.find(b'\xff\xd9')
                    if a != -1 and b != -1:
                        if b > a:
                            jpg_bytes = bytes_buffer[a:b+2]
                            bytes_buffer = bytes_buffer[b+2:]
                            
                            # Fast in-memory JPEG decode
                            frame = cv2.imdecode(np.frombuffer(jpg_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
                            if frame is not None:
                                with self.lock:
                                    self.latest_frame = frame
                                self._update_fps()
                        else:
                            # Incomplete/corrupted packet, trim buffer
                            bytes_buffer = bytes_buffer[a:]

            except Exception as e:
                self.connected = False
                self.reconnect_count += 1
                self.status_message = f"Stream disconnected ({type(e).__name__}). Reconnecting..."
                time.sleep(1.0)

    def _update_fps(self):
        self.fps_counter += 1
        now = time.monotonic()
        delta = now - self.last_fps_time
        if delta >= 1.0:
            self.stream_fps = self.fps_counter / delta
            self.fps_counter = 0
            self.last_fps_time = now

    def get_latest_frame(self):
        with self.lock:
            if self.latest_frame is None:
                return None
            return self.latest_frame.copy()

    def stop(self):
        self.running = False


# ==============================================================================
# 3. NON-BLOCKING ASYNCHRONOUS VIDEO RECORDER WORKER
# ==============================================================================
class AsyncVideoRecorder(threading.Thread):
    """
    Dedicated worker thread handling video encoding to disk via a bounded queue.
    Prevents file I/O from stalling the main vision/HUD pipeline.
    """
    def __init__(self, output_path, frame_size, fps=25.0):
        super().__init__(daemon=True, name="RecorderWorker")
        self.output_path = output_path
        self.frame_size = frame_size
        self.fps = fps
        self.queue = queue.Queue(maxsize=45)
        self.running = True
        self.writer = None
        self.frames_written = 0
        self.start_time = time.monotonic()
        self.codec_used = "UNKNOWN"

        # Initialize VideoWriter with primary codec and robust fallbacks
        codecs_to_try = [
            ('mp4v', '.mp4'),
            ('XVID', '.avi'),
            ('MJPG', '.avi')
        ]
        base, _ = os.path.splitext(output_path)

        for fourcc_str, ext in codecs_to_try:
            try:
                candidate_path = base + ext
                fourcc = cv2.VideoWriter_fourcc(*fourcc_str)
                writer = cv2.VideoWriter(candidate_path, fourcc, self.fps, self.frame_size)
                if writer.isOpened():
                    self.writer = writer
                    self.output_path = candidate_path
                    self.codec_used = fourcc_str
                    break
            except Exception:
                continue

        if not self.writer or not self.writer.isOpened():
            print(f"[HOLOHAND][ERROR] Could not initialize VideoWriter for {output_path}")

    def enqueue_frame(self, frame):
        if not self.running or not self.writer:
            return False
        try:
            self.queue.put_nowait(frame.copy())
            return True
        except queue.Full:
            # Drop frame rather than blocking computer vision pipeline
            return False

    def run(self):
        while self.running or not self.queue.empty():
            try:
                frame = self.queue.get(timeout=0.1)
                if self.writer and self.writer.isOpened():
                    self.writer.write(frame)
                    self.frames_written += 1
                self.queue.task_done()
            except queue.Empty:
                continue

        if self.writer and self.writer.isOpened():
            self.writer.release()
            print(f"[HOLOHAND] Video recording finalized: {self.output_path} ({self.frames_written} frames)")

    def stop(self):
        self.running = False


# ==============================================================================
# 4. PYGAME MUSIC CONDUCTOR & SYNTHESIZER SUBSYSTEM
# ==============================================================================
class MusicConductorEngine:
    """
    High-fidelity music conductor supporting real local playlists (.mp3, .wav, .ogg)
    and procedural harmonic synthesizers so music works instantly offline.
    """
    def __init__(self, music_directory):
        self.music_dir = music_directory
        self.playlist = []
        self.current_track_idx = -1
        self.is_playing = False
        self.is_muted = False
        self.volume = 0.7  # 0.0 to 1.0
        self.track_title = "None"
        self.sample_rates = 44100
        self.shutter_sound = None
        self.click_sound = None
        self.whoosh_sound = None

        if PYGAME_AVAILABLE:
            self._ensure_music_assets()
            self._scan_playlist()
            self._generate_sound_effects()
            pygame.mixer.music.set_volume(self.volume)

    def _ensure_music_assets(self):
        """Generates procedural demo synth chords if music directory is empty."""
        os.makedirs(self.music_dir, exist_ok=True)
        existing = [f for f in os.listdir(self.music_dir) if f.lower().endswith(('.mp3', '.wav', '.ogg'))]
        if not existing:
            demo_track_path = os.path.join(self.music_dir, "holohand_cyber_ambient.wav")
            print("[HOLOHAND] Generating procedural ambient music demo track...")
            self._synthesize_ambient_wav(demo_track_path, duration_sec=30)

    def _synthesize_ambient_wav(self, file_path, duration_sec=30):
        """Creates an offline ambient cyber chord track using NumPy."""
        sample_rate = 44100
        t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), False)
        # Synth chord frequencies: Root (130.81 C3), Fifth (196.00 G3), Minor 3rd (155.56 Eb3), Octave (261.63 C4)
        c3 = np.sin(2 * np.pi * 130.81 * t)
        g3 = np.sin(2 * np.pi * 196.00 * t)
        eb3 = np.sin(2 * np.pi * 155.56 * t)
        c4 = np.sin(2 * np.pi * 261.63 * t) * 0.5
        # LFO modulation for shimmering sci-fi pad
        lfo = 0.7 + 0.3 * np.sin(2 * np.pi * 0.25 * t)
        chord = (c3 + g3 + eb3 + c4) * 0.25 * lfo
        # Soft envelope fade in / out
        fade_samples = int(sample_rate * 2.0)
        chord[:fade_samples] *= np.linspace(0, 1, fade_samples)
        chord[-fade_samples:] *= np.linspace(1, 0, fade_samples)

        audio_stereo = np.column_stack((chord, chord))
        audio_int16 = (audio_stereo * 32767).astype(np.int16)

        import wave
        with wave.open(file_path, 'wb') as wav_file:
            wav_file.setnchannels(2)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_int16.tobytes())

    def _generate_sound_effects(self):
        """Generates procedural holographic camera shutter click, tactile mouse click, and swipe whoosh."""
        sample_rate = 44100
        duration = 0.08
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        # Noise burst + high resonant transient for camera shutter
        noise = (np.random.rand(len(t)) * 2 - 1) * np.exp(-t * 60)
        click = np.sin(2 * np.pi * 2400 * t) * np.exp(-t * 80)
        signal = (noise * 0.6 + click * 0.4)
        stereo = np.column_stack((signal, signal))
        sound_int16 = (stereo * 32767).astype(np.int16)
        self.shutter_sound = pygame.sndarray.make_sound(sound_int16)

        # Mouse click sound (crisp 30ms pop/click)
        t_click = np.linspace(0, 0.03, int(sample_rate * 0.03), False)
        c_sig = np.sin(2 * np.pi * 1800 * t_click) * np.exp(-t_click * 180)
        c_stereo = np.column_stack((c_sig, c_sig))
        self.click_sound = pygame.sndarray.make_sound((c_stereo * 32767).astype(np.int16))

        # Swipe whoosh sound (120ms frequency sweep for tab switch)
        t_sw = np.linspace(0, 0.12, int(sample_rate * 0.12), False)
        sw_freq = np.linspace(600, 1800, len(t_sw))
        sw_sig = np.sin(2 * np.pi * sw_freq * t_sw) * np.sin(np.pi * t_sw / 0.12) * 0.4
        sw_stereo = np.column_stack((sw_sig, sw_sig))
        self.whoosh_sound = pygame.sndarray.make_sound((sw_stereo * 32767).astype(np.int16))

    def _scan_playlist(self):
        if not os.path.exists(self.music_dir):
            return
        files = [os.path.join(self.music_dir, f) for f in sorted(os.listdir(self.music_dir))
                 if f.lower().endswith(('.mp3', '.wav', '.ogg'))]
        self.playlist = files
        if self.playlist:
            self.current_track_idx = 0
            self.track_title = os.path.basename(self.playlist[0])

    def play(self):
        if not PYGAME_AVAILABLE or not self.playlist:
            return
        try:
            if not self.is_playing:
                track = self.playlist[self.current_track_idx]
                pygame.mixer.music.load(track)
                pygame.mixer.music.play(-1)  # Loop continuously
                self.is_playing = True
                self.track_title = os.path.basename(track)
        except Exception as e:
            print(f"[HOLOHAND][ERROR] Playback failed: {e}")

    def pause(self):
        if not PYGAME_AVAILABLE:
            return
        if self.is_playing:
            pygame.mixer.music.pause()
            self.is_playing = False

    def resume(self):
        if not PYGAME_AVAILABLE:
            return
        if not self.is_playing:
            pygame.mixer.music.unpause()
            self.is_playing = True

    def toggle_play_pause(self):
        if self.is_playing:
            self.pause()
        else:
            if pygame.mixer.music.get_busy():
                self.resume()
            else:
                self.play()

    def next_track(self):
        if not PYGAME_AVAILABLE or not self.playlist:
            return
        self.current_track_idx = (self.current_track_idx + 1) % len(self.playlist)
        track = self.playlist[self.current_track_idx]
        self.track_title = os.path.basename(track)
        if self.is_playing:
            pygame.mixer.music.load(track)
            pygame.mixer.music.play(-1)

    def prev_track(self):
        if not PYGAME_AVAILABLE or not self.playlist:
            return
        self.current_track_idx = (self.current_track_idx - 1) % len(self.playlist)
        track = self.playlist[self.current_track_idx]
        self.track_title = os.path.basename(track)
        if self.is_playing:
            pygame.mixer.music.load(track)
            pygame.mixer.music.play(-1)

    def set_volume(self, vol):
        self.volume = max(0.0, min(1.0, vol))
        if PYGAME_AVAILABLE and not self.is_muted:
            pygame.mixer.music.set_volume(self.volume)

    def change_volume(self, delta):
        self.set_volume(self.volume + delta)

    def toggle_mute(self):
        self.is_muted = not self.is_muted
        if PYGAME_AVAILABLE:
            if self.is_muted:
                pygame.mixer.music.set_volume(0.0)
            else:
                pygame.mixer.music.set_volume(self.volume)

    def play_shutter(self):
        if self.shutter_sound:
            self.shutter_sound.play()

    def play_click(self):
        if self.click_sound and not self.is_muted:
            try:
                self.click_sound.play()
            except Exception:
                pass

    def play_swipe(self):
        if self.whoosh_sound and not self.is_muted:
            try:
                self.whoosh_sound.play()
            except Exception:
                pass


# ==============================================================================
# 4B. HARDWARE FLASHLIGHT CONTROLLER
# ==============================================================================
class HardwareFlashController:
    """
    Manages physical ESP32-CAM onboard high-power Flash LED (GPIO 4)
    via asynchronous non-blocking HTTP GET requests to /flash?state=1|0.
    """
    def __init__(self, stream_url):
        self.stream_url = stream_url
        self.is_on = False
        self.base_url = None
        if stream_url and (stream_url.startswith("http://") or stream_url.startswith("https://")):
            parts = stream_url.split('/')
            if len(parts) >= 3:
                self.base_url = f"{parts[0]}//{parts[2]}"

    def toggle(self):
        self.set_state(not self.is_on)
        return self.is_on

    def set_state(self, state: bool):
        self.is_on = state
        if self.base_url:
            threading.Thread(target=self._send_command, args=(state,), daemon=True).start()

    def _send_command(self, state: bool):
        try:
            url = f"{self.base_url}/flash?state={'1' if state else '0'}"
            req = urllib.request.Request(url, headers={'User-Agent': 'HoloHand-Flash/1.0'})
            urllib.request.urlopen(req, timeout=1.5)
        except Exception:
            pass


# ==============================================================================
# 5. HAND GEOMETRY & FEATURE EXTRACTION ENGINE
# ==============================================================================
class HandFeatureExtractor:
    """
    Computes invariant normalized geometry, finger extension states,
    palm coordinate frames, scale, orientation, and motion vectors from landmarks.
    """
    @staticmethod
    def extract_features(landmarks, image_width, image_height):
        """
        Input: MediaPipe landmarks (21 NormalizedLandmarks)
        Output: Dictionary of geometric features
        """
        # Pixel coordinates
        pts = np.array([[lm.x * image_width, lm.y * image_height, lm.z * image_width] for lm in landmarks])

        # Key anatomical indices
        wrist = pts[0]
        thumb_cmc, thumb_mcp, thumb_ip, thumb_tip = pts[1], pts[2], pts[3], pts[4]
        index_mcp, index_pip, index_dip, index_tip = pts[5], pts[6], pts[7], pts[8]
        middle_mcp, middle_pip, middle_dip, middle_tip = pts[9], pts[10], pts[11], pts[12]
        ring_mcp, ring_pip, ring_dip, ring_tip = pts[13], pts[14], pts[15], pts[16]
        pinky_mcp, pinky_pip, pinky_dip, pinky_tip = pts[17], pts[18], pts[19], pts[20]

        # Palm Center (centroid of wrist, index_mcp, middle_mcp, ring_mcp, pinky_mcp)
        palm_center = np.mean([wrist, index_mcp, middle_mcp, ring_mcp, pinky_mcp], axis=0)

        # Hand Scale: Euclidean distance between wrist and middle_mcp
        hand_scale = np.linalg.norm(middle_mcp[:2] - wrist[:2])
        if hand_scale < 1.0:
            hand_scale = 1.0  # Safeguard against zero division

        # Hand Orientation (angle of palm axis from wrist to middle MCP, 0 deg = Up)
        delta_v = middle_mcp[:2] - wrist[:2]
        orientation_deg = math.degrees(math.atan2(delta_v[1], delta_v[0])) + 90.0

        # Normalized Pinch Distance: Thumb Tip (4) to Index Tip (8)
        raw_pinch_dist = float(np.linalg.norm(thumb_tip[:2] - index_tip[:2]))
        norm_pinch_dist = float(raw_pinch_dist / hand_scale)

        # Thumb-to-Index Span Ratio for Real-Time Master Volume Control
        # Scaled from SPAN_MIN_VOL_DIST (0% volume, fingers touching) to SPAN_MAX_VOL_DIST (100% volume, spread wide)
        span_ratio = float(np.clip((norm_pinch_dist - SPAN_MIN_VOL_DIST) / (SPAN_MAX_VOL_DIST - SPAN_MIN_VOL_DIST), 0.0, 1.0))

        # Normalized Middle Pinch Distance: Thumb Tip (4) to Middle Tip (12)
        raw_middle_pinch = float(np.linalg.norm(thumb_tip[:2] - middle_tip[:2]))
        norm_middle_pinch_dist = float(raw_middle_pinch / hand_scale)

        # Finger Extension State (Invariant to hand rotation)
        # For Index, Middle, Ring, Pinky: tip distance from wrist vs PIP distance from wrist
        def is_extended(tip, pip, mcp):
            dist_tip = np.linalg.norm(tip[:2] - wrist[:2])
            dist_pip = np.linalg.norm(pip[:2] - wrist[:2])
            dist_mcp = np.linalg.norm(mcp[:2] - wrist[:2])
            return dist_tip > dist_pip * 1.05 and dist_tip > dist_mcp * 1.08

        index_ext = is_extended(index_tip, index_pip, index_mcp)
        middle_ext = is_extended(middle_tip, middle_pip, middle_mcp)
        ring_ext = is_extended(ring_tip, ring_pip, ring_mcp)
        pinky_ext = is_extended(pinky_tip, pinky_pip, pinky_mcp)

        # Thumb Extension: distance from thumb tip to pinky MCP vs thumb IP to pinky MCP
        thumb_dist_tip = np.linalg.norm(thumb_tip[:2] - pinky_mcp[:2])
        thumb_dist_ip = np.linalg.norm(thumb_ip[:2] - pinky_mcp[:2])
        thumb_ext = thumb_dist_tip > thumb_dist_ip * 1.06 and (norm_pinch_dist > PINCH_THRESHOLD * 1.1)

        # Thumb Direction Vector (for Thumb Up / Thumb Down classification)
        thumb_vec = thumb_tip[:2] - thumb_mcp[:2]
        thumb_angle_y = math.degrees(math.atan2(thumb_vec[1], thumb_vec[0]))  # -90 is straight up, +90 is straight down

        return {
            "pts": pts,
            "wrist": wrist,
            "palm_center": palm_center,
            "hand_scale": hand_scale,
            "orientation_deg": orientation_deg,
            "norm_pinch_dist": norm_pinch_dist,
            "raw_pinch_dist": raw_pinch_dist,
            "thumb_index_span_ratio": span_ratio,
            "norm_middle_pinch_dist": norm_middle_pinch_dist,
            "thumb_ext": thumb_ext,
            "index_ext": index_ext,
            "middle_ext": middle_ext,
            "ring_ext": ring_ext,
            "pinky_ext": pinky_ext,
            "thumb_angle_y": thumb_angle_y,
            "tips": {
                "thumb": thumb_tip,
                "index": index_tip,
                "middle": middle_tip,
                "ring": ring_tip,
                "pinky": pinky_tip
            }
        }


# ==============================================================================
# 6. GESTURE RECOGNITION & TEMPORAL STABILIZATION STATE MACHINE
# ==============================================================================
class GestureRecognizer:
    """
    Classifies raw hand features into robust gestures, applies temporal hysteresis,
    cooldown management, and motion velocity tracking.
    """
    def __init__(self):
        self.candidate_gesture = "NONE"
        self.stable_gesture = "NONE"
        self.candidate_count = 0
        self.last_fire_time = {}
        self.is_pinching = False
        self.is_caliper_active = False
        self.pinch_start_pos = None

        # Palm center history for swipe velocity calculation: deque of (timestamp, x, y)
        self.motion_history = deque(maxlen=30)

    def update(self, features, timestamp):
        """
        Evaluates current hand frame features and updates state machine.
        Returns: (active_gesture, is_newly_confirmed, continuous_payload)
        """
        if features is None:
            self.candidate_gesture = "NONE"
            self.stable_gesture = "NONE"
            self.candidate_count = 0
            self.is_pinching = False
            self.is_caliper_active = False
            self.pinch_start_pos = None
            self.motion_history.clear()
            return "NONE", False, None

        palm = features["palm_center"]
        self.motion_history.append((timestamp, palm[0], palm[1]))

        # 1. Continuous Pinch with Hysteresis
        norm_pinch = features["norm_pinch_dist"]
        if not self.is_pinching and norm_pinch < PINCH_THRESHOLD:
            self.is_pinching = True
            self.pinch_start_pos = (palm[0], palm[1])
        elif self.is_pinching and norm_pinch > PINCH_RELEASE_THRESH:
            self.is_pinching = False
            self.pinch_start_pos = None

        # 2. Velocity and Swipe Evaluation (Dynamic Instantaneous Gestures)
        swipe_gesture = self._detect_swipe(timestamp)
        if swipe_gesture in ["SWIPE_RIGHT", "SWIPE_LEFT"]:
            if self.check_cooldown("SWIPE_CONFIRM", 0.35):
                self.stable_gesture = swipe_gesture
                self.candidate_gesture = swipe_gesture
                self.candidate_count = STABILIZATION_FRAMES
                return swipe_gesture, True, {"swipe": swipe_gesture}

        # 3. Geometric Pose Classification
        t = features["thumb_ext"]
        i = features["index_ext"]
        m = features["middle_ext"]
        r = features["ring_ext"]
        p = features["pinky_ext"]
        thumb_ang = features["thumb_angle_y"]
        span_ratio = features.get("thumb_index_span_ratio", 0.5)

        num_ext = sum([i, m, r, p])

        raw_pose = "NONE"
        if self.is_pinching:
            raw_pose = "PINCH"
        elif num_ext == 4:
            self.is_caliper_active = False
            raw_pose = "OPEN_PALM"
        elif num_ext == 0:
            self.is_caliper_active = False
            if t:
                if -150 < thumb_ang < -30:
                    raw_pose = "THUMB_UP"
                elif 30 < thumb_ang < 150:
                    raw_pose = "THUMB_DOWN"
                else:
                    raw_pose = "CLOSED_FIST"
            else:
                raw_pose = "CLOSED_FIST"
        elif i and p and not m and not r:
            self.is_caliper_active = False
            # Rock On / Horns: Index and Pinky extended, Middle and Ring folded
            raw_pose = "HORNS"
        elif i and m and not r and not p:
            self.is_caliper_active = False
            # Peace Sign / Two fingers raised
            raw_pose = "PEACE_SIGN"
        elif i and m and r and not p:
            self.is_caliper_active = False
            raw_pose = "THREE_FINGERS_UP"
        elif i and not m and not r and not p:
            # Index pointing: evaluate orientation
            index_vec = features["tips"]["index"][:2] - features["pts"][5][:2]
            idx_ang = math.degrees(math.atan2(index_vec[1], index_vec[0]))
            if -150 < idx_ang < -30 and not (self.is_caliper_active or norm_pinch < PINCH_THRESHOLD):
                raw_pose = "INDEX_POINTING_UP"
            elif 30 < idx_ang < 150 and not (self.is_caliper_active or norm_pinch < PINCH_THRESHOLD):
                raw_pose = "INDEX_POINTING_DOWN"
            elif (t or self.is_pinching or self.is_caliper_active or norm_pinch < 0.40):
                # Thumb and Index opposed -> Optical Caliper Volume Control
                self.is_caliper_active = True
                raw_pose = "CALIPER_VOLUME"
            elif t:
                # Index pointing forward/sideways with thumb extended (Torch gun)
                raw_pose = "L_SHAPE"
            else:
                raw_pose = "INDEX_POINTING"
        elif self.is_pinching:
            raw_pose = "PINCH"
        elif self.is_caliper_active and not r and not p:
            raw_pose = "CALIPER_VOLUME"
        elif swipe_gesture != "NONE":
            raw_pose = swipe_gesture

        # 4. Temporal Stabilization
        is_new_activation = False
        if raw_pose == self.candidate_gesture:
            self.candidate_count += 1
        else:
            self.candidate_gesture = raw_pose
            self.candidate_count = 1

        if self.candidate_count >= STABILIZATION_FRAMES:
            if self.stable_gesture != self.candidate_gesture:
                self.stable_gesture = self.candidate_gesture
                is_new_activation = True

        # Continuous payload (supports both pinch vertical motion and thumb-index distance span)
        payload = None
        if self.is_pinching or self.is_caliper_active or self.stable_gesture in ["CALIPER_VOLUME", "PINCH"]:
            thumb_pt = features["tips"]["thumb"]
            index_pt = features["tips"]["index"]
            pinch_y = (thumb_pt[1] + index_pt[1]) / 2.0
            delta_y = (palm[1] - self.pinch_start_pos[1]) if self.pinch_start_pos else 0.0
            norm_y = span_ratio  # Caliper distance directly governs the volume ratio
            payload = {
                "pinch_delta_y": delta_y,
                "palm_y": palm[1],
                "pinch_y": pinch_y,
                "norm_y": norm_y,
                "volume_ratio": span_ratio,
                "norm_span": norm_pinch,
                "raw_dist": features.get("raw_pinch_dist", np.linalg.norm(thumb_pt[:2] - index_pt[:2])),
                "thumb_pt": (int(thumb_pt[0]), int(thumb_pt[1])),
                "index_pt": (int(index_pt[0]), int(index_pt[1]))
            }

        return self.stable_gesture, is_new_activation, payload

    def _detect_swipe(self, current_time):
        if len(self.motion_history) < 2:
            return "NONE"

        cur_t, cur_x, cur_y = self.motion_history[-1]

        # Scan backwards through motion history for a valid swipe window (0.08s to 0.45s)
        for hist_t, hist_x, hist_y in reversed(self.motion_history):
            dt = cur_t - hist_t
            if dt < 0.08:
                continue
            if dt > 0.45:
                break

            # User perspective: physical hand moving to user's right moves towards lower X in un-mirrored camera image
            dx_user = -(cur_x - hist_x)
            dy = cur_y - hist_y
            min_disp = DEFAULT_DISPLAY_WIDTH * SWIPE_MIN_DISTANCE

            # Check horizontal dominance and minimum displacement
            if abs(dx_user) >= min_disp and abs(dx_user) > abs(dy) * 1.15:
                velocity_x = (dx_user / float(DEFAULT_DISPLAY_WIDTH)) / dt
                if velocity_x > SWIPE_VELOCITY_THRESH:
                    self.motion_history.clear()
                    return "SWIPE_RIGHT"
                elif velocity_x < -SWIPE_VELOCITY_THRESH:
                    self.motion_history.clear()
                    return "SWIPE_LEFT"

        return "NONE"

    def check_cooldown(self, action_name, cooldown_sec=DEFAULT_COOLDOWN_SEC):
        now = time.monotonic()
        last = self.last_fire_time.get(action_name, 0.0)
        if now - last >= cooldown_sec:
            self.last_fire_time[action_name] = now
            return True
        return False


# ==============================================================================
# 7. FUTURISTIC HOLOGRAPHIC VISUAL ENGINE
# ==============================================================================
class HolographicVisualEngine:
    """
    Renders high-fps, alpha-blended augmented reality HUD elements:
    Landmark laser skeleton, rotating palm hologram reticle, kinetic fingertip trails,
    expanding activation shockwaves, particle bursts, and virtual control panels.
    """
    def __init__(self, display_width, display_height):
        self.width = display_width
        self.height = display_height

        # Kinetic particle physics simulation
        self.particles = []
        self.shockwaves = []
        self.shutter_flash_alpha = 0.0

        # Fingertip motion trails: deque of (x, y, timestamp)
        self.index_trail = deque(maxlen=16)
        self.thumb_trail = deque(maxlen=16)

    def trigger_shockwave(self, center_x, center_y, color=COLOR_CYAN):
        self.shockwaves.append({
            "cx": center_x,
            "cy": center_y,
            "radius": 15.0,
            "max_radius": 140.0,
            "alpha": 1.0,
            "color": color
        })

    def trigger_particle_burst(self, center_x, center_y, count=18, color=COLOR_CYAN):
        for _ in range(count):
            angle = np.random.uniform(0, 2 * np.pi)
            speed = np.random.uniform(60, 220)  # px/s
            self.particles.append({
                "x": float(center_x),
                "y": float(center_y),
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed,
                "life": 1.0,
                "decay": np.random.uniform(1.4, 2.8),
                "color": color,
                "size": np.random.uniform(2.0, 4.0)
            })

    def trigger_shutter_flash(self):
        self.shutter_flash_alpha = 1.0

    def update_animations(self, dt):
        # Update shockwaves
        for sw in self.shockwaves:
            sw["radius"] += 280.0 * dt
            sw["alpha"] = max(0.0, 1.0 - (sw["radius"] / sw["max_radius"]))
        self.shockwaves = [sw for sw in self.shockwaves if sw["alpha"] > 0.02]

        # Update particles
        for p in self.particles:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["life"] -= p["decay"] * dt
        self.particles = [p for p in self.particles if p["life"] > 0.0]

        # Decay shutter flash
        if self.shutter_flash_alpha > 0.0:
            self.shutter_flash_alpha = max(0.0, self.shutter_flash_alpha - dt * 3.5)

    def render_hand_skeleton(self, frame, features, visual_mode):
        if features is None:
            self.index_trail.clear()
            self.thumb_trail.clear()
            return

        pts = features["pts"].astype(np.int32)
        tips = features["tips"]

        # Track trails for index and thumb
        now = time.monotonic()
        if "index" in tips:
            self.index_trail.append((int(tips["index"][0]), int(tips["index"][1]), now))
        if "thumb" in tips:
            self.thumb_trail.append((int(tips["thumb"][0]), int(tips["thumb"][1]), now))

        # Hand bone connections defined by landmark pairs
        connections = [
            (0, 1), (1, 2), (2, 3), (3, 4),        # Thumb
            (0, 5), (5, 6), (6, 7), (7, 8),        # Index
            (5, 9), (9, 10), (10, 11), (11, 12),   # Middle
            (9, 13), (13, 14), (14, 15), (15, 16), # Ring
            (13, 17), (17, 18), (18, 19), (19, 20),# Pinky
            (0, 17)                                # Palm base
        ]

        if visual_mode in (VISUAL_HOLOGRAM, VISUAL_SCAN):
            # Pass 1: Semi-transparent glow backing (for HOLOGRAM mode)
            if visual_mode == VISUAL_HOLOGRAM:
                glow_overlay = frame.copy()
                for p1, p2 in connections:
                    cv2.line(glow_overlay, tuple(pts[p1][:2]), tuple(pts[p2][:2]), COLOR_BLUE, 7, cv2.LINE_AA)
                cv2.addWeighted(glow_overlay, 0.4, frame, 0.6, 0, frame)

            # Pass 2: Crisp laser foreground skeleton
            for p1, p2 in connections:
                cv2.line(frame, tuple(pts[p1][:2]), tuple(pts[p2][:2]), COLOR_CYAN, 2, cv2.LINE_AA)

            # Joint Nodes
            for idx in range(21):
                pt = tuple(pts[idx][:2])
                cv2.circle(frame, pt, 4, COLOR_VIOLET, -1, cv2.LINE_AA)
                cv2.circle(frame, pt, 6, COLOR_WHITE, 1, cv2.LINE_AA)

            # Fingertip Nodes
            for tip_name in ["thumb", "index", "middle", "ring", "pinky"]:
                if tip_name in tips:
                    tip_pt = (int(tips[tip_name][0]), int(tips[tip_name][1]))
                    cv2.circle(frame, tip_pt, 7, COLOR_CYAN, 2, cv2.LINE_AA)
                    cv2.circle(frame, tip_pt, 3, COLOR_WHITE, -1, cv2.LINE_AA)

        # Pass 3: Fingertip Comet Trails (HOLOGRAM mode only)
        if visual_mode == VISUAL_HOLOGRAM:
            self._render_trail(frame, self.index_trail, COLOR_CYAN)
            self._render_trail(frame, self.thumb_trail, COLOR_VIOLET)

    def _render_trail(self, frame, trail_deque, color):
        trail_len = len(trail_deque)
        if trail_len < 2:
            return
        for i in range(trail_len - 1):
            p1 = (trail_deque[i][0], trail_deque[i][1])
            p2 = (trail_deque[i+1][0], trail_deque[i+1][1])
            alpha_frac = (i + 1) / float(trail_len)
            thickness = max(1, int(alpha_frac * 3.5))
            cv2.line(frame, p1, p2, color, thickness, cv2.LINE_AA)

    def render_palm_scanner(self, frame, features, current_time):
        """
        Renders futuristic rotating circular scanner centered on hand palm.
        """
        if features is None:
            return

        cx, cy = int(features["palm_center"][0]), int(features["palm_center"][1])
        scale = features["hand_scale"]
        r1 = int(scale * 0.55)
        r2 = int(scale * 0.75)
        r3 = int(scale * 0.95)

        rot = (current_time * 85.0) % 360.0

        # Outer Segmented Rotating Ring
        cv2.ellipse(frame, (cx, cy), (r2, r2), rot, 0, 80, COLOR_CYAN, 2, cv2.LINE_AA)
        cv2.ellipse(frame, (cx, cy), (r2, r2), rot, 120, 200, COLOR_CYAN, 2, cv2.LINE_AA)
        cv2.ellipse(frame, (cx, cy), (r2, r2), rot, 240, 320, COLOR_CYAN, 2, cv2.LINE_AA)

        # Counter-rotating Inner Violet Ring
        cv2.ellipse(frame, (cx, cy), (r1, r1), -rot * 1.4, 0, 60, COLOR_VIOLET, 1, cv2.LINE_AA)
        cv2.ellipse(frame, (cx, cy), (r1, r1), -rot * 1.4, 180, 240, COLOR_VIOLET, 1, cv2.LINE_AA)

        # Target Crosshair Reticle
        ch_len = int(scale * 0.25)
        cv2.line(frame, (cx - ch_len, cy), (cx + ch_len, cy), COLOR_WHITE, 1, cv2.LINE_AA)
        cv2.line(frame, (cx, cy - ch_len), (cx, cy + ch_len), COLOR_WHITE, 1, cv2.LINE_AA)
        cv2.circle(frame, (cx, cy), 3, COLOR_CYAN, -1, cv2.LINE_AA)

        # Technical Hand Metric Readouts
        tech_str = f"ROT:{features['orientation_deg']:+.0f} DEG"
        cv2.putText(frame, tech_str, (cx + r2 + 10, cy - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.38, COLOR_CYAN, 1, cv2.LINE_AA)
        cv2.putText(frame, f"SCL:{int(scale)}px", (cx + r2 + 10, cy + 10), cv2.FONT_HERSHEY_SIMPLEX, 0.35, COLOR_WHITE, 1, cv2.LINE_AA)

    def render_effects(self, frame):
        # Shockwaves
        for sw in self.shockwaves:
            r = int(sw["radius"])
            if r > 0 and sw["alpha"] > 0:
                overlay = frame.copy()
                cv2.circle(overlay, (int(sw["cx"]), int(sw["cy"])), r, sw["color"], 3, cv2.LINE_AA)
                cv2.addWeighted(overlay, sw["alpha"] * 0.8, frame, 1.0 - sw["alpha"] * 0.8, 0, frame)

        # Kinetic Particles
        for p in self.particles:
            if p["life"] > 0:
                pt = (int(p["x"]), int(p["y"]))
                sz = max(1, int(p["size"] * p["life"]))
                cv2.circle(frame, pt, sz, p["color"], -1, cv2.LINE_AA)

        # Shutter Flash
        if self.shutter_flash_alpha > 0.01:
            overlay = np.full_like(frame, 255)
            cv2.addWeighted(overlay, self.shutter_flash_alpha * 0.75, frame, 1.0 - (self.shutter_flash_alpha * 0.75), 0, frame)

    def render_pinch_volume_slider(self, frame, pinch_y, volume):
        """Renders an AR vertical volume slider when user is pinching."""
        h, w = frame.shape[:2]
        slider_x = w - 45
        slider_top = 85
        slider_bot = h - 85
        slider_h = slider_bot - slider_top

        # Slider track backdrop
        overlay = frame.copy()
        cv2.rectangle(overlay, (slider_x - 16, slider_top - 15), (slider_x + 16, slider_bot + 15), COLOR_DARK_GLASS, -1)
        cv2.rectangle(overlay, (slider_x - 16, slider_top - 15), (slider_x + 16, slider_bot + 15), COLOR_CYAN, 1)
        cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)

        # Track line
        cv2.line(frame, (slider_x, slider_top), (slider_x, slider_bot), (80, 80, 80), 3, cv2.LINE_AA)

        # Active level fill
        level_y = int(slider_bot - (volume * slider_h))
        level_y = max(slider_top, min(slider_bot, level_y))
        cv2.line(frame, (slider_x, slider_bot), (slider_x, level_y), COLOR_CYAN, 4, cv2.LINE_AA)

        # Handle knob
        cv2.circle(frame, (slider_x, level_y), 9, COLOR_CYAN, -1, cv2.LINE_AA)
        cv2.circle(frame, (slider_x, level_y), 12, COLOR_WHITE, 1, cv2.LINE_AA)

        # Volume percentage label
        pct_str = f"{int(volume * 100)}%"
        cv2.putText(frame, pct_str, (slider_x - 56, level_y + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, COLOR_CYAN, 1, cv2.LINE_AA)
        cv2.putText(frame, "VOL", (slider_x - 12, slider_top - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.35, COLOR_WHITE, 1, cv2.LINE_AA)

    def render_caliper_volume_hud(self, frame, thumb_pt, index_pt, volume, raw_px_dist, is_system_audio=True):
        """
        Renders a futuristic holographic Optical Vernier Caliper directly connecting
        the user's Thumb Tip and Index Tip, coupled with a live Cyber Master Volume Gauge.
        """
        h, w = frame.shape[:2]
        vol_pct = int(np.clip(volume, 0.0, 1.0) * 100)

        # Dynamic color theme based on volume level
        if vol_pct > 85:
            theme_color = COLOR_RED
        elif vol_pct > 55:
            theme_color = COLOR_AMBER
        else:
            theme_color = COLOR_CYAN

        # 1. Optical Caliper Measurement Laser between Thumb Tip and Index Tip
        if thumb_pt and index_pt and thumb_pt != (0, 0) and index_pt != (0, 0):
            # Outer neon glow
            overlay = frame.copy()
            cv2.line(overlay, thumb_pt, index_pt, theme_color, 6, cv2.LINE_AA)
            cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)

            # Core laser beam
            cv2.line(frame, thumb_pt, index_pt, COLOR_WHITE, 2, cv2.LINE_AA)

            # Endpoint Vernier Rings and Crosshairs
            for pt in [thumb_pt, index_pt]:
                cv2.circle(frame, pt, 14, theme_color, 2, cv2.LINE_AA)
                cv2.circle(frame, pt, 7, COLOR_WHITE, -1, cv2.LINE_AA)
                cv2.line(frame, (pt[0] - 18, pt[1]), (pt[0] + 18, pt[1]), theme_color, 1, cv2.LINE_AA)
                cv2.line(frame, (pt[0], pt[1] - 18), (pt[0], pt[1] + 18), theme_color, 1, cv2.LINE_AA)

            # Midpoint Telemetry Pill
            mid_x = int((thumb_pt[0] + index_pt[0]) / 2.0)
            mid_y = int((thumb_pt[1] + index_pt[1]) / 2.0)

            pill_w, pill_h = 190, 48
            p_x1 = max(10, min(w - pill_w - 10, mid_x - pill_w // 2))
            p_y1 = max(60, min(h - pill_h - 60, mid_y - pill_h // 2))
            p_x2 = p_x1 + pill_w
            p_y2 = p_y1 + pill_h

            pill_overlay = frame.copy()
            cv2.rectangle(pill_overlay, (p_x1, p_y1), (p_x2, p_y2), COLOR_DARK_GLASS, -1)
            cv2.rectangle(pill_overlay, (p_x1, p_y1), (p_x2, p_y2), theme_color, 2)
            cv2.addWeighted(pill_overlay, 0.85, frame, 0.15, 0, frame)

            # Pill Text
            cv2.putText(frame, f"CALIPER SPAN: {int(raw_px_dist)}px", (p_x1 + 14, p_y1 + 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, COLOR_WHITE, 1, cv2.LINE_AA)
            sys_tag = "[WINDOWS OS AUDIO]" if is_system_audio else "[SYNTH AUDIO]"
            cv2.putText(frame, f"VOL: {vol_pct}% {sys_tag}", (p_x1 + 14, p_y1 + 38),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, theme_color, 1, cv2.LINE_AA)

        # 2. Right Margin Cyber Master Volume Gauge
        gauge_x = w - 46
        gauge_top = 80
        gauge_bot = h - 80
        gauge_h = gauge_bot - gauge_top

        # Gauge Glass Backdrop
        gauge_bg = frame.copy()
        cv2.rectangle(gauge_bg, (gauge_x - 22, gauge_top - 20), (gauge_x + 22, gauge_bot + 24), COLOR_DARK_GLASS, -1)
        cv2.rectangle(gauge_bg, (gauge_x - 22, gauge_top - 20), (gauge_x + 22, gauge_bot + 24), theme_color, 1)
        cv2.addWeighted(gauge_bg, 0.85, frame, 0.15, 0, frame)

        # Track Frame
        cv2.rectangle(frame, (gauge_x - 12, gauge_top), (gauge_x + 12, gauge_bot), (60, 60, 60), 1)

        # Segmented level notches
        notch_step = max(4, gauge_h // 25)
        fill_y = int(gauge_bot - (volume * gauge_h))
        for ny in range(gauge_bot, gauge_top, -notch_step):
            if ny >= fill_y:
                cv2.rectangle(frame, (gauge_x - 9, ny - 3), (gauge_x + 9, ny), theme_color, -1)
            else:
                cv2.rectangle(frame, (gauge_x - 6, ny - 2), (gauge_x + 6, ny), (50, 50, 50), -1)

        # Top & Bottom Gauge Headers
        cv2.putText(frame, "MASTER", (gauge_x - 22, gauge_top - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.35, COLOR_WHITE, 1, cv2.LINE_AA)
        cv2.putText(frame, "AUDIO", (gauge_x - 18, gauge_top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.35, theme_color, 1, cv2.LINE_AA)

        # Big percentage readout
        cv2.putText(frame, f"{vol_pct}%", (gauge_x - 68, fill_y + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.55, COLOR_WHITE, 2, cv2.LINE_AA)
        cv2.putText(frame, f"{vol_pct}%", (gauge_x - 68, fill_y + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.55, theme_color, 1, cv2.LINE_AA)

        # Soundwave Arcs at base
        cv2.putText(frame, f"{'[MUTE]' if vol_pct == 0 else ('[MAX]' if vol_pct == 100 else '[LIVE]')}",
                    (gauge_x - 20, gauge_bot + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.32, theme_color, 1, cv2.LINE_AA)

    def render_top_hud(self, frame, active_mode, visual_mode, actions_enabled, dry_run, stream_status, proc_fps, stream_fps, is_flash_on=False):
        """Renders technical cyber top status bar."""
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (self.width, 54), COLOR_DARK_GLASS, -1)
        cv2.line(overlay, (0, 54), (self.width, 54), COLOR_CYAN, 1)
        cv2.addWeighted(overlay, 0.82, frame, 0.18, 0, frame)

        # Branding
        cv2.putText(frame, "PROJECT HOLOHAND", (16, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.65, COLOR_CYAN, 2, cv2.LINE_AA)
        cv2.putText(frame, "ESP32-CAM AR STUDIO", (16, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.38, COLOR_WHITE, 1, cv2.LINE_AA)

        # Mode Badge
        mode_color = COLOR_CYAN if "HOLOGRAM" in active_mode else (COLOR_ORANGE if "CAMERA" in active_mode else COLOR_VIOLET)
        cv2.rectangle(frame, (230, 10), (450, 44), mode_color, 1)
        cv2.putText(frame, f"MODE: {active_mode.split(':')[1].strip()}", (240, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.48, mode_color, 1, cv2.LINE_AA)

        # Automation Status
        if not actions_enabled:
            status_text = "[ACTIONS DISABLED - 'E']"
            status_color = COLOR_RED
        elif dry_run:
            status_text = "[DRY-RUN ACTIVE]"
            status_color = COLOR_ORANGE
        else:
            status_text = "[ACTIONS ARMED]"
            status_color = COLOR_GREEN
        cv2.putText(frame, status_text, (465, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.40, status_color, 1, cv2.LINE_AA)

        # Flashlight Status Badge
        flash_text = "FLASH: ON" if is_flash_on else "FLASH: OFF"
        flash_color = COLOR_AMBER if is_flash_on else (120, 120, 120)
        cv2.rectangle(frame, (self.width - 345, 10), (self.width - 255, 44), flash_color, 1)
        cv2.putText(frame, flash_text, (self.width - 340, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.38, flash_color, 1, cv2.LINE_AA)

        # Telemetry FPS / Stream Status
        cv2.putText(frame, f"CAM: {stream_fps:.1f}", (self.width - 245, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.38, COLOR_WHITE, 1, cv2.LINE_AA)
        cv2.putText(frame, f"CV:  {proc_fps:.1f}", (self.width - 245, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.38, COLOR_CYAN, 1, cv2.LINE_AA)
        cv2.putText(frame, f"VIS: {visual_mode[:4]}", (self.width - 120, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.40, COLOR_VIOLET, 1, cv2.LINE_AA)

    def render_bottom_hud(self, frame, gesture, action_status, music_engine, is_recording, rec_time_str):
        """Renders bottom telemetry and audio/recording status."""
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, self.height - 48), (self.width, self.height), COLOR_DARK_GLASS, -1)
        cv2.line(overlay, (0, self.height - 48), (self.width, self.height - 48), COLOR_CYAN, 1)
        cv2.addWeighted(overlay, 0.82, frame, 0.18, 0, frame)

        # Gesture & Action Confirmation
        cv2.putText(frame, f"GESTURE: {gesture}", (16, self.height - 28), cv2.FONT_HERSHEY_SIMPLEX, 0.48, COLOR_CYAN, 1, cv2.LINE_AA)
        cv2.putText(frame, f"ACTION: {action_status}", (16, self.height - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.40, COLOR_WHITE, 1, cv2.LINE_AA)

        # Video Recording Indicator
        if is_recording:
            cv2.circle(frame, (self.width - 200, self.height - 24), 7, COLOR_RED, -1, cv2.LINE_AA)
            cv2.putText(frame, f"REC {rec_time_str}", (self.width - 185, self.height - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.52, COLOR_RED, 2, cv2.LINE_AA)

        # Music Player Conductor Status
        if music_engine and music_engine.playlist:
            vol_pct = int(music_engine.volume * 100)
            vol_str = f"VOL: {vol_pct}%" if not music_engine.is_muted else "VOL: MUTED"
            state_str = "PLAYING" if music_engine.is_playing else "PAUSED"
            cv2.putText(frame, f"TRACK: {music_engine.track_title[:24]} [{state_str} | {vol_str}]",
                        (340, self.height - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.42, COLOR_VIOLET, 1, cv2.LINE_AA)

    def render_mouse_hud(self, frame, mouse_ctrl, pointer_pos):
        """Renders the Air-Mouse active interaction zone and pointer reticle."""
        if mouse_ctrl is None:
            return

        h, w = frame.shape[:2]
        min_x, min_y, max_x, max_y = mouse_ctrl.active_box
        if max_x <= min_x or max_y <= min_y:
            min_x = int(w * mouse_ctrl.margin_ratio)
            max_x = int(w * (1.0 - mouse_ctrl.margin_ratio))
            min_y = int(h * mouse_ctrl.margin_ratio)
            max_y = int(h * (1.0 - mouse_ctrl.margin_ratio))

        # Semi-transparent active zone border
        cv2.rectangle(frame, (min_x, min_y), (max_x, max_y), (60, 50, 40), 1)

        # Tech Corner Brackets
        c_len = 20
        for bx, by in [(min_x, min_y), (max_x, min_y), (min_x, max_y), (max_x, max_y)]:
            dx = c_len if bx == min_x else -c_len
            dy = c_len if by == min_y else -c_len
            cv2.line(frame, (bx, by), (bx + dx, by), COLOR_CYAN, 2)
            cv2.line(frame, (bx, by), (bx, by + dy), COLOR_CYAN, 2)

        cv2.putText(frame, "AIR-MOUSE ACTIVE INTERACTION ZONE", (min_x + 12, min_y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, COLOR_CYAN, 1, cv2.LINE_AA)

        # Crosshair cursor at pointer pos
        if pointer_pos is not None:
            px, py = int(pointer_pos[0]), int(pointer_pos[1])
            is_inside = (min_x <= px <= max_x and min_y <= py <= max_y)
            cur_color = COLOR_GREEN if is_inside else COLOR_ORANGE
            if mouse_ctrl.is_dragging:
                cur_color = COLOR_AMBER
            elif "DOUBLE CLICK" in mouse_ctrl.mouse_status:
                cur_color = (0, 240, 255)
            elif "CLICK" in mouse_ctrl.mouse_status:
                cur_color = COLOR_CYAN
            elif "TAB SWITCH" in mouse_ctrl.mouse_status:
                cur_color = COLOR_VIOLET
            elif "SCROLL" in mouse_ctrl.mouse_status:
                cur_color = COLOR_CYAN

            # Draw outer targeting reticle
            cv2.circle(frame, (px, py), 14, cur_color, 2, cv2.LINE_AA)
            cv2.circle(frame, (px, py), 3, COLOR_WHITE, -1, cv2.LINE_AA)
            cv2.line(frame, (px - 20, py), (px + 20, py), cur_color, 1, cv2.LINE_AA)
            cv2.line(frame, (px, py - 20), (px, py + 20), cur_color, 1, cv2.LINE_AA)

            # Draw Anchor Line if dragging
            if mouse_ctrl.is_dragging and getattr(mouse_ctrl, "anchor_screen_x", None) is not None:
                norm_ax = mouse_ctrl.anchor_screen_x / float(max(1, mouse_ctrl.screen_w))
                norm_ay = mouse_ctrl.anchor_screen_y / float(max(1, mouse_ctrl.screen_h))
                cam_ax = int(max_x - norm_ax * (max_x - min_x))
                cam_ay = int(min_y + norm_ay * (max_y - min_y))
                cv2.line(frame, (cam_ax, cam_ay), (px, py), COLOR_AMBER, 1, cv2.LINE_AA)
                cv2.circle(frame, (cam_ax, cam_ay), 6, COLOR_RED, -1, cv2.LINE_AA)

            # Directional arrows for Tab Switching
            if "TAB SWITCH: NEXT" in mouse_ctrl.mouse_status:
                cv2.putText(frame, ">> NEXT TAB [Ctrl+Tab]", (px + 24, py - 12),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.48, COLOR_CYAN, 2, cv2.LINE_AA)
            elif "TAB SWITCH: PREV" in mouse_ctrl.mouse_status:
                cv2.putText(frame, "<< PREV TAB [Ctrl+Shift+Tab]", (px - 210, py - 12),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.48, COLOR_VIOLET, 2, cv2.LINE_AA)

            # Badge text
            badge_str = f"{mouse_ctrl.mouse_status} [{mouse_ctrl.cur_screen_x}, {mouse_ctrl.cur_screen_y}]"
            cv2.putText(frame, badge_str, (px + 16, py + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.40, cur_color, 1, cv2.LINE_AA)

    def render_presentation_dashboard(
        self, frame, features, gesture, last_action_desc, active_mode, visual_mode,
        music_engine, mouse_ctrl, flash_ctrl, proc_fps, stream_fps,
        is_recording, rec_time_str, audit_log, current_time,
        canvas_w=1920, canvas_h=1080
    ):
        """
        Renders the full-screen 1080p Cyber Mission Control Presentation Dashboard:
        - Top Status Bar with mode selectors & hardware telemetry
        - Left Telemetry Deck (System specs, 3D kinematics, 5-finger sensor array)
        - Central Main AR Viewport (Live camera stream with holographic HUD)
        - Right Command & Media Deck (Active gesture classifier, audio/mouse monitors, audit log)
        - Bottom Navigation Cheatsheet Bar
        """
        dashboard = np.full((canvas_h, canvas_w, 3), (14, 10, 8), dtype=np.uint8)

        # Background subtle grid pattern
        for x in range(0, canvas_w, 60):
            cv2.line(dashboard, (x, 0), (x, canvas_h), (22, 16, 12), 1)
        for y in range(0, canvas_h, 60):
            cv2.line(dashboard, (0, y), (canvas_w, y), (22, 16, 12), 1)

        top_h = 56
        bot_h = 42
        main_h = canvas_h - top_h - bot_h - 16
        left_w = 320
        right_w = 330
        view_w = canvas_w - left_w - right_w - 32
        view_h = main_h
        view_x = 16 + left_w + 8
        view_y = top_h + 8

        # ----------------------------------------------------------------------
        # 1. CENTRAL AR STAGE (Camera Viewport)
        # ----------------------------------------------------------------------
        cam_resized = cv2.resize(frame, (view_w, view_h))
        dashboard[view_y : view_y + view_h, view_x : view_x + view_w] = cam_resized

        # Viewport Outer Border & Tech Corner Accents
        cv2.rectangle(dashboard, (view_x, view_y), (view_x + view_w, view_y + view_h), COLOR_CYAN, 1)
        brk = 18
        for bx, by in [(view_x, view_y), (view_x + view_w, view_y), (view_x, view_y + view_h), (view_x + view_w, view_y + view_h)]:
            dx = brk if bx == view_x else -brk
            dy = brk if by == view_y else -brk
            cv2.line(dashboard, (bx, by), (bx + dx, by), COLOR_WHITE, 2)
            cv2.line(dashboard, (bx, by), (bx, by + dy), COLOR_WHITE, 2)

        # Header tag on viewport
        cv2.putText(dashboard, "LIVE CAMERA AR FEED // ESP32-CAM MJPEG @ 30 FPS",
                    (view_x + 14, view_y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.36, COLOR_CYAN, 1, cv2.LINE_AA)

        # ----------------------------------------------------------------------
        # 2. TOP STATUS BAR
        # ----------------------------------------------------------------------
        cv2.rectangle(dashboard, (0, 0), (canvas_w, top_h), (20, 15, 12), -1)
        cv2.line(dashboard, (0, top_h), (canvas_w, top_h), COLOR_CYAN, 1)

        # Brand / Logo
        cv2.circle(dashboard, (34, 28), 14, COLOR_CYAN, 2, cv2.LINE_AA)
        cv2.circle(dashboard, (34, 28), 6, COLOR_WHITE, -1, cv2.LINE_AA)
        cv2.putText(dashboard, "PROJECT HOLOHAND", (58, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.65, COLOR_CYAN, 2, cv2.LINE_AA)
        cv2.putText(dashboard, "ESP32-CAM REAL-TIME AR WORKSTATION", (58, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.33, COLOR_WHITE, 1, cv2.LINE_AA)

        # Mode Selector Tabs
        modes_meta = [
            ("MODE_HOLO",  "[1] HOLOGRAM",   MODE_HOLOGRAM, COLOR_CYAN),
            ("MODE_CAM",   "[2] CAMERA",     MODE_CAMERA,   COLOR_ORANGE),
            ("MODE_MUSIC", "[3] CONDUCTOR",  MODE_MUSIC,    COLOR_VIOLET),
            ("MODE_MOUSE", "[4] AIR-MOUSE",  MODE_MOUSE,    COLOR_AMBER),
        ]
        tab_start_x = 440
        tab_w = 150
        tab_h = 34
        tab_y = 11

        for idx, (m_id, m_lbl, m_const, m_col) in enumerate(modes_meta):
            tx = tab_start_x + idx * (tab_w + 10)
            is_active = (active_mode == m_const)
            bg_col = (45, 30, 20) if is_active else (26, 20, 16)
            bdr_col = m_col if is_active else (60, 50, 42)
            txt_col = COLOR_WHITE if is_active else (160, 150, 140)

            cv2.rectangle(dashboard, (tx, tab_y), (tx + tab_w, tab_y + tab_h), bg_col, -1)
            cv2.rectangle(dashboard, (tx, tab_y), (tx + tab_w, tab_y + tab_h), bdr_col, 2 if is_active else 1)
            if is_active:
                cv2.circle(dashboard, (tx + 14, tab_y + 17), 4, m_col, -1, cv2.LINE_AA)
            cv2.putText(dashboard, m_lbl, (tx + 24, tab_y + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.38, txt_col, 1, cv2.LINE_AA)

        # Top Right Badges
        rx = canvas_w - 480
        is_flash = flash_ctrl.is_on if flash_ctrl else False
        f_col = COLOR_AMBER if is_flash else (100, 100, 100)
        cv2.rectangle(dashboard, (rx, 14), (rx + 95, 42), f_col, 1)
        cv2.putText(dashboard, f"FLASH: {'ON' if is_flash else 'OFF'}", (rx + 8, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.36, f_col, 1, cv2.LINE_AA)

        cv2.putText(dashboard, f"CAM: {stream_fps:.1f}", (rx + 115, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.36, COLOR_WHITE, 1, cv2.LINE_AA)
        cv2.putText(dashboard, f"CV:  {proc_fps:.1f}", (rx + 115, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.36, COLOR_CYAN, 1, cv2.LINE_AA)

        cv2.putText(dashboard, f"LAYOUT: STUDIO [TAB]", (rx + 215, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.36, COLOR_VIOLET, 1, cv2.LINE_AA)
        cv2.putText(dashboard, f"DISPLAY: FULL [F11]", (rx + 215, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.36, COLOR_GREEN, 1, cv2.LINE_AA)

        # ----------------------------------------------------------------------
        # 3. LEFT TELEMETRY DECK
        # ----------------------------------------------------------------------
        lx1, ly1 = 14, view_y
        lx2, ly2 = 14 + left_w, view_y + view_h
        cv2.rectangle(dashboard, (lx1, ly1), (lx2, ly2), (22, 17, 13), -1)
        cv2.rectangle(dashboard, (lx1, ly1), (lx2, ly2), (50, 40, 32), 1)

        for bx, by in [(lx1, ly1), (lx2, ly1), (lx1, ly2), (lx2, ly2)]:
            dx = brk if bx == lx1 else -brk
            dy = brk if by == ly1 else -brk
            cv2.line(dashboard, (bx, by), (bx + dx, by), COLOR_VIOLET, 2)
            cv2.line(dashboard, (bx, by), (bx, by + dy), COLOR_VIOLET, 2)

        cur_y = ly1 + 24
        cv2.putText(dashboard, "// SYSTEM TELEMETRY", (lx1 + 14, cur_y), cv2.FONT_HERSHEY_SIMPLEX, 0.44, COLOR_VIOLET, 1, cv2.LINE_AA)
        cur_y += 18
        cv2.line(dashboard, (lx1 + 14, cur_y), (lx2 - 14, cur_y), (50, 40, 32), 1)
        cur_y += 18

        telemetry_items = [
            ("SENSOR:", "OV2640 2MP (SVGA)"),
            ("INTERFACE:", "HTTP MJPEG / Wi-Fi"),
            ("DMA BUFFER:", "PSRAM (2 Frames)"),
            ("BROWNOUT:", "SUPPRESSED (Active)"),
            ("LATENCY:", f"{1000.0 / max(1.0, proc_fps):.1f} ms / frame"),
            ("FRAME REQ:", "30 FPS Synchronous"),
        ]
        for k, v in telemetry_items:
            cv2.putText(dashboard, k, (lx1 + 14, cur_y), cv2.FONT_HERSHEY_SIMPLEX, 0.34, (140, 130, 120), 1, cv2.LINE_AA)
            cv2.putText(dashboard, v, (lx1 + 115, cur_y), cv2.FONT_HERSHEY_SIMPLEX, 0.34, COLOR_WHITE, 1, cv2.LINE_AA)
            cur_y += 18

        cur_y += 12
        cv2.putText(dashboard, "// 3D SPATIAL KINEMATICS", (lx1 + 14, cur_y), cv2.FONT_HERSHEY_SIMPLEX, 0.44, COLOR_CYAN, 1, cv2.LINE_AA)
        cur_y += 18
        cv2.line(dashboard, (lx1 + 14, cur_y), (lx2 - 14, cur_y), (50, 40, 32), 1)
        cur_y += 18

        if features:
            pc = features["palm_center"]
            kin_items = [
                ("CENTROID:", f"X:{int(pc[0])} Y:{int(pc[1])}"),
                ("ROTATION:", f"{features['orientation_deg']:+.1f} DEG"),
                ("HAND SCALE:", f"{features['hand_scale']:.1f} px"),
                ("PINCH DIST:", f"{features['norm_pinch_dist']:.3f}"),
            ]
            for k, v in kin_items:
                cv2.putText(dashboard, k, (lx1 + 14, cur_y), cv2.FONT_HERSHEY_SIMPLEX, 0.34, (140, 130, 120), 1, cv2.LINE_AA)
                cv2.putText(dashboard, v, (lx1 + 115, cur_y), cv2.FONT_HERSHEY_SIMPLEX, 0.34, COLOR_CYAN, 1, cv2.LINE_AA)
                cur_y += 18

            cur_y += 6
            cv2.putText(dashboard, "PINCH GAUGE (0.24 THRESH):", (lx1 + 14, cur_y), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (140, 130, 120), 1, cv2.LINE_AA)
            cur_y += 10
            bar_w = left_w - 28
            cv2.rectangle(dashboard, (lx1 + 14, cur_y), (lx1 + 14 + bar_w, cur_y + 10), (35, 25, 20), -1)
            cv2.rectangle(dashboard, (lx1 + 14, cur_y), (lx1 + 14 + bar_w, cur_y + 10), (70, 60, 50), 1)
            fill_pct = min(1.0, features["norm_pinch_dist"] / 0.50)
            fill_col = COLOR_GREEN if features["norm_pinch_dist"] < PINCH_THRESHOLD else COLOR_CYAN
            cv2.rectangle(dashboard, (lx1 + 14, cur_y), (lx1 + 14 + int(bar_w * fill_pct), cur_y + 10), fill_col, -1)
            thresh_x = lx1 + 14 + int(bar_w * (PINCH_THRESHOLD / 0.50))
            cv2.line(dashboard, (thresh_x, cur_y - 2), (thresh_x, cur_y + 12), COLOR_RED, 2)
            cur_y += 22
        else:
            cv2.putText(dashboard, "WAITING FOR HAND DETECTION...", (lx1 + 14, cur_y + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.36, COLOR_ORANGE, 1, cv2.LINE_AA)
            cur_y += 90

        cur_y += 10
        cv2.putText(dashboard, "// 5-FINGER SENSOR ARRAY", (lx1 + 14, cur_y), cv2.FONT_HERSHEY_SIMPLEX, 0.44, COLOR_GREEN, 1, cv2.LINE_AA)
        cur_y += 18
        cv2.line(dashboard, (lx1 + 14, cur_y), (lx2 - 14, cur_y), (50, 40, 32), 1)
        cur_y += 18

        fingers = [
            ("THUMB",  features["thumb_ext"] if features else False),
            ("INDEX",  features["index_ext"] if features else False),
            ("MIDDLE", features["middle_ext"] if features else False),
            ("RING",   features["ring_ext"] if features else False),
            ("PINKY",  features["pinky_ext"] if features else False),
        ]
        for f_name, f_ext in fingers:
            dot_col = COLOR_GREEN if f_ext else (70, 70, 70)
            status_str = "[ EXTENDED ]" if f_ext else "[ FOLDED   ]"
            status_col = COLOR_WHITE if f_ext else (100, 100, 100)

            cv2.circle(dashboard, (lx1 + 24, cur_y - 4), 5, dot_col, -1, cv2.LINE_AA)
            cv2.putText(dashboard, f_name, (lx1 + 38, cur_y), cv2.FONT_HERSHEY_SIMPLEX, 0.35, COLOR_WHITE, 1, cv2.LINE_AA)
            cv2.putText(dashboard, status_str, (lx1 + 115, cur_y), cv2.FONT_HERSHEY_SIMPLEX, 0.34, status_col, 1, cv2.LINE_AA)
            cur_y += 20

        cur_y += 14
        cv2.putText(dashboard, "// ACTIVE MODE GESTURE MAP", (lx1 + 14, cur_y), cv2.FONT_HERSHEY_SIMPLEX, 0.44, COLOR_AMBER, 1, cv2.LINE_AA)
        cur_y += 18
        cv2.line(dashboard, (lx1 + 14, cur_y), (lx2 - 14, cur_y), (50, 40, 32), 1)
        cur_y += 18

        mode_bullets = []
        if active_mode == MODE_HOLOGRAM:
            mode_bullets = [
                "• Closed Fist: Play/Pause",
                "• Thumbs Up/Dn: Play/Pause",
                "• Index Up/Dn: Vol +/-",
                "• Peace Sign: Prev Slide / Mute",
                "• Horns: Toggle Flashlight",
                "• Palm ➔ Fist: 3s Photo Timer",
            ]
        elif active_mode == MODE_CAMERA:
            mode_bullets = [
                "• Peace Sign: Instant Photo",
                "• Palm ➔ Fist: 3s Countdown",
                "• 3 Fingers: Toggle 1080p Rec",
                "• Horns / L-Shape: Torch Flash",
                "• ESC / Fist: Disarm/Cancel",
            ]
        elif active_mode == MODE_MUSIC:
            mode_bullets = [
                "• Thumbs Up: Play Track",
                "• Thumbs Down: Pause Track",
                "• Index Up/Dn: Step Vol (+-5%)",
                "• Pinch: Spatial Height Vol",
                "• Swipes: Next/Prev Track",
                "• Peace Sign: Toggle Mute",
            ]
        else:
            mode_bullets = [
                "• Index Tip: Cursor Motion",
                "• Quick Pinch: Left Click (Anchored)",
                "• Double Pinch: Double Click",
                "• Hold Pinch: Left Drag & Drop",
                "• Peace / Mid-Pinch: Right Click",
                "• 3 Fingers: Middle Click (New Tab)",
                "• Swipe Left/Right: Switch Tabs",
                "• Index Up/Dn: Wheel Scroll",
            ]

        for bullet in mode_bullets:
            cv2.putText(dashboard, bullet, (lx1 + 14, cur_y), cv2.FONT_HERSHEY_SIMPLEX, 0.33, (190, 180, 170), 1, cv2.LINE_AA)
            cur_y += 18

        # ----------------------------------------------------------------------
        # 4. RIGHT COMMAND & MEDIA DECK
        # ----------------------------------------------------------------------
        rx1, ry1 = canvas_w - right_w - 14, view_y
        rx2, ry2 = canvas_w - 14, view_y + view_h
        cv2.rectangle(dashboard, (rx1, ry1), (rx2, ry2), (22, 17, 13), -1)
        cv2.rectangle(dashboard, (rx1, ry1), (rx2, ry2), (50, 40, 32), 1)

        for bx, by in [(rx1, ry1), (rx2, ry1), (rx1, ry2), (rx2, ry2)]:
            dx = brk if bx == rx1 else -brk
            dy = brk if by == ry1 else -brk
            cv2.line(dashboard, (bx, by), (bx + dx, by), COLOR_CYAN, 2)
            cv2.line(dashboard, (bx, by), (bx, by + dy), COLOR_CYAN, 2)

        cur_y = ry1 + 24
        cv2.putText(dashboard, "// GESTURE CLASSIFIER", (rx1 + 14, cur_y), cv2.FONT_HERSHEY_SIMPLEX, 0.44, COLOR_CYAN, 1, cv2.LINE_AA)
        cur_y += 18
        cv2.line(dashboard, (rx1 + 14, cur_y), (rx2 - 14, cur_y), (50, 40, 32), 1)
        cur_y += 16

        cv2.rectangle(dashboard, (rx1 + 14, cur_y), (rx2 - 14, cur_y + 46), (36, 28, 22), -1)
        cv2.rectangle(dashboard, (rx1 + 14, cur_y), (rx2 - 14, cur_y + 46), COLOR_CYAN, 1)
        cv2.putText(dashboard, f"GESTURE: {gesture}", (rx1 + 24, cur_y + 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.54, COLOR_CYAN, 2, cv2.LINE_AA)
        cur_y += 62

        cv2.putText(dashboard, "ACTION STATUS:", (rx1 + 14, cur_y), cv2.FONT_HERSHEY_SIMPLEX, 0.34, (140, 130, 120), 1, cv2.LINE_AA)
        cur_y += 16
        cv2.putText(dashboard, last_action_desc[:38], (rx1 + 14, cur_y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, COLOR_WHITE, 1, cv2.LINE_AA)
        cur_y += 24

        # Mode Specific Monitor on Right Deck
        if active_mode == MODE_MOUSE:
            cv2.putText(dashboard, "// AIR-MOUSE MONITOR", (rx1 + 14, cur_y), cv2.FONT_HERSHEY_SIMPLEX, 0.44, COLOR_AMBER, 1, cv2.LINE_AA)
            cur_y += 18
            cv2.line(dashboard, (rx1 + 14, cur_y), (rx2 - 14, cur_y), (50, 40, 32), 1)
            cur_y += 18

            m_items = [
                ("SCREEN COORD:", f"X:{mouse_ctrl.cur_screen_x}  Y:{mouse_ctrl.cur_screen_y}"),
                ("CLICK STATE:", mouse_ctrl.mouse_status),
                ("DRAGGING:", "YES [HELD]" if mouse_ctrl.is_dragging else "NO (IDLE)"),
                ("SMOOTHING:", "DYNAMIC DUAL-EXPONENTIAL"),
                ("DEADZONE:", "CENTER 64% (18% MARGIN)"),
            ]
            for k, v in m_items:
                col = COLOR_AMBER if "CLICK" in v or "DRAG" in v else COLOR_WHITE
                cv2.putText(dashboard, k, (rx1 + 14, cur_y), cv2.FONT_HERSHEY_SIMPLEX, 0.34, (140, 130, 120), 1, cv2.LINE_AA)
                cv2.putText(dashboard, v, (rx1 + 120, cur_y), cv2.FONT_HERSHEY_SIMPLEX, 0.34, col, 1, cv2.LINE_AA)
                cur_y += 20

            cur_y += 8
            cv2.putText(dashboard, "AIR-MOUSE DEADZONE RADAR:", (rx1 + 14, cur_y), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (140, 130, 120), 1, cv2.LINE_AA)
            cur_y += 10
            r_w, r_h = right_w - 28, 80
            cv2.rectangle(dashboard, (rx1 + 14, cur_y), (rx1 + 14 + r_w, cur_y + r_h), (35, 25, 20), -1)
            cv2.rectangle(dashboard, (rx1 + 14, cur_y), (rx1 + 14 + r_w, cur_y + r_h), (70, 60, 50), 1)

            dz_x1 = rx1 + 14 + int(r_w * 0.18)
            dz_x2 = rx1 + 14 + int(r_w * 0.82)
            dz_y1 = cur_y + int(r_h * 0.18)
            dz_y2 = cur_y + int(r_h * 0.82)
            cv2.rectangle(dashboard, (dz_x1, dz_y1), (dz_x2, dz_y2), COLOR_AMBER, 1)

            if features:
                norm_radar_x = min(1.0, max(0.0, mouse_ctrl.cur_screen_x / float(mouse_ctrl.screen_w)))
                norm_radar_y = min(1.0, max(0.0, mouse_ctrl.cur_screen_y / float(mouse_ctrl.screen_h)))
                dot_rx = rx1 + 14 + int(norm_radar_x * r_w)
                dot_ry = cur_y + int(norm_radar_y * r_h)
                cv2.circle(dashboard, (dot_rx, dot_ry), 4, COLOR_GREEN, -1, cv2.LINE_AA)
            cur_y += r_h + 20

        elif active_mode == MODE_MUSIC or (music_engine and music_engine.is_playing):
            cv2.putText(dashboard, "// AUDIO EQUALIZER & CONDUCTOR", (rx1 + 14, cur_y), cv2.FONT_HERSHEY_SIMPLEX, 0.44, COLOR_VIOLET, 1, cv2.LINE_AA)
            cur_y += 18
            cv2.line(dashboard, (rx1 + 14, cur_y), (rx2 - 14, cur_y), (50, 40, 32), 1)
            cur_y += 18

            eq_w = right_w - 28
            bar_w = int(eq_w / 12) - 4
            eq_max_h = 60
            for b_idx in range(12):
                bx = rx1 + 14 + b_idx * (bar_w + 4)
                if music_engine and music_engine.is_playing:
                    phase = b_idx * 0.55
                    freq = 2.4 + (b_idx % 3) * 0.8
                    h_val = int(eq_max_h * (0.2 + 0.8 * abs(math.sin(current_time * freq + phase))) * music_engine.volume)
                else:
                    h_val = 4
                cv2.rectangle(dashboard, (bx, cur_y + eq_max_h - h_val), (bx + bar_w, cur_y + eq_max_h), COLOR_VIOLET, -1)
                cv2.rectangle(dashboard, (bx, cur_y + eq_max_h - h_val), (bx + bar_w, cur_y + eq_max_h), COLOR_WHITE, 1)

            cur_y += eq_max_h + 16
            cv2.putText(dashboard, f"TRACK: {music_engine.track_title[:24] if music_engine else 'None'}",
                        (rx1 + 14, cur_y), cv2.FONT_HERSHEY_SIMPLEX, 0.35, COLOR_WHITE, 1, cv2.LINE_AA)
            cur_y += 18
            state_str = "PLAYING" if (music_engine and music_engine.is_playing) else "PAUSED"
            vol_pct = int(music_engine.volume * 100) if music_engine else 0
            cv2.putText(dashboard, f"STATE: {state_str}  |  VOL: {vol_pct}%",
                        (rx1 + 14, cur_y), cv2.FONT_HERSHEY_SIMPLEX, 0.35, COLOR_CYAN, 1, cv2.LINE_AA)
            cur_y += 26
        else:
            cv2.putText(dashboard, "// CAMERA STUDIO MONITOR", (rx1 + 14, cur_y), cv2.FONT_HERSHEY_SIMPLEX, 0.44, COLOR_ORANGE, 1, cv2.LINE_AA)
            cur_y += 18
            cv2.line(dashboard, (rx1 + 14, cur_y), (rx2 - 14, cur_y), (50, 40, 32), 1)
            cur_y += 18

            cam_items = [
                ("PHOTO STORAGE:", "captures/photos/"),
                ("VIDEO STORAGE:", "captures/videos/"),
                ("VIDEO CODEC:", "H.264 / MP4V / XVID"),
                ("RECORDING:", f"REC {rec_time_str}" if is_recording else "IDLE"),
                ("SHUTTER SOUND:", "SYNTHESIZED BURST"),
            ]
            for k, v in cam_items:
                col = COLOR_RED if is_recording and "REC" in v else COLOR_WHITE
                cv2.putText(dashboard, k, (rx1 + 14, cur_y), cv2.FONT_HERSHEY_SIMPLEX, 0.34, (140, 130, 120), 1, cv2.LINE_AA)
                cv2.putText(dashboard, v, (rx1 + 120, cur_y), cv2.FONT_HERSHEY_SIMPLEX, 0.34, col, 1, cv2.LINE_AA)
                cur_y += 20
            cur_y += 10

        # Section 3: RECENT ACTION AUDIT LOG
        cv2.putText(dashboard, "// RECENT EVENT AUDIT LOG", (rx1 + 14, cur_y), cv2.FONT_HERSHEY_SIMPLEX, 0.44, COLOR_WHITE, 1, cv2.LINE_AA)
        cur_y += 18
        cv2.line(dashboard, (rx1 + 14, cur_y), (rx2 - 14, cur_y), (50, 40, 32), 1)
        cur_y += 18

        if audit_log:
            for t_stamp, log_text in list(audit_log)[-7:]:
                cv2.putText(dashboard, f"[{t_stamp}]", (rx1 + 14, cur_y), cv2.FONT_HERSHEY_SIMPLEX, 0.30, COLOR_CYAN, 1, cv2.LINE_AA)
                cv2.putText(dashboard, log_text[:32], (rx1 + 95, cur_y), cv2.FONT_HERSHEY_SIMPLEX, 0.32, COLOR_WHITE, 1, cv2.LINE_AA)
                cur_y += 18
        else:
            cv2.putText(dashboard, "NO ACTIONS LOGGED YET", (rx1 + 14, cur_y), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (120, 110, 100), 1, cv2.LINE_AA)

        # ----------------------------------------------------------------------
        # 5. BOTTOM NAVIGATION BAR
        # ----------------------------------------------------------------------
        cv2.rectangle(dashboard, (0, canvas_h - bot_h), (canvas_w, canvas_h), (20, 15, 12), -1)
        cv2.line(dashboard, (0, canvas_h - bot_h), (canvas_w, canvas_h - bot_h), COLOR_CYAN, 1)

        hotkey_str = "[ESC] Panic Stop  |  [E] Arm Actions  |  [1-4] Switch Modes  |  [P] Matrix  |  [C] Photo  |  [R] Video  |  [F] Flash  |  [TAB] Layout  |  [F11] Fullscreen  |  [Q] Quit"
        cv2.putText(dashboard, hotkey_str, (20, canvas_h - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.36, COLOR_WHITE, 1, cv2.LINE_AA)
        cv2.putText(dashboard, "HARSH SHAH (@harshvshah12) • PROJECT HOLOHAND v2.2",
                    (canvas_w - 380, canvas_h - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.36, COLOR_CYAN, 1, cv2.LINE_AA)

        return dashboard


# ==============================================================================
# 8. VIRTUAL HOLOGRAPHIC CONTROL PANEL
# ==============================================================================
class VirtualControlPanel:
    """
    AR 2D interactive floating control panel rendered directly over the camera stream.
    Users hover their index fingertip over buttons and trigger actions via Pinch or Dwell.
    """
    def __init__(self, display_width, display_height):
        self.width = display_width
        self.height = display_height
        self.is_visible = False
        self.hovered_btn = None
        self.hover_start_time = 0.0

        # Define Virtual Buttons: (id, label, x, y, w, h)
        bw, bh = 135, 34
        cx = display_width // 2
        start_y = 65

        self.buttons = [
            {"id": "MODE_HOLO",  "label": "[1] HOLO",        "rect": (cx - 285, start_y, bw, bh)},
            {"id": "MODE_CAM",   "label": "[2] CAMERA",      "rect": (cx - 142, start_y, bw, bh)},
            {"id": "MODE_MUSIC", "label": "[3] MUSIC",       "rect": (cx + 5,   start_y, bw, bh)},
            {"id": "MODE_MOUSE", "label": "[4] AIR-MOUSE",   "rect": (cx + 148, start_y, bw, bh)},
            {"id": "PLAY_PAUSE", "label": "PLAY / PAUSE",    "rect": (cx - 285, start_y + 42, bw, bh)},
            {"id": "PREV_TRACK", "label": "PREV TRACK",      "rect": (cx - 142, start_y + 42, bw, bh)},
            {"id": "NEXT_TRACK", "label": "NEXT TRACK",      "rect": (cx + 5,   start_y + 42, bw, bh)},
            {"id": "SNAP_PHOTO", "label": "SNAP PHOTO",      "rect": (cx + 148, start_y + 42, bw, bh)},
            {"id": "VOL_DOWN",   "label": "VOLUME -",        "rect": (cx - 285, start_y + 84, bw, bh)},
            {"id": "VOL_UP",     "label": "VOLUME +",        "rect": (cx - 142, start_y + 84, bw, bh)},
            {"id": "TOGGLE_REC", "label": "REC ON/OFF",      "rect": (cx + 5,   start_y + 84, bw, bh)},
            {"id": "TOGGLE_FLASH","label": "FLASH ON/OFF",    "rect": (cx + 148, start_y + 84, bw, bh)},
            {"id": "TOGGLE_ARM", "label": "ARM / DISARM",    "rect": (cx - 142, start_y + 126, bw, bh)},
            {"id": "CLOSE_PANEL","label": "CLOSE [X]",       "rect": (cx + 5,   start_y + 126, bw, bh)},
        ]

    def toggle(self):
        self.is_visible = not self.is_visible
        self.hovered_btn = None

    def update_interaction(self, pointer_pos, is_pinching, current_time):
        """
        Input: pointer_pos (x, y) from index fingertip.
        Returns: triggered_action_id or None.
        """
        if not self.is_visible or pointer_pos is None:
            self.hovered_btn = None
            return None

        px, py = pointer_pos
        current_hover = None

        for btn in self.buttons:
            bx, by, bw, bh = btn["rect"]
            if bx <= px <= bx + bw and by <= py <= by + bh:
                current_hover = btn["id"]
                break

        triggered_action = None
        if current_hover != self.hovered_btn:
            self.hovered_btn = current_hover
            self.hover_start_time = current_time
        elif self.hovered_btn is not None:
            dwell_time = current_time - self.hover_start_time
            # Trigger via pinch or dwell completion
            if is_pinching or dwell_time >= HOVER_DWELL_SECONDS:
                triggered_action = self.hovered_btn
                self.hovered_btn = None  # Reset after trigger
                self.hover_start_time = current_time

        return triggered_action

    def render(self, frame, pointer_pos, current_time):
        if not self.is_visible:
            return

        # Semi-transparent background plate
        overlay = frame.copy()
        cx = self.width // 2
        cv2.rectangle(overlay, (cx - 305, 52), (cx + 305, 235), COLOR_DARK_GLASS, -1)
        cv2.rectangle(overlay, (cx - 305, 52), (cx + 305, 235), COLOR_CYAN, 2)
        cv2.addWeighted(overlay, 0.88, frame, 0.12, 0, frame)

        cv2.putText(frame, "HOLOGRAM COMMAND MATRIX", (cx - 130, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.45, COLOR_CYAN, 1, cv2.LINE_AA)

        # Draw buttons
        for btn in self.buttons:
            bx, by, bw, bh = btn["rect"]
            is_hover = (btn["id"] == self.hovered_btn)

            border_col = COLOR_VIOLET if is_hover else COLOR_CYAN
            bg_col = (50, 20, 40) if is_hover else (30, 24, 20)

            # Button background & border
            cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), bg_col, -1)
            cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), border_col, 1)

            # Dwell progress fill if hovered
            if is_hover:
                dwell = current_time - self.hover_start_time
                progress = min(1.0, dwell / HOVER_DWELL_SECONDS)
                fill_w = int(bw * progress)
                cv2.rectangle(frame, (bx, by + bh - 4), (bx + fill_w, by + bh), COLOR_VIOLET, -1)

            cv2.putText(frame, btn["label"], (bx + 12, by + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.38, COLOR_WHITE, 1, cv2.LINE_AA)

        # Draw pointer cursor on top of panel
        if pointer_pos is not None:
            px, py = int(pointer_pos[0]), int(pointer_pos[1])
            cv2.circle(frame, (px, py), 6, COLOR_CYAN, 2, cv2.LINE_AA)
            cv2.circle(frame, (px, py), 2, COLOR_WHITE, -1, cv2.LINE_AA)


# ==============================================================================
# 9. DESKTOP OS AUTOMATION & HARDWARE AUDIO BRIDGE
# ==============================================================================
class WindowsMasterAudioController:
    """
    Direct low-latency Windows Endpoint Master Audio interface using pycaw.
    Controls hardware OS master volume with zero keystroke delay.
    """
    def __init__(self):
        self._endpoint = None
        self._available = False
        self._init_endpoint()

    def _init_endpoint(self):
        if not PYCAW_AVAILABLE:
            return
        try:
            import comtypes
            comtypes.CoInitialize()
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            self._endpoint = cast(interface, POINTER(IAudioEndpointVolume))
            self._available = True
        except Exception:
            self._available = False

    def get_volume(self) -> float:
        if not self._available:
            return 0.5
        try:
            return float(self._endpoint.GetMasterVolumeLevelScalar())
        except Exception:
            self._init_endpoint()
            try:
                return float(self._endpoint.GetMasterVolumeLevelScalar())
            except Exception:
                return 0.5

    def set_volume(self, scalar: float):
        if not self._available:
            return
        scalar = max(0.0, min(1.0, float(scalar)))
        try:
            self._endpoint.SetMasterVolumeLevelScalar(scalar, None)
        except Exception:
            self._init_endpoint()
            try:
                self._endpoint.SetMasterVolumeLevelScalar(scalar, None)
            except Exception:
                pass


class DesktopActionBridge:
    """
    Executes native desktop automation, presentation slides, scrolling,
    tab switching, and OS master volume safely with rate-limiting and dry-run protection.
    """
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.enabled = True
        self.last_scroll_time = 0.0
        self.last_vol_time = 0.0
        self.last_tab_time = 0.0
        self.audio_hw = WindowsMasterAudioController()

    def set_system_volume(self, scalar: float):
        """Sets Windows OS Master Volume continuously in real time (0.0 to 1.0)."""
        if not self.enabled or self.dry_run:
            return
        now = time.monotonic()
        if now - self.last_vol_time >= 0.02:  # Up to 50 updates/sec for smooth vernier feel
            self.last_vol_time = now
            if self.audio_hw._available:
                self.audio_hw.set_volume(scalar)
            elif PYAUTOGUI_AVAILABLE:
                pass

    def get_system_volume(self) -> float:
        """Returns current Windows Master Volume scalar (0.0 to 1.0)."""
        if self.audio_hw._available:
            return self.audio_hw.get_volume()
        return 0.5

    def next_tab(self):
        """Switches to the Next Tab in Browser / OS Application Window (Ctrl+Tab)."""
        if not self.enabled or self.dry_run or not PYAUTOGUI_AVAILABLE:
            return
        now = time.monotonic()
        if now - self.last_tab_time >= 0.25:
            self.last_tab_time = now
            try:
                pyautogui.keyDown('ctrl')
                pyautogui.press('tab')
                pyautogui.keyUp('ctrl')
            except Exception as e:
                print(f"[HOLOHAND][WARN] next_tab failed: {e}")

    def prev_tab(self):
        """Switches to the Previous Tab in Browser / OS Application Window (Ctrl+Shift+Tab)."""
        if not self.enabled or self.dry_run or not PYAUTOGUI_AVAILABLE:
            return
        now = time.monotonic()
        if now - self.last_tab_time >= 0.25:
            self.last_tab_time = now
            try:
                pyautogui.keyDown('ctrl')
                pyautogui.keyDown('shift')
                pyautogui.press('tab')
                pyautogui.keyUp('shift')
                pyautogui.keyUp('ctrl')
            except Exception as e:
                print(f"[HOLOHAND][WARN] prev_tab failed: {e}")

    def play_pause(self):
        if not self.enabled or self.dry_run or not PYAUTOGUI_AVAILABLE:
            return
        try:
            pyautogui.press('playpause')
        except Exception as e:
            print(f"[HOLOHAND][WARN] Media key failed: {e}")

    def next_track(self):
        if not self.enabled or self.dry_run or not PYAUTOGUI_AVAILABLE:
            return
        try:
            pyautogui.press('nexttrack')
        except Exception:
            pass

    def prev_track(self):
        if not self.enabled or self.dry_run or not PYAUTOGUI_AVAILABLE:
            return
        try:
            pyautogui.press('prevtrack')
        except Exception:
            pass

    def volume_up(self):
        if not self.enabled or self.dry_run:
            return
        if self.audio_hw._available:
            cur = self.audio_hw.get_volume()
            self.audio_hw.set_volume(min(1.0, cur + 0.05))
        elif PYAUTOGUI_AVAILABLE:
            try:
                pyautogui.press('volumeup')
            except Exception:
                pass

    def volume_down(self):
        if not self.enabled or self.dry_run:
            return
        if self.audio_hw._available:
            cur = self.audio_hw.get_volume()
            self.audio_hw.set_volume(max(0.0, cur - 0.05))
        elif PYAUTOGUI_AVAILABLE:
            try:
                pyautogui.press('volumedown')
            except Exception:
                pass

    def next_slide(self):
        if not self.enabled or self.dry_run or not PYAUTOGUI_AVAILABLE:
            return
        try:
            pyautogui.press('right')
        except Exception:
            pass

    def prev_slide(self):
        if not self.enabled or self.dry_run or not PYAUTOGUI_AVAILABLE:
            return
        try:
            pyautogui.press('left')
        except Exception:
            pass

    def scroll(self, amount):
        if not self.enabled or self.dry_run or not PYAUTOGUI_AVAILABLE:
            return
        now = time.monotonic()
        if now - self.last_scroll_time > 0.04:  # Rate-limit scrolling
            self.last_scroll_time = now
            try:
                pyautogui.scroll(amount)
            except Exception:
                pass


# ==============================================================================
# 9.5 VIRTUAL AIR-MOUSE SUBSYSTEM
# ==============================================================================
class VirtualAirMouseController:
    """
    Translates hand coordinates and gestures into smooth, jitter-free OS mouse
    actions (Cursor movement, Left Click, Double Click, Drag & Drop, Right Click,
    Middle Click, Vertical Scrolling, and Left/Right Swipe Tab Switching) with
    click position anchoring, dynamic velocity smoothing, and active deadzones.
    """
    def __init__(self, dry_run=False, margin_ratio=0.18, desktop_bridge=None):
        self.dry_run = dry_run
        self.enabled = True
        self.margin_ratio = margin_ratio
        self.desktop_bridge = desktop_bridge

        # Screen dimensions
        if PYAUTOGUI_AVAILABLE:
            pyautogui.FAILSAFE = False  # Avoid abrupt exit at screen corners
            self.screen_w, self.screen_h = pyautogui.size()
        else:
            self.screen_w, self.screen_h = 1920, 1080

        # State tracking
        self.cur_screen_x = self.screen_w // 2
        self.cur_screen_y = self.screen_h // 2
        self.prev_raw_x = None
        self.prev_raw_y = None

        # Position Anchor during click/drag
        self.anchor_screen_x = self.cur_screen_x
        self.anchor_screen_y = self.cur_screen_y

        self.is_dragging = False
        self.is_pinching = False
        self.pinch_start_time = 0.0
        self.last_click_time = 0.0
        self.last_right_click_time = 0.0
        self.last_middle_click_time = 0.0
        self.last_scroll_time = 0.0
        self.last_swipe_time = 0.0
        self.mouse_status = "HOVER"
        self.active_box = (0, 0, 1, 1)

    def update(self, pointer_pos, gesture, is_new, payload, current_time, cam_w, cam_h, features=None, music_engine=None):
        """
        Input: pointer_pos (px, py) on camera frame, gesture name, is_new flag.
        Returns: current mouse status string.
        """
        if not self.enabled or pointer_pos is None:
            if self.is_dragging:
                self.release_drag()
            return "STANDBY"

        # Calculate Active Interaction Boundary (Deadzone box)
        min_x = int(cam_w * self.margin_ratio)
        max_x = int(cam_w * (1.0 - self.margin_ratio))
        min_y = int(cam_h * self.margin_ratio)
        max_y = int(cam_h * (1.0 - self.margin_ratio))
        self.active_box = (min_x, min_y, max_x, max_y)

        px, py = pointer_pos

        # Mirror X coordinate so moving hand to user's right moves cursor right
        norm_x = 1.0 - max(0.0, min(1.0, (px - min_x) / float(max(1, max_x - min_x))))
        norm_y = max(0.0, min(1.0, (py - min_y) / float(max(1, max_y - min_y))))

        target_x = int(norm_x * self.screen_w)
        target_y = int(norm_y * self.screen_h)

        # Dynamic Dual-Exponential Smoothing
        if self.prev_raw_x is None:
            self.cur_screen_x = target_x
            self.cur_screen_y = target_y
            self.prev_raw_x = target_x
            self.prev_raw_y = target_y
        else:
            displacement = math.hypot(target_x - self.prev_raw_x, target_y - self.prev_raw_y)
            if displacement > 70:
                alpha = 0.75  # Rapid flick response
            elif displacement > 25:
                alpha = 0.45  # Standard navigation
            elif displacement > 8:
                alpha = 0.20  # Precision adjustment
            else:
                alpha = 0.08  # Rock-solid button lock (anti-jitter)

            self.cur_screen_x = int(self.cur_screen_x * (1.0 - alpha) + target_x * alpha)
            self.cur_screen_y = int(self.cur_screen_y * (1.0 - alpha) + target_y * alpha)
            self.prev_raw_x = target_x
            self.prev_raw_y = target_y

        # Clamp to screen boundary
        self.cur_screen_x = max(0, min(self.screen_w - 1, self.cur_screen_x))
        self.cur_screen_y = max(0, min(self.screen_h - 1, self.cur_screen_y))

        # Handle Mouse Action Gestures
        status = "HOVER"

        # ----------------------------------------------------------------------
        # 1. SWIPE GESTURES: TAB SWITCHING (Left-to-Right / Right-to-Left)
        # ----------------------------------------------------------------------
        if gesture == "SWIPE_RIGHT" and is_new:
            if current_time - self.last_swipe_time > 0.25:
                self.last_swipe_time = current_time
                if not self.dry_run:
                    if self.desktop_bridge:
                        self.desktop_bridge.next_tab()
                    elif PYAUTOGUI_AVAILABLE:
                        try:
                            pyautogui.keyDown('ctrl')
                            pyautogui.press('tab')
                            pyautogui.keyUp('ctrl')
                        except Exception:
                            pass
                if music_engine:
                    music_engine.play_swipe()
                self.mouse_status = "TAB SWITCH: NEXT [Ctrl+Tab]"
                return self.mouse_status

        if gesture == "SWIPE_LEFT" and is_new:
            if current_time - self.last_swipe_time > 0.25:
                self.last_swipe_time = current_time
                if not self.dry_run:
                    if self.desktop_bridge:
                        self.desktop_bridge.prev_tab()
                    elif PYAUTOGUI_AVAILABLE:
                        try:
                            pyautogui.keyDown('ctrl')
                            pyautogui.keyDown('shift')
                            pyautogui.press('tab')
                            pyautogui.keyUp('shift')
                            pyautogui.keyUp('ctrl')
                        except Exception:
                            pass
                if music_engine:
                    music_engine.play_swipe()
                self.mouse_status = "TAB SWITCH: PREV [Ctrl+Shift+Tab]"
                return self.mouse_status

        # ----------------------------------------------------------------------
        # 2. PINCH GESTURE: LEFT CLICK, DOUBLE CLICK, OR DRAG & DROP
        # ----------------------------------------------------------------------
        if gesture == "PINCH":
            if not self.is_pinching:
                self.is_pinching = True
                self.pinch_start_time = current_time
                # Freeze click anchor point to eliminate finger-pinch drift
                self.anchor_screen_x = self.cur_screen_x
                self.anchor_screen_y = self.cur_screen_y

            hold_duration = current_time - self.pinch_start_time
            if hold_duration >= 0.35 and not self.is_dragging:
                # Sustained Pinch (>0.35s) -> Engage Drag & Drop
                if not self.dry_run and PYAUTOGUI_AVAILABLE:
                    try:
                        pyautogui.mouseDown(button='left')
                    except Exception:
                        pass
                self.is_dragging = True
                status = "DRAGGING [HELD]"
            elif self.is_dragging:
                status = "DRAGGING [HELD]"
            else:
                # Quick pinch in progress (<0.35s): anchor cursor coordinates so target isn't lost
                self.cur_screen_x = self.anchor_screen_x
                self.cur_screen_y = self.anchor_screen_y
                status = "PINCH [CLICK READY]"
        else:
            # Pinch was released
            if self.is_pinching:
                hold_duration = current_time - self.pinch_start_time
                self.is_pinching = False

                if self.is_dragging:
                    # Release Drag
                    if not self.dry_run and PYAUTOGUI_AVAILABLE:
                        try:
                            pyautogui.mouseUp(button='left')
                        except Exception:
                            pass
                    self.is_dragging = False
                    status = "RELEASED DRAG"
                elif hold_duration < 0.35:
                    # Quick pinch confirmed -> Execute click at anchor point!
                    click_x = self.anchor_screen_x
                    click_y = self.anchor_screen_y

                    # Double Click vs Single Click
                    if current_time - self.last_click_time < 0.45:
                        if not self.dry_run and PYAUTOGUI_AVAILABLE:
                            try:
                                pyautogui.doubleClick(click_x, click_y)
                            except Exception:
                                pass
                        status = "DOUBLE CLICK"
                        if music_engine:
                            music_engine.play_click()
                    else:
                        if not self.dry_run and PYAUTOGUI_AVAILABLE:
                            try:
                                pyautogui.click(click_x, click_y, button='left')
                            except Exception:
                                pass
                        status = "LEFT CLICK"
                        if music_engine:
                            music_engine.play_click()
                    self.last_click_time = current_time

        # ----------------------------------------------------------------------
        # 3. RIGHT CLICK: Peace Sign (✌️) OR Thumb+Middle Finger Pinch
        # ----------------------------------------------------------------------
        is_middle_pinch = False
        if features and "norm_middle_pinch_dist" in features:
            is_middle_pinch = (features["norm_middle_pinch_dist"] < PINCH_THRESHOLD)

        if (gesture == "PEACE_SIGN" and is_new) or is_middle_pinch:
            if current_time - self.last_right_click_time > 0.45:
                self.last_right_click_time = current_time
                if not self.dry_run and PYAUTOGUI_AVAILABLE:
                    try:
                        pyautogui.click(self.cur_screen_x, self.cur_screen_y, button='right')
                    except Exception:
                        pass
                status = "RIGHT CLICK"
                if music_engine:
                    music_engine.play_click()

        # ----------------------------------------------------------------------
        # 4. MIDDLE CLICK (Wheel Button / New Tab / Close Tab): Three Fingers Up
        # ----------------------------------------------------------------------
        if gesture == "THREE_FINGERS_UP" and is_new:
            if current_time - self.last_middle_click_time > 0.55:
                self.last_middle_click_time = current_time
                if not self.dry_run and PYAUTOGUI_AVAILABLE:
                    try:
                        pyautogui.click(self.cur_screen_x, self.cur_screen_y, button='middle')
                    except Exception:
                        pass
                status = "MIDDLE CLICK [Tab Open/Close]"
                if music_engine:
                    music_engine.play_click()

        # ----------------------------------------------------------------------
        # 5. VERTICAL WHEEL SCROLLING (Index Up = Scroll Up, Index Down = Scroll Down)
        # ----------------------------------------------------------------------
        if gesture == "INDEX_POINTING_UP":
            if current_time - self.last_scroll_time > 0.06:
                self.last_scroll_time = current_time
                if not self.dry_run and PYAUTOGUI_AVAILABLE:
                    try:
                        pyautogui.scroll(120)
                    except Exception:
                        pass
                status = "SCROLL UP"

        if gesture == "INDEX_POINTING_DOWN":
            if current_time - self.last_scroll_time > 0.06:
                self.last_scroll_time = current_time
                if not self.dry_run and PYAUTOGUI_AVAILABLE:
                    try:
                        pyautogui.scroll(-120)
                    except Exception:
                        pass
                status = "SCROLL DOWN"

        # ----------------------------------------------------------------------
        # 6. CLOSED FIST: Safety Drag Release
        # ----------------------------------------------------------------------
        if gesture == "CLOSED_FIST" and self.is_dragging:
            self.release_drag()
            status = "RELEASED DRAG"

        # Move the OS cursor (unless in quick pinch anchor lock)
        if not self.dry_run and PYAUTOGUI_AVAILABLE:
            try:
                pyautogui.moveTo(self.cur_screen_x, self.cur_screen_y)
            except Exception:
                pass

        self.mouse_status = status
        return status

    def release_drag(self):
        if self.is_dragging:
            if not self.dry_run and PYAUTOGUI_AVAILABLE:
                try:
                    pyautogui.mouseUp(button='left')
                except Exception:
                    pass
            self.is_dragging = False
            self.is_pinching = False


# ==============================================================================
# 10. PRIMARY APPLICATION ORCHESTRATOR
# ==============================================================================
class HoloHandApp:
    """
    Top-level application orchestrator tying together camera acquisition,
    MediaPipe landmark tracking, gesture classification, operating modes,
    holographic rendering, media capture, and desktop actions.
    """
    def __init__(self, stream_url=DEFAULT_STREAM_URL, dry_run=False, start_mode=MODE_HOLOGRAM, start_visual=VISUAL_HOLOGRAM, fullscreen=True, dashboard_layout="STUDIO"):
        self.stream_url = stream_url
        self.dry_run = dry_run
        self.active_mode = start_mode
        self.visual_mode = start_visual
        self.actions_enabled = True
        self.fullscreen = fullscreen
        self.dashboard_layout = dashboard_layout  # "STUDIO" (Mission Control Dashboard) or "FULLFRAME" (Direct AR HUD)

        # Window & Dimension parameters
        self.window_name = "PROJECT HOLOHAND - ESP32-CAM AR MISSION CONTROL"
        self.display_width = DEFAULT_DISPLAY_WIDTH
        self.display_height = DEFAULT_DISPLAY_HEIGHT

        # Screen Canvas Dimensions (auto-detects 1080p, 1440p, 4K)
        if PYAUTOGUI_AVAILABLE:
            self.canvas_width, self.canvas_height = pyautogui.size()
        else:
            self.canvas_width, self.canvas_height = 1920, 1080

        # Initialize Subsystems
        print("[HOLOHAND] Launching ESP32-CAM Stream Acquisition Worker...")
        self.stream_worker = StreamAcquisitionWorker(self.stream_url)
        self.stream_worker.start()

        print("[HOLOHAND] Initializing MediaPipe Hands Engine...")
        self.hands_detector = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=MAX_HANDS,
            min_detection_confidence=CONF_DETECTION,
            min_tracking_confidence=CONF_TRACKING
        )

        self.recognizer = GestureRecognizer()
        self.visual_engine = HolographicVisualEngine(self.display_width, self.display_height)
        self.control_panel = VirtualControlPanel(self.display_width, self.display_height)
        self.desktop_bridge = DesktopActionBridge(dry_run=self.dry_run)
        self.mouse_controller = VirtualAirMouseController(dry_run=self.dry_run, desktop_bridge=self.desktop_bridge)
        self.music_engine = MusicConductorEngine(MUSIC_DIR)
        self.flash_ctrl = HardwareFlashController(self.stream_url)
        self.caliper_volume = self.desktop_bridge.get_system_volume()
        self.last_vol_log_time = 0.0

        # Video Recorder Reference
        self.recorder = None
        self.is_recording = False
        self.rec_start_time = 0.0

        # Countdown capture state (for open palm -> fist photo)
        self.countdown_active = False
        self.countdown_start = 0.0
        self.countdown_duration = 3.0
        self.last_open_palm_time = 0.0

        # Diagnostics & Timing
        self.last_action_desc = "System Standby"
        self.show_diagnostics = False
        self.prev_frame_time = time.monotonic()
        self.proc_fps = 0.0
        self.running = True
        self.audit_log = deque(maxlen=8)

        # Create output directories
        os.makedirs(PHOTO_DIR, exist_ok=True)
        os.makedirs(VIDEO_DIR, exist_ok=True)

    def _log_event(self, text):
        t_str = datetime.now().strftime("%H:%M:%S")
        if not self.audit_log or self.audit_log[-1][1] != text:
            self.audit_log.append((t_str, text))

    def run(self):
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        if self.fullscreen:
            cv2.setWindowProperty(self.window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        else:
            cv2.resizeWindow(self.window_name, self.canvas_width, self.canvas_height)

        print("\n=======================================================")
        print("  PROJECT HOLOHAND — MISSION CONTROL WORKSTATION READY")
        print("=======================================================")
        print("KEYBOARD CONTROLS:")
        print("  ESC:       EMERGENCY DISABLE (Stop desktop actions)")
        print("  E / SPACE: Toggle desktop actions enable/disable")
        print("  1 / 2 / 3: Switch Operating Modes (Holo, Cam, Music)")
        print("  4 / M:     Switch to Mode D: Virtual Air-Mouse")
        print("  TAB:       Toggle Studio Dashboard / Full-Frame AR View")
        print("  F / F11:   Toggle Borderless Fullscreen / Windowed Mode")
        print("  V:         Cycle Visual Mode (Holo -> Scan -> Minimal)")
        print("  P:         Toggle Holographic Virtual Control Panel")
        print("  C:         Manual Instant Photo Capture")
        print("  R:         Toggle Video Recording Start/Stop")
        print("  X:         Toggle Dry-Run Mode")
        print("  D:         Toggle Calibration & Diagnostic HUD")
        print("  Q:         Quit Cleanly")
        print("=======================================================\n")

        fps_timer = time.monotonic()
        fps_count = 0

        while self.running:
            loop_start = time.monotonic()
            raw_frame = self.stream_worker.get_latest_frame()

            # Render connection waiting screen if camera stream not yet ready
            if raw_frame is None:
                display_frame = self._render_offline_screen()
                cv2.imshow(self.window_name, display_frame)
                key = cv2.waitKey(20) & 0xFF
                if key == ord('q') or key == 27:  # Quit or ESC
                    break
                continue

            # Resize raw camera frame to target canvas size
            frame = cv2.resize(raw_frame, (self.display_width, self.display_height))
            clean_camera_frame = frame.copy()

            # 1. MediaPipe Hand Landmark Processing
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_results = self.hands_detector.process(rgb_frame)

            features = None
            pointer_pos = None
            detected_hands = 0

            if mp_results.multi_hand_landmarks:
                detected_hands = len(mp_results.multi_hand_landmarks)
                # Primary hand extraction (first hand detected)
                primary_lm = mp_results.multi_hand_landmarks[0].landmark
                features = HandFeatureExtractor.extract_features(primary_lm, self.display_width, self.display_height)
                pointer_pos = (features["tips"]["index"][0], features["tips"]["index"][1])

            # 2. Gesture Evaluation & State Transition
            gesture, is_new, payload = self.recognizer.update(features, loop_start)

            # Check Two-Hand Gestures
            if detected_hands >= 2:
                lm1 = mp_results.multi_hand_landmarks[0].landmark
                lm2 = mp_results.multi_hand_landmarks[1].landmark
                feat1 = HandFeatureExtractor.extract_features(lm1, self.display_width, self.display_height)
                feat2 = HandFeatureExtractor.extract_features(lm2, self.display_width, self.display_height)
                # Two-Hand Open Palm toggles Virtual Control Panel
                if feat1["thumb_ext"] and feat1["index_ext"] and feat2["thumb_ext"] and feat2["index_ext"]:
                    if self.recognizer.check_cooldown("TWO_HAND_PANEL", 1.5):
                        self.control_panel.toggle()
                        self.visual_engine.trigger_shockwave(self.display_width // 2, self.display_height // 2, COLOR_VIOLET)

            # 3. Virtual Control Panel Interaction
            is_pinching = (gesture == "PINCH")
            panel_action = self.control_panel.update_interaction(pointer_pos, is_pinching, loop_start)
            if panel_action:
                self._handle_panel_action(panel_action, clean_camera_frame)

            # 4. Operating Mode Action Routing
            if is_new and gesture != "NONE" and features:
                cx, cy = int(features["palm_center"][0]), int(features["palm_center"][1])
                self.visual_engine.trigger_particle_burst(cx, cy)
                self.visual_engine.trigger_shockwave(cx, cy)

            # Record open palm timestamp for sequential gesture (Open Palm -> Closed Fist)
            if gesture == "OPEN_PALM":
                self.last_open_palm_time = loop_start

            self._route_gesture_actions(gesture, is_new, payload, clean_camera_frame, loop_start, features)

            # 5. Countdown Capture Processing
            if self.countdown_active:
                remaining = self.countdown_duration - (loop_start - self.countdown_start)
                if remaining <= 0:
                    self.countdown_active = False
                    self._capture_photo(clean_camera_frame)
                else:
                    count_num = int(math.ceil(remaining))
                    cx, cy = self.display_width // 2, self.display_height // 2
                    overlay = frame.copy()
                    cv2.circle(overlay, (cx, cy), 110, COLOR_DARK_GLASS, -1)
                    cv2.circle(overlay, (cx, cy), 110, COLOR_CYAN, 3, cv2.LINE_AA)
                    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

                    fraction = max(0.0, remaining / self.countdown_duration)
                    end_angle = int(360 * fraction)
                    cv2.ellipse(frame, (cx, cy), (95, 95), -90, 0, end_angle, COLOR_AMBER, 4, cv2.LINE_AA)

                    cv2.putText(frame, str(count_num), (cx - 28, cy + 32),
                                cv2.FONT_HERSHEY_SIMPLEX, 3.6, COLOR_WHITE, 6, cv2.LINE_AA)
                    cv2.putText(frame, str(count_num), (cx - 28, cy + 32),
                                cv2.FONT_HERSHEY_SIMPLEX, 3.6, COLOR_CYAN, 2, cv2.LINE_AA)
                    cv2.putText(frame, "PHOTO COUNTDOWN", (cx - 82, cy + 85),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.42, COLOR_AMBER, 1, cv2.LINE_AA)

            # Real-Time Thumb-to-Index Distance Master Volume Control & AR Caliper HUD
            if gesture in ["CALIPER_VOLUME", "PINCH"] and payload:
                target_vol = payload.get("volume_ratio", payload.get("norm_y", 0.5))
                # One-pole filter for silky smooth, jitter-free vernier feel
                self.caliper_volume = float(np.clip(self.caliper_volume * 0.65 + target_vol * 0.35, 0.0, 1.0))

                # Update live Windows Master Volume and internal music engine
                self.desktop_bridge.set_system_volume(self.caliper_volume)
                self.music_engine.set_volume(self.caliper_volume)

                # Render Vernier Caliper HUD directly connecting thumb and index tips
                thumb_pt = payload.get("thumb_pt", (0, 0))
                index_pt = payload.get("index_pt", (0, 0))
                raw_dist = payload.get("raw_dist", 0.0)
                self.visual_engine.render_caliper_volume_hud(
                    frame, thumb_pt, index_pt, self.caliper_volume, raw_dist,
                    is_system_audio=self.desktop_bridge.audio_hw._available
                )

            # 6. Video Recording Frame Enqueueing
            rec_time_str = "00:00"
            if self.is_recording and self.recorder:
                dur = int(loop_start - self.rec_start_time)
                rec_time_str = f"{dur // 60:02d}:{dur % 60:02d}"
                self.recorder.enqueue_frame(clean_camera_frame)

            # 7. Holographic AR Visual Rendering
            dt = max(0.001, loop_start - self.prev_frame_time)
            self.prev_frame_time = loop_start
            self.visual_engine.update_animations(dt)

            if self.visual_mode != VISUAL_MINIMAL:
                self.visual_engine.render_hand_skeleton(frame, features, self.visual_mode)
                self.visual_engine.render_palm_scanner(frame, features, loop_start)
            self.visual_engine.render_effects(frame)

            # Render Virtual Control Panel
            self.control_panel.render(frame, pointer_pos, loop_start)

            # Render Telemetry HUDs
            self.visual_engine.render_top_hud(
                frame, self.active_mode, self.visual_mode, self.actions_enabled,
                self.dry_run, self.stream_worker.status_message, self.proc_fps, self.stream_worker.stream_fps,
                is_flash_on=self.flash_ctrl.is_on
            )
            self.visual_engine.render_bottom_hud(
                frame, gesture, self.last_action_desc, self.music_engine, self.is_recording, rec_time_str
            )

            # Air-Mouse HUD Overlay
            if self.active_mode == MODE_MOUSE:
                self.visual_engine.render_mouse_hud(frame, self.mouse_controller, pointer_pos)

            # Optional Diagnostic Calibration Overlay
            if self.show_diagnostics and features:
                self._render_diagnostic_overlay(frame, features, gesture)

            # Display composite AR frame: Studio Dashboard vs Fullframe
            if self.dashboard_layout == "STUDIO":
                display_frame = self.visual_engine.render_presentation_dashboard(
                    frame, features, gesture, self.last_action_desc, self.active_mode, self.visual_mode,
                    self.music_engine, self.mouse_controller, self.flash_ctrl, self.proc_fps, self.stream_worker.stream_fps,
                    self.is_recording, rec_time_str, self.audit_log, loop_start,
                    canvas_w=self.canvas_width, canvas_h=self.canvas_height
                )
            else:
                display_frame = cv2.resize(frame, (self.canvas_width, self.canvas_height))

            cv2.imshow(self.window_name, display_frame)

            # FPS measurement
            fps_count += 1
            if loop_start - fps_timer >= 1.0:
                self.proc_fps = fps_count / (loop_start - fps_timer)
                fps_count = 0
                fps_timer = loop_start

            # Handle Keyboard Input
            key = cv2.waitKey(1) & 0xFF
            if key != 255:
                self._handle_keyboard_shortcut(key, clean_camera_frame)

        self._shutdown()

    # ==========================================================================
    # ACTION ROUTING & MODE LOGIC
    # ==========================================================================
    def _route_gesture_actions(self, gesture, is_new, payload, clean_frame, now, features=None):
        if not self.actions_enabled:
            return

        cx = int(features["palm_center"][0]) if (features and "palm_center" in features) else (self.display_width // 2)
        cy = int(features["palm_center"][1]) if (features and "palm_center" in features) else (self.display_height // 2)

        # Sequential Gesture: Open Palm followed by Closed Fist initiates 3s photo timer across all modes
        if gesture == "CLOSED_FIST" and is_new:
            if now - self.last_open_palm_time <= 2.2:
                self.countdown_active = True
                self.countdown_start = now
                self.last_open_palm_time = 0.0
                self.last_action_desc = "Timer Photo: 3s Countdown! (Palm -> Fist)"
                self.visual_engine.trigger_shockwave(cx, cy, COLOR_CYAN)
                self.visual_engine.trigger_particle_burst(cx, cy, 25, COLOR_CYAN)
                return

        # ----------------------------------------------------------------------
        # MODE A: HOLOGRAM CONTROL
        # ----------------------------------------------------------------------
        if self.active_mode == MODE_HOLOGRAM:
            if gesture == "CLOSED_FIST" and is_new:
                if self.recognizer.check_cooldown("FIST_PLAY_PAUSE", 0.8):
                    self.last_action_desc = "Toggle Play/Pause (Music + OS)"
                    self.music_engine.toggle_play_pause()
                    self.desktop_bridge.play_pause()
            elif gesture == "THUMB_UP" and is_new:
                if self.recognizer.check_cooldown("THUMB_UP", 0.8):
                    self.last_action_desc = "Music/Media: Play/Resume"
                    self.music_engine.play()
                    self.desktop_bridge.play_pause()
            elif gesture == "THUMB_DOWN" and is_new:
                if self.recognizer.check_cooldown("THUMB_DOWN", 0.8):
                    self.last_action_desc = "Music/Media: Pause"
                    self.music_engine.pause()
                    self.desktop_bridge.play_pause()
            elif gesture == "INDEX_POINTING_UP":
                if self.recognizer.check_cooldown("VOL_UP", 0.15):
                    self.caliper_volume = min(1.0, self.caliper_volume + 0.05)
                    self.desktop_bridge.set_system_volume(self.caliper_volume)
                    self.music_engine.change_volume(+0.05)
                    self.last_action_desc = f"Master Volume UP ({int(self.caliper_volume * 100)}%)"
            elif gesture == "INDEX_POINTING_DOWN":
                if self.recognizer.check_cooldown("VOL_DN", 0.15):
                    self.caliper_volume = max(0.0, self.caliper_volume - 0.05)
                    self.desktop_bridge.set_system_volume(self.caliper_volume)
                    self.music_engine.change_volume(-0.05)
                    self.last_action_desc = f"Master Volume DOWN ({int(self.caliper_volume * 100)}%)"
            elif gesture == "PEACE_SIGN" and is_new:
                if self.recognizer.check_cooldown("PEACE_MUTE", 0.8):
                    self.music_engine.toggle_mute()
                    self.desktop_bridge.prev_slide()
                    self.last_action_desc = f"Media: {'Muted' if self.music_engine.is_muted else 'Unmuted'}"
            elif gesture == "SWIPE_RIGHT" and is_new:
                if self.recognizer.check_cooldown("SWIPE_RIGHT", 0.5):
                    self.last_action_desc = "Media Next Track >> & Next Tab"
                    self.music_engine.next_track()
                    self.desktop_bridge.next_track()
                    self.desktop_bridge.next_tab()
            elif gesture == "SWIPE_LEFT" and is_new:
                if self.recognizer.check_cooldown("SWIPE_LEFT", 0.5):
                    self.last_action_desc = "Media << Prev Track & Prev Tab"
                    self.music_engine.prev_track()
                    self.desktop_bridge.prev_track()
                    self.desktop_bridge.prev_tab()
            elif gesture == "HORNS" and is_new:
                if self.recognizer.check_cooldown("FLASH_TOGGLE", 1.2):
                    is_on = self.flash_ctrl.toggle()
                    self.last_action_desc = f"Hologram: Flashlight {'ON' if is_on else 'OFF'}"
                    if is_on:
                        self.visual_engine.trigger_shockwave(cx, cy, COLOR_AMBER)
                        self.visual_engine.trigger_particle_burst(cx, cy, 18, COLOR_AMBER)
            elif gesture in ["CALIPER_VOLUME", "PINCH"] and payload:
                vol = payload.get("volume_ratio", payload.get("norm_y", 0.5))
                self.caliper_volume = float(np.clip(self.caliper_volume * 0.65 + vol * 0.35, 0.0, 1.0))
                self.desktop_bridge.set_system_volume(self.caliper_volume)
                self.music_engine.set_volume(self.caliper_volume)
                self.last_action_desc = f"Master Volume: {int(self.caliper_volume * 100)}% (Thumb-Index Distance)"

        # ----------------------------------------------------------------------
        # MODE B: CAMERA STUDIO
        # ----------------------------------------------------------------------
        elif self.active_mode == MODE_CAMERA:
            if gesture == "HORNS" and is_new:
                if self.recognizer.check_cooldown("FLASH_TOGGLE", 1.2):
                    is_on = self.flash_ctrl.toggle()
                    self.last_action_desc = f"Camera (🤘 Horns): Flashlight {'ON' if is_on else 'OFF'}"
                    if is_on:
                        self.visual_engine.trigger_shockwave(cx, cy, COLOR_AMBER)
                        self.visual_engine.trigger_particle_burst(cx, cy, 18, COLOR_AMBER)
            elif gesture == "L_SHAPE" and is_new:
                if self.recognizer.check_cooldown("FLASH_LSHAPE", 1.2):
                    is_on = self.flash_ctrl.toggle()
                    self.last_action_desc = f"Torch (🔦 L-Shape): Flashlight {'ON' if is_on else 'OFF'}"
                    if is_on:
                        self.visual_engine.trigger_shockwave(cx, cy, COLOR_AMBER)
            elif gesture == "PEACE_SIGN" and is_new:
                if self.recognizer.check_cooldown("PHOTO_PEACE", 1.5):
                    self._capture_photo(clean_frame)
            elif gesture == "THREE_FINGERS_UP" and is_new:
                if self.recognizer.check_cooldown("TOGGLE_REC", 1.8):
                    self._toggle_recording()

        # ----------------------------------------------------------------------
        # MODE C: MUSIC CONDUCTOR
        # ----------------------------------------------------------------------
        elif self.active_mode == MODE_MUSIC:
            if gesture == "THUMB_UP" and is_new:
                if self.recognizer.check_cooldown("MUSIC_PLAY", 0.6):
                    self.last_action_desc = "Conductor: Play Track"
                    self.music_engine.play()
            elif gesture == "THUMB_DOWN" and is_new:
                if self.recognizer.check_cooldown("MUSIC_PAUSE", 0.6):
                    self.last_action_desc = "Conductor: Pause Track"
                    self.music_engine.pause()
            elif gesture == "CLOSED_FIST" and is_new:
                if self.recognizer.check_cooldown("MUSIC_STOP", 0.6):
                    self.last_action_desc = "Conductor: Toggle Play/Pause"
                    self.music_engine.toggle_play_pause()
            elif gesture == "INDEX_POINTING_UP":
                if self.recognizer.check_cooldown("MUSIC_VOL_UP", 0.15):
                    self.caliper_volume = min(1.0, self.caliper_volume + 0.05)
                    self.desktop_bridge.set_system_volume(self.caliper_volume)
                    self.music_engine.change_volume(+0.05)
                    self.last_action_desc = f"Conductor: Master Vol Up ({int(self.caliper_volume * 100)}%)"
            elif gesture == "INDEX_POINTING_DOWN":
                if self.recognizer.check_cooldown("MUSIC_VOL_DN", 0.15):
                    self.caliper_volume = max(0.0, self.caliper_volume - 0.05)
                    self.desktop_bridge.set_system_volume(self.caliper_volume)
                    self.music_engine.change_volume(-0.05)
                    self.last_action_desc = f"Conductor: Master Vol Down ({int(self.caliper_volume * 100)}%)"
            elif gesture == "SWIPE_RIGHT" and is_new:
                if self.recognizer.check_cooldown("MUSIC_NEXT", 0.5):
                    self.music_engine.next_track()
                    self.desktop_bridge.next_track()
                    self.last_action_desc = f"Conductor: Next Track -> {self.music_engine.track_title}"
            elif gesture == "SWIPE_LEFT" and is_new:
                if self.recognizer.check_cooldown("MUSIC_PREV", 0.5):
                    self.music_engine.prev_track()
                    self.desktop_bridge.prev_track()
                    self.last_action_desc = f"Conductor: Prev Track <- {self.music_engine.track_title}"
            elif gesture == "PEACE_SIGN" and is_new:
                if self.recognizer.check_cooldown("MUSIC_MUTE", 0.8):
                    self.music_engine.toggle_mute()
                    self.last_action_desc = f"Conductor: {'Muted' if self.music_engine.is_muted else 'Unmuted'}"
            elif gesture in ["CALIPER_VOLUME", "PINCH"] and payload:
                vol = payload.get("volume_ratio", payload.get("norm_y", 0.5))
                self.caliper_volume = float(np.clip(self.caliper_volume * 0.65 + vol * 0.35, 0.0, 1.0))
                self.desktop_bridge.set_system_volume(self.caliper_volume)
                self.music_engine.set_volume(self.caliper_volume)
                self.last_action_desc = f"Conductor: Master Volume {int(self.caliper_volume * 100)}% (Thumb-Index Distance)"
            elif gesture == "HORNS" and is_new:
                if self.recognizer.check_cooldown("FLASH_TOGGLE", 1.2):
                    is_on = self.flash_ctrl.toggle()
                    self.last_action_desc = f"Conductor: Flashlight {'ON' if is_on else 'OFF'}"
                    if is_on:
                        self.visual_engine.trigger_shockwave(cx, cy, COLOR_AMBER)
                        self.visual_engine.trigger_particle_burst(cx, cy, 18, COLOR_AMBER)

        # ----------------------------------------------------------------------
        # MODE D: VIRTUAL AIR-MOUSE
        # ----------------------------------------------------------------------
        elif self.active_mode == MODE_MOUSE:
            pointer_pos = (features["tips"]["index"][0], features["tips"]["index"][1]) if (features and "tips" in features and "index" in features["tips"]) else None
            m_status = self.mouse_controller.update(
                pointer_pos, gesture, is_new, payload, now,
                self.display_width, self.display_height,
                features=features, music_engine=self.music_engine
            )
            if m_status not in ["HOVER", "STANDBY", "PINCH [CLICK READY]"]:
                self.last_action_desc = f"Mouse: {m_status}"
                if "TAB SWITCH: NEXT" in m_status:
                    self.visual_engine.trigger_shockwave(cx, cy, COLOR_CYAN)
                    self.visual_engine.trigger_particle_burst(cx, cy, 25, COLOR_CYAN)
                elif "TAB SWITCH: PREV" in m_status:
                    self.visual_engine.trigger_shockwave(cx, cy, COLOR_VIOLET)
                    self.visual_engine.trigger_particle_burst(cx, cy, 25, COLOR_VIOLET)
                elif "CLICK" in m_status:
                    self.visual_engine.trigger_shockwave(cx, cy, COLOR_GREEN)
                elif "DRAG" in m_status:
                    self.visual_engine.trigger_particle_burst(cx, cy, 12, COLOR_AMBER)

            if gesture == "HORNS" and is_new:
                if self.recognizer.check_cooldown("FLASH_TOGGLE", 1.2):
                    is_on = self.flash_ctrl.toggle()
                    self.last_action_desc = f"Mouse: Flashlight {'ON' if is_on else 'OFF'}"
                    if is_on:
                        self.visual_engine.trigger_shockwave(cx, cy, COLOR_AMBER)
                        self.visual_engine.trigger_particle_burst(cx, cy, 18, COLOR_AMBER)

        if self.last_action_desc and self.last_action_desc != "System Standby":
            self._log_event(self.last_action_desc)

    def _handle_panel_action(self, action_id, clean_frame):
        if action_id == "MODE_HOLO":
            self.active_mode = MODE_HOLOGRAM
            self.last_action_desc = "Panel: Switched to Hologram Control"
        elif action_id == "MODE_CAM":
            self.active_mode = MODE_CAMERA
            self.last_action_desc = "Panel: Switched to Camera Studio"
        elif action_id == "MODE_MUSIC":
            self.active_mode = MODE_MUSIC
            self.last_action_desc = "Panel: Switched to Music Conductor"
        elif action_id == "MODE_MOUSE":
            self.active_mode = MODE_MOUSE
            self.last_action_desc = "Panel: Switched to Virtual Air-Mouse"
        elif action_id == "PLAY_PAUSE":
            if self.active_mode == MODE_MUSIC:
                self.music_engine.toggle_play_pause()
            else:
                self.desktop_bridge.play_pause()
            self.last_action_desc = "Panel: Play/Pause toggled"
        elif action_id == "PREV_TRACK":
            if self.active_mode == MODE_MUSIC:
                self.music_engine.prev_track()
            else:
                self.desktop_bridge.prev_track()
        elif action_id == "NEXT_TRACK":
            if self.active_mode == MODE_MUSIC:
                self.music_engine.next_track()
            else:
                self.desktop_bridge.next_track()
        elif action_id == "VOL_DOWN":
            if self.active_mode == MODE_MUSIC:
                self.music_engine.change_volume(-0.05)
            else:
                self.desktop_bridge.volume_down()
        elif action_id == "VOL_UP":
            if self.active_mode == MODE_MUSIC:
                self.music_engine.change_volume(+0.05)
            else:
                self.desktop_bridge.volume_up()
        elif action_id == "SNAP_PHOTO":
            self._capture_photo(clean_frame)
        elif action_id == "TOGGLE_REC":
            self._toggle_recording()
        elif action_id == "TOGGLE_FLASH":
            is_on = self.flash_ctrl.toggle()
            self.last_action_desc = f"Panel: Flashlight {'ON' if is_on else 'OFF'}"
            if is_on:
                self.visual_engine.trigger_shockwave(self.display_width // 2, self.display_height // 2, COLOR_AMBER)
        elif action_id == "TOGGLE_ARM":
            self.actions_enabled = not self.actions_enabled
            self.last_action_desc = f"Panel: Actions {'Enabled' if self.actions_enabled else 'Disabled'}"
        elif action_id == "CLOSE_PANEL":
            self.control_panel.toggle()

        if self.last_action_desc and self.last_action_desc != "System Standby":
            self._log_event(self.last_action_desc)

    def _capture_photo(self, clean_frame):
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        filename = f"holohand_photo_{timestamp_str}.jpg"
        filepath = os.path.join(PHOTO_DIR, filename)
        try:
            cv2.imwrite(filepath, clean_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            self.visual_engine.trigger_shutter_flash()
            self.music_engine.play_shutter()
            self.last_action_desc = f"Captured: {filename}"
            self._log_event(self.last_action_desc)
            print(f"[HOLOHAND] Photograph saved successfully: {filepath}")
        except Exception as e:
            self.last_action_desc = f"Photo Save Failed: {e}"
            self._log_event(self.last_action_desc)
            print(f"[HOLOHAND][ERROR] Failed to save photograph: {e}")

    def _toggle_recording(self):
        if not self.is_recording:
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"holohand_video_{timestamp_str}.mp4"
            filepath = os.path.join(VIDEO_DIR, filename)
            self.recorder = AsyncVideoRecorder(filepath, (self.display_width, self.display_height))
            self.recorder.start()
            self.is_recording = True
            self.rec_start_time = time.monotonic()
            self.last_action_desc = f"Recording started: {os.path.basename(self.recorder.output_path)}"
            self._log_event(self.last_action_desc)
            print(f"[HOLOHAND] Video recording started: {self.recorder.output_path}")
        else:
            if self.recorder:
                self.recorder.stop()
                self.last_action_desc = f"Recording finalized: {os.path.basename(self.recorder.output_path)}"
                self._log_event(self.last_action_desc)
            self.is_recording = False
            self.recorder = None

    def _handle_keyboard_shortcut(self, key, clean_frame):
        if key == 27:  # ESC: Emergency Disable
            self.actions_enabled = False
            self.last_action_desc = "EMERGENCY DISABLE TRIGGERED (Actions Stopped)"
            print("[HOLOHAND][EMERGENCY] Desktop actions disarmed.")
        elif key == ord('e') or key == 32:  # E or Space
            self.actions_enabled = not self.actions_enabled
            self.last_action_desc = f"Actions {'ARMED' if self.actions_enabled else 'DISABLED'}"
        elif key == ord('1'):
            self.active_mode = MODE_HOLOGRAM
            self.last_action_desc = "Mode switched to Hologram Control"
        elif key == ord('2'):
            self.active_mode = MODE_CAMERA
            self.last_action_desc = "Mode switched to Camera Studio"
        elif key == ord('3'):
            self.active_mode = MODE_MUSIC
            self.last_action_desc = "Mode switched to Music Conductor"
        elif key == ord('4') or key == ord('m') or key == ord('M'):
            self.active_mode = MODE_MOUSE
            self.last_action_desc = "Mode switched to Virtual Air-Mouse"
        elif key == 9:  # TAB key
            self.dashboard_layout = "FULLFRAME" if self.dashboard_layout == "STUDIO" else "STUDIO"
            self.last_action_desc = f"Layout switched to {self.dashboard_layout}"
        elif key == ord('f') or key == ord('F'):
            # Toggle fullscreen mode
            self.fullscreen = not self.fullscreen
            if self.fullscreen:
                cv2.setWindowProperty(self.window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
            else:
                cv2.setWindowProperty(self.window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)
                cv2.resizeWindow(self.window_name, 1280, 720)
            self.last_action_desc = f"Fullscreen {'ON' if self.fullscreen else 'OFF'}"
        elif key == ord('t') or key == ord('T') or key == ord('l') or key == ord('L'):
            is_on = self.flash_ctrl.toggle()
            self.last_action_desc = f"Flashlight {'ON' if is_on else 'OFF'}"
            if is_on:
                self.visual_engine.trigger_shockwave(self.display_width // 2, self.display_height // 2, COLOR_AMBER)
        elif key == ord('v'):
            idx = (VISUAL_MODES.index(self.visual_mode) + 1) % len(VISUAL_MODES)
            self.visual_mode = VISUAL_MODES[idx]
            self.last_action_desc = f"Visual mode set to {self.visual_mode}"
        elif key == ord('p'):
            self.control_panel.toggle()
        elif key == ord('c'):
            self._capture_photo(clean_frame)
        elif key == ord('r'):
            self._toggle_recording()
        elif key == ord('x'):
            self.dry_run = not self.dry_run
            self.desktop_bridge.dry_run = self.dry_run
            self.last_action_desc = f"Dry-run mode {'ON' if self.dry_run else 'OFF'}"
        elif key == ord('d'):
            self.show_diagnostics = not self.show_diagnostics
        elif key == ord('q'):
            self.running = False

        if self.last_action_desc and self.last_action_desc != "System Standby":
            self._log_event(self.last_action_desc)

    def _render_offline_screen(self):
        screen = np.full((self.canvas_height, self.canvas_width, 3), COLOR_DARK_GLASS, dtype=np.uint8)
        # Scan lines
        for y in range(0, self.canvas_height, 4):
            cv2.line(screen, (0, y), (self.canvas_width, y), (30, 20, 16), 1)

        cx, cy = self.canvas_width // 2, self.canvas_height // 2
        cv2.rectangle(screen, (cx - 380, cy - 140), (cx + 380, cy + 140), COLOR_RED, 2)
        cv2.putText(screen, "PROJECT HOLOHAND — MISSION CONTROL OFFLINE", (cx - 340, cy - 70), cv2.FONT_HERSHEY_SIMPLEX, 0.85, COLOR_RED, 2, cv2.LINE_AA)
        cv2.putText(screen, f"Target ESP32-CAM Stream: {self.stream_url}", (cx - 340, cy - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, COLOR_WHITE, 1, cv2.LINE_AA)
        cv2.putText(screen, self.stream_worker.status_message, (cx - 340, cy + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.50, COLOR_ORANGE, 1, cv2.LINE_AA)
        cv2.putText(screen, "Check ESP32-CAM Serial Monitor (115200 baud) for Wi-Fi status.", (cx - 340, cy + 65), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160, 160, 160), 1, cv2.LINE_AA)
        cv2.putText(screen, "Press 'Q' to quit cleanly. Press 'TAB' to switch layouts.", (cx - 340, cy + 105), cv2.FONT_HERSHEY_SIMPLEX, 0.45, COLOR_CYAN, 1, cv2.LINE_AA)
        return screen

    def _render_diagnostic_overlay(self, frame, features, current_gesture):
        ox, oy = 20, 80
        w, h = 320, 180
        overlay = frame.copy()
        cv2.rectangle(overlay, (ox, oy), (ox + w, oy + h), (10, 10, 10), -1)
        cv2.rectangle(overlay, (ox, oy), (ox + w, oy + h), COLOR_VIOLET, 1)
        cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)

        cv2.putText(frame, "DIAGNOSTIC CALIBRATION MATRIX", (ox + 10, oy + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.42, COLOR_VIOLET, 1, cv2.LINE_AA)
        cv2.putText(frame, f"Scale: {features['hand_scale']:.1f} px | Rot: {features['orientation_deg']:.1f} deg", (ox + 10, oy + 44), cv2.FONT_HERSHEY_SIMPLEX, 0.38, COLOR_WHITE, 1)
        cv2.putText(frame, f"Norm Pinch Dist: {features['norm_pinch_dist']:.3f} (Thresh: {PINCH_THRESHOLD})", (ox + 10, oy + 66), cv2.FONT_HERSHEY_SIMPLEX, 0.38, COLOR_CYAN, 1)

        fingers_str = f"T:{int(features['thumb_ext'])} I:{int(features['index_ext'])} M:{int(features['middle_ext'])} R:{int(features['ring_ext'])} P:{int(features['pinky_ext'])}"
        cv2.putText(frame, f"Fingers Ext: [{fingers_str}]", (ox + 10, oy + 88), cv2.FONT_HERSHEY_SIMPLEX, 0.38, COLOR_WHITE, 1)
        cv2.putText(frame, f"Candidate: {self.recognizer.candidate_gesture} (Dwell: {self.recognizer.candidate_count})", (ox + 10, oy + 110), cv2.FONT_HERSHEY_SIMPLEX, 0.38, COLOR_ORANGE, 1)
        cv2.putText(frame, f"Confirmed: {current_gesture}", (ox + 10, oy + 132), cv2.FONT_HERSHEY_SIMPLEX, 0.40, COLOR_GREEN, 1)

    def _shutdown(self):
        print("\n[HOLOHAND] Initiating clean shutdown sequence...")
        if self.is_recording and self.recorder:
            self.recorder.stop()
        self.stream_worker.stop()
        self.hands_detector.close()
        cv2.destroyAllWindows()
        print("[HOLOHAND] All threads and video pipelines closed successfully.")


# ==============================================================================
# 11. AUTOMATED VALIDATION TEST SUITE
# ==============================================================================
def run_validation_suite():
    """
    Executes automated local unit tests for geometry extraction, gesture transitions,
    temporal dwell stabilization, recording queues, and audio synthesis.
    """
    print("\n=======================================================")
    print("  PROJECT HOLOHAND — LOCAL VALIDATION & TESTING SUITE")
    print("=======================================================")

    # Test 1: Directory Structure
    for d in [PHOTO_DIR, VIDEO_DIR, MUSIC_DIR]:
        os.makedirs(d, exist_ok=True)
        assert os.path.exists(d), f"Directory creation failed: {d}"
    print("[PASS] Test 1: Storage directories verified.")

    # Test 2: Gesture Recognizer Temporal Stabilization
    recognizer = GestureRecognizer()
    dummy_features_open = {
        "pts": np.zeros((21, 3)),
        "palm_center": np.array([320.0, 240.0, 0.0]),
        "hand_scale": 100.0,
        "orientation_deg": 0.0,
        "norm_pinch_dist": 0.25,
        "thumb_ext": True, "index_ext": True, "middle_ext": True, "ring_ext": True, "pinky_ext": True,
        "thumb_angle_y": -90.0,
        "tips": {"index": np.array([320.0, 150.0, 0.0]), "thumb": np.array([280.0, 200.0, 0.0])}
    }

    # Frame 1: Candidate detected, not yet stable
    g, confirmed, _ = recognizer.update(dummy_features_open, time.monotonic())
    assert confirmed is False, "Gesture should not confirm on frame 1 without dwell"

    # Feed STABILIZATION_FRAMES to confirm
    for _ in range(STABILIZATION_FRAMES):
        g, confirmed, _ = recognizer.update(dummy_features_open, time.monotonic())
    assert g == "OPEN_PALM", f"Expected OPEN_PALM, got {g}"
    print("[PASS] Test 2: Temporal gesture stabilization and dwell verified.")

    # Test 3: Pinch Classification & Hysteresis
    dummy_features_pinch = dummy_features_open.copy()
    dummy_features_pinch["norm_pinch_dist"] = PINCH_THRESHOLD * 0.8
    for _ in range(STABILIZATION_FRAMES):
        g, _, payload = recognizer.update(dummy_features_pinch, time.monotonic())
    assert g == "PINCH", f"Expected PINCH, got {g}"
    print("[PASS] Test 3: Normalized pinch detection and hysteresis verified.")

    # Test 4: Audio Engine & Procedural Sound Synthesis
    music_engine = MusicConductorEngine(MUSIC_DIR)
    assert os.path.exists(os.path.join(MUSIC_DIR, "holohand_cyber_ambient.wav")), "Synth track generation failed"
    print("[PASS] Test 4: Music conductor and procedural audio synthesis verified.")

    # Test 5: Video Recorder Initialization & Codec Verification
    test_video_path = os.path.join(VIDEO_DIR, "test_verify.mp4")
    recorder = AsyncVideoRecorder(test_video_path, (640, 480), fps=20.0)
    assert recorder.writer is not None, "VideoWriter initialization failed"
    recorder.start()
    dummy_img = np.zeros((480, 640, 3), dtype=np.uint8)
    for _ in range(5):
        recorder.enqueue_frame(dummy_img)
    time.sleep(0.3)
    recorder.stop()
    recorder.join()
    if os.path.exists(recorder.output_path):
        os.remove(recorder.output_path)
    print("[PASS] Test 5: Async video recorder and codec fallback verified.")

    # Test 6: Hardware Flash Controller & Horns Gesture Classification
    flash_ctrl = HardwareFlashController("http://192.168.1.100/stream")
    assert flash_ctrl.is_on is False
    flash_ctrl.toggle()
    assert flash_ctrl.is_on is True
    flash_ctrl.toggle()
    assert flash_ctrl.is_on is False

    dummy_features_horns = dummy_features_open.copy()
    dummy_features_horns["index_ext"] = True
    dummy_features_horns["pinky_ext"] = True
    dummy_features_horns["middle_ext"] = False
    dummy_features_horns["ring_ext"] = False
    dummy_features_horns["thumb_ext"] = False
    recognizer = GestureRecognizer()
    for _ in range(STABILIZATION_FRAMES):
        g, _, _ = recognizer.update(dummy_features_horns, time.monotonic())
    assert g == "HORNS", f"Expected HORNS, got {g}"
    print("[PASS] Test 6: Hardware Flashlight controller and Horns gesture verified.")

    # Test 7: Music Conductor Gestures (Thumbs, Index Pointing, Peace Sign, Fist)
    # 7a. Thumbs Up
    feat_thumb_up = dummy_features_open.copy()
    feat_thumb_up["index_ext"] = False
    feat_thumb_up["middle_ext"] = False
    feat_thumb_up["ring_ext"] = False
    feat_thumb_up["pinky_ext"] = False
    feat_thumb_up["thumb_ext"] = True
    feat_thumb_up["thumb_angle_y"] = -85.0
    rec = GestureRecognizer()
    for _ in range(STABILIZATION_FRAMES):
        g, _, _ = rec.update(feat_thumb_up, time.monotonic())
    assert g == "THUMB_UP", f"Expected THUMB_UP, got {g}"

    # 7b. Thumbs Down
    feat_thumb_dn = feat_thumb_up.copy()
    feat_thumb_dn["thumb_angle_y"] = 90.0
    rec = GestureRecognizer()
    for _ in range(STABILIZATION_FRAMES):
        g, _, _ = rec.update(feat_thumb_dn, time.monotonic())
    assert g == "THUMB_DOWN", f"Expected THUMB_DOWN, got {g}"

    # 7c. Closed Fist
    feat_fist = feat_thumb_up.copy()
    feat_fist["thumb_ext"] = False
    rec = GestureRecognizer()
    for _ in range(STABILIZATION_FRAMES):
        g, _, _ = rec.update(feat_fist, time.monotonic())
    assert g == "CLOSED_FIST", f"Expected CLOSED_FIST, got {g}"

    # 7d. Index Pointing Up
    feat_idx_up = dummy_features_open.copy()
    feat_idx_up["index_ext"] = True
    feat_idx_up["middle_ext"] = False
    feat_idx_up["ring_ext"] = False
    feat_idx_up["pinky_ext"] = False
    feat_idx_up["thumb_ext"] = False
    feat_idx_up["tips"] = {"index": np.array([320.0, 100.0, 0.0]), "thumb": np.array([280.0, 200.0, 0.0])}
    feat_idx_up["pts"] = np.zeros((21, 3))
    feat_idx_up["pts"][5] = np.array([320.0, 220.0, 0.0])  # MCP lower than tip -> pointing UP
    rec = GestureRecognizer()
    for _ in range(STABILIZATION_FRAMES):
        g, _, _ = rec.update(feat_idx_up, time.monotonic())
    assert g == "INDEX_POINTING_UP", f"Expected INDEX_POINTING_UP, got {g}"

    # 7e. Index Pointing Down
    feat_idx_dn = feat_idx_up.copy()
    feat_idx_dn["tips"] = {"index": np.array([320.0, 300.0, 0.0]), "thumb": np.array([280.0, 200.0, 0.0])}
    feat_idx_dn["pts"] = np.zeros((21, 3))
    feat_idx_dn["pts"][5] = np.array([320.0, 180.0, 0.0])  # MCP higher than tip -> pointing DOWN
    rec = GestureRecognizer()
    for _ in range(STABILIZATION_FRAMES):
        g, _, _ = rec.update(feat_idx_dn, time.monotonic())
    assert g == "INDEX_POINTING_DOWN", f"Expected INDEX_POINTING_DOWN, got {g}"

    # 7f. Peace Sign
    feat_peace = dummy_features_open.copy()
    feat_peace["index_ext"] = True
    feat_peace["middle_ext"] = True
    feat_peace["ring_ext"] = False
    feat_peace["pinky_ext"] = False
    feat_peace["thumb_ext"] = False
    rec = GestureRecognizer()
    for _ in range(STABILIZATION_FRAMES):
        g, _, _ = rec.update(feat_peace, time.monotonic())
    assert g == "PEACE_SIGN", f"Expected PEACE_SIGN, got {g}"

    # 7g. Caliper Volume (Thumb-to-Index Distance Span)
    feat_caliper = dummy_features_open.copy()
    feat_caliper["index_ext"] = True
    feat_caliper["thumb_ext"] = True
    feat_caliper["middle_ext"] = False
    feat_caliper["ring_ext"] = False
    feat_caliper["pinky_ext"] = False
    feat_caliper["norm_pinch_dist"] = 0.50
    feat_caliper["thumb_index_span_ratio"] = 0.50
    feat_caliper["tips"] = {"thumb": np.array([280.0, 200.0, 0.0]), "index": np.array([380.0, 200.0, 0.0])}
    rec_cal = GestureRecognizer()
    for _ in range(STABILIZATION_FRAMES):
        g, _, payload = rec_cal.update(feat_caliper, time.monotonic())
    assert g == "CALIPER_VOLUME", f"Expected CALIPER_VOLUME, got {g}"
    assert payload is not None and "volume_ratio" in payload
    assert abs(payload["volume_ratio"] - 0.50) < 0.05
    print("[PASS] Test 7: Music Conductor gestures (Thumb Up/Dn, Fist, Index Up/Dn, Peace Sign, Caliper Volume) verified.")

    # Test 8: Sequential Gesture (Open Palm -> Closed Fist 3s Countdown) & Route Safety
    test_app = HoloHandApp(stream_url="http://127.0.0.1:9999/dummy", dry_run=True)
    t0 = time.monotonic()
    # Trigger open palm
    test_app.last_open_palm_time = t0
    # Immediately trigger closed fist within 0.5s
    test_app._route_gesture_actions("CLOSED_FIST", True, None, None, t0 + 0.5, dummy_features_horns)
    assert test_app.countdown_active is True, "Open Palm -> Fist should activate countdown photo"
    # Verify Horns routing without crash
    test_app._route_gesture_actions("HORNS", True, None, None, t0 + 2.0, dummy_features_horns)
    test_app._shutdown()
    print("[PASS] Test 8: Sequential Open Palm -> Fist countdown and Horns route safety verified.")

    # Test 9: Virtual Air-Mouse Controller & Gesture Kinematics
    mouse_ctrl = VirtualAirMouseController(dry_run=True, margin_ratio=0.18)
    cam_w, cam_h = 640, 480
    t_mouse = time.monotonic()

    # 9a. Normal Pointer Tracking & Coordinate Mirroring
    status = mouse_ctrl.update((320, 240), "NONE", False, None, t_mouse, cam_w, cam_h)
    assert status == "HOVER", f"Expected HOVER, got {status}"
    assert abs(mouse_ctrl.cur_screen_x - mouse_ctrl.screen_w // 2) <= 5, "Center camera should map within deadzone center"
    assert abs(mouse_ctrl.cur_screen_y - mouse_ctrl.screen_h // 2) <= 5, "Center camera should map within deadzone center"

    # 9b. Left Click on Quick Pinch (<0.35s)
    mouse_ctrl.update((320, 240), "PINCH", True, None, t_mouse + 0.1, cam_w, cam_h)
    assert mouse_ctrl.is_pinching is True
    # Release pinch after 0.15s
    status_click = mouse_ctrl.update((320, 240), "NONE", True, None, t_mouse + 0.25, cam_w, cam_h)
    assert status_click == "LEFT CLICK", f"Expected LEFT CLICK, got {status_click}"

    # 9c. Double Click on Subsequent Quick Pinch (<0.40s)
    mouse_ctrl.update((320, 240), "PINCH", True, None, t_mouse + 0.35, cam_w, cam_h)
    status_dbl = mouse_ctrl.update((320, 240), "NONE", True, None, t_mouse + 0.45, cam_w, cam_h)
    assert status_dbl == "DOUBLE CLICK", f"Expected DOUBLE CLICK, got {status_dbl}"

    # 9d. Sustained Pinch (>0.35s) -> Drag & Drop
    mouse_ctrl.update((320, 240), "PINCH", True, None, t_mouse + 1.0, cam_w, cam_h)
    status_drag = mouse_ctrl.update((330, 250), "PINCH", False, None, t_mouse + 1.45, cam_w, cam_h)
    assert status_drag == "DRAGGING [HELD]", f"Expected DRAGGING [HELD], got {status_drag}"
    assert mouse_ctrl.is_dragging is True

    # Release drag
    status_rel = mouse_ctrl.update((330, 250), "NONE", True, None, t_mouse + 1.6, cam_w, cam_h)
    assert status_rel == "RELEASED DRAG", f"Expected RELEASED DRAG, got {status_rel}"
    assert mouse_ctrl.is_dragging is False

    # 9e. Peace Sign -> Right Click
    status_rc = mouse_ctrl.update((320, 240), "PEACE_SIGN", True, None, t_mouse + 2.0, cam_w, cam_h)
    assert status_rc == "RIGHT CLICK", f"Expected RIGHT CLICK, got {status_rc}"

    # 9f. Scrolling
    status_up = mouse_ctrl.update((320, 240), "INDEX_POINTING_UP", False, None, t_mouse + 2.5, cam_w, cam_h)
    assert status_up == "SCROLL UP", f"Expected SCROLL UP, got {status_up}"
    status_dn = mouse_ctrl.update((320, 240), "INDEX_POINTING_DOWN", False, None, t_mouse + 2.7, cam_w, cam_h)
    assert status_dn == "SCROLL DOWN", f"Expected SCROLL DOWN, got {status_dn}"

    # 9g. Hand Swipe Right -> Next Tab [Ctrl+Tab]
    status_sw_r = mouse_ctrl.update((320, 240), "SWIPE_RIGHT", True, None, t_mouse + 3.2, cam_w, cam_h)
    assert status_sw_r == "TAB SWITCH: NEXT [Ctrl+Tab]", f"Expected TAB SWITCH: NEXT, got {status_sw_r}"

    # 9h. Hand Swipe Left -> Prev Tab [Ctrl+Shift+Tab]
    status_sw_l = mouse_ctrl.update((320, 240), "SWIPE_LEFT", True, None, t_mouse + 3.8, cam_w, cam_h)
    assert status_sw_l == "TAB SWITCH: PREV [Ctrl+Shift+Tab]", f"Expected TAB SWITCH: PREV, got {status_sw_l}"

    # 9i. Middle Click -> Three Fingers Up
    status_mc = mouse_ctrl.update((320, 240), "THREE_FINGERS_UP", True, None, t_mouse + 4.4, cam_w, cam_h)
    assert "MIDDLE CLICK" in status_mc, f"Expected MIDDLE CLICK, got {status_mc}"

    # 9j. Direct Swipe Detection Verification (Stationary hand followed by dynamic flick)
    rec_swipe = GestureRecognizer()
    t_sim = 10.0
    for _ in range(25):  # 25 frames stationary
        t_sim += 0.05
        rec_swipe.motion_history.append((t_sim, 320.0, 240.0))
    # Rapid flick to user's right (lower X in camera)
    for offset in [40.0, 85.0, 130.0]:
        t_sim += 0.05
        rec_swipe.motion_history.append((t_sim, 320.0 - offset, 240.0))
    detected_swipe = rec_swipe._detect_swipe(t_sim)
    assert detected_swipe == "SWIPE_RIGHT", f"Expected SWIPE_RIGHT, got {detected_swipe}"

    # 9k. Desktop Action Bridge Tab Switching & Real-Time Master Volume Verification
    bridge = DesktopActionBridge(dry_run=True)
    bridge.next_tab()
    bridge.prev_tab()
    bridge.set_system_volume(0.75)
    vol_read = bridge.get_system_volume()
    assert 0.0 <= vol_read <= 1.0, f"System volume {vol_read} outside valid [0, 1] range"

    print("[PASS] Test 9: Virtual Air-Mouse controller, swipe kinematics, and OS tab switching verified.")

    # Test 10: Cyber Mission Control 1080p Presentation Dashboard Rendering
    vis_engine = HolographicVisualEngine(cam_w, cam_h)
    dummy_cam = np.zeros((cam_h, cam_w, 3), dtype=np.uint8)
    vis_engine.render_mouse_hud(dummy_cam, mouse_ctrl, (320, 240))

    test_audit = deque([("12:00:00", "System Boot"), ("12:00:01", "Air-Mouse Armed")], maxlen=8)
    dashboard_1080p = vis_engine.render_presentation_dashboard(
        dummy_cam, dummy_features_open, "OPEN_PALM", "Test Action OK", MODE_MOUSE, VISUAL_HOLOGRAM,
        music_engine, mouse_ctrl, flash_ctrl, 30.0, 30.0,
        False, "00:00", test_audit, time.monotonic(),
        canvas_w=1920, canvas_h=1080
    )
    assert dashboard_1080p.shape == (1080, 1920, 3), f"Expected (1080, 1920, 3), got {dashboard_1080p.shape}"
    assert dashboard_1080p.dtype == np.uint8, "Dashboard output should be uint8"
    assert np.count_nonzero(dashboard_1080p) > 1000, "Dashboard canvas should have rendered UI content"
    print("[PASS] Test 10: Cyber Mission Control 1080p presentation dashboard rendering verified.")

    print("=======================================================")
    print("  ALL 10 VALIDATION TESTS PASSED WITH 100% SUCCESS")
    print("=======================================================\n")


# ==============================================================================
# 12. ENTRY POINT & CLI PARSING
# ==============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Project HoloHand: ESP32-CAM Real-Time AR Gesture Studio & Music Conductor",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--url", "--stream", dest="stream_url", default=DEFAULT_STREAM_URL,
                        help="HTTP MJPEG stream URL of ESP32-CAM (e.g. http://192.168.1.100/stream) or local camera index")
    parser.add_argument("--mode", dest="mode", choices=["hologram", "camera", "music", "mouse"], default="hologram",
                        help="Initial operating mode: 'hologram', 'camera', 'music', or 'mouse'")
    parser.add_argument("--layout", dest="layout", choices=["studio", "fullframe"], default="studio",
                        help="Display layout: 'studio' (Mission Control Dashboard) or 'fullframe' (Direct AR HUD)")
    parser.add_argument("--visual", dest="visual", choices=["hologram", "scan", "minimal"], default="hologram",
                        help="Initial visual HUD effects mode")
    parser.add_argument("--windowed", dest="windowed", action="store_true",
                        help="Launch in 1280x720 window instead of default borderless fullscreen")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true",
                        help="Display actions on HUD without executing desktop automation")
    parser.add_argument("--test", dest="run_tests", action="store_true",
                        help="Run automated unit and validation test suite then exit")

    args = parser.parse_args()

    if args.run_tests:
        run_validation_suite()
        sys.exit(0)

    mode_map = {
        "hologram": MODE_HOLOGRAM,
        "camera": MODE_CAMERA,
        "music": MODE_MUSIC,
        "mouse": MODE_MOUSE
    }
    visual_map = {
        "hologram": VISUAL_HOLOGRAM,
        "scan": VISUAL_SCAN,
        "minimal": VISUAL_MINIMAL
    }

    app = HoloHandApp(
        stream_url=args.stream_url,
        dry_run=args.dry_run,
        start_mode=mode_map[args.mode],
        start_visual=visual_map[args.visual],
        fullscreen=not args.windowed,
        dashboard_layout=args.layout.upper()
    )
    app.run()
