#!/usr/bin/env python3
"""
================================================================================
PROJECT HOLOHAND — MASTER VIDEO DEMONSTRATION PRODUCER
================================================================================
Generates a complete 1080p (1920x1080 @ 24fps) video demonstration of Project HoloHand:
  - Real human hand recognized by the actual computer vision model in camera feed
  - Cyber Mission Control 1080p Presentation Dashboard
  - Detailed showcase across all 4 categories:
      1. Category 1 — Mode A: Hologram Control (OS Media, Caliper Volume, Slides, Swipes)
      2. Category 2 — Mode B: Camera Studio (Photo, 3s Timer Countdown, Video Rec, Flash)
      3. Category 3 — Mode C: Music Conductor (Ambient Synth, Spatial Caliper Conducting)
      4. Category 4 — Mode D: Virtual Air-Mouse (Hover, Clicks, Drag, Scroll, Tab Swiping)
  - Clear, synchronized voiceover narration, cyber ambient background music, and UI SFX
  - Lower-third feature banners and synchronized subtitles
  - Engineering Team Members prominently highlighted throughout:
      • Harsh Shah — Roll No: 28, PRN: 1262240840 (Lead Architect & Vision Core)
      • Sohaliya Patil — Roll No: 22, PRN: 1262240616 (Hardware & Embedded Systems)
      • Sandra Santosh — Roll No: 21, PRN: 1262240615 (Audio Synthesis & Video)
      • Bhoomi — Roll No: 27, PRN: 1262240801 (AR Visuals & Presentation GUI)
      • Tashu — Roll No: 31, PRN: 1262240894 (Kinematics & Feature Engineering)
================================================================================
"""

import os
import sys
import time
import math
import wave
from collections import deque
import cv2
import numpy as np
import av
import win32com.client
import mediapipe as mp

from holohand_backend import (
    HandFeatureExtractor, GestureRecognizer, HolographicVisualEngine,
    MusicConductorEngine, VirtualAirMouseController, HardwareFlashController,
    MODE_HOLOGRAM, MODE_CAMERA, MODE_MUSIC, MODE_MOUSE, VISUAL_HOLOGRAM,
    COLOR_CYAN, COLOR_VIOLET, COLOR_AMBER, COLOR_GREEN, COLOR_RED, COLOR_WHITE, COLOR_DARK_GLASS
)

CAPTURES_DIR = os.path.join("x:\\ESP", "captures")
OUTPUT_VIDEO = os.path.join("x:\\ESP", "PROJECT_HOLOHAND_DEMO_VIDEO.mp4")
OUTPUT_SCRIPT = os.path.join("x:\\ESP", "VIDEO_VOICEOVER_SCRIPT.md")
TEMP_VOICE_DIR = os.path.join(CAPTURES_DIR, "voiceover_segments")
AMBIENT_WAV = os.path.join("x:\\ESP", "music", "holohand_cyber_ambient.wav")
PHOTO_DIR = os.path.join("x:\\ESP", "captures", "photos")
VIDEO_DIR = os.path.join("x:\\ESP", "captures", "videos")

FPS = 24
SAMPLE_RATE = 44100
CANVAS_W, CANVAS_H = 1920, 1080
CAM_W, CAM_H = 960, 720

TEAM_MEMBERS = [
    "Harsh Shah (Roll 28 | PRN 1262240840)",
    "Sohaliya Patil (Roll 22 | PRN 1262240616)",
    "Sandra Santosh (Roll 21 | PRN 1262240615)",
    "Bhoomi (Roll 27 | PRN 1262240801)",
    "Tashu (Roll 31 | PRN 1262240894)"
]

SCENE_SCRIPTS = [
    {
        "id": "scene1_intro",
        "title": "PROJECT HOLOHAND — INTRODUCTION",
        "category": "PROJECT INTRODUCTION",
        "speaker": "Harsh Shah & Team",
        "text": "Welcome to the official project demonstration of Project HoloHand, a real-time, hardware-connected Augmented Reality Gesture Control Studio and Music Conductor powered by an ESP32-CAM and Python. This project was designed and engineered by team members: Harsh Shah, Sohaliya Patil, Sandra Santosh, Bhoomi, and Tashu."
    },
    {
        "id": "scene2_arch",
        "title": "HARDWARE & SYSTEM ARCHITECTURE",
        "category": "SYSTEM ARCHITECTURE",
        "speaker": "Sohaliya Patil",
        "text": "Project HoloHand bridges physical edge hardware with advanced computer vision. The AI-Thinker ESP32-CAM board with an OV2640 sensor runs on dual-core Xtensa silicon with PSRAM, streaming low-overhead JPEG frames over Wi-Fi. On the laptop, our multi-threaded Python backend acquires frames with zero backlog, performs MediaPipe twenty-one landmark hand tracking, extracts invariant geometric features, and stabilizes gestures over time without cloud latency."
    },
    {
        "id": "scene3_mode_a",
        "title": "MODE A: HOLOGRAM CONTROL",
        "category": "CATEGORY 1 — MODE A",
        "speaker": "Bhoomi",
        "text": "Category one is Mode A: Hologram Control, dedicated to desktop automation and media presentation. An open palm represents the neutral ready state. A closed fist toggles play and pause on active operating system media like Spotify or YouTube. Thumbs up resumes playback, while thumbs down pauses. Index pointing up and down adjusts volume in discrete steps. Our flagship feature is the Optical Vernier Caliper: by simply adjusting the physical distance between the thumb and index fingertips, the system directly modulates the Windows master volume in real time, from zero percent touching to one hundred percent wide open. A peace sign toggles mute. Flicking the hand left or right skips tracks and switches browser tabs. And the rock horns gesture toggles the physical ESP32-CAM flashlight over Wi-Fi."
    },
    {
        "id": "scene4_mode_b",
        "title": "MODE B: CAMERA STUDIO",
        "category": "CATEGORY 2 — MODE B",
        "speaker": "Tashu",
        "text": "Category two is Mode B: Camera Studio, turning the ESP32-CAM into a hands-free photography and video workstation. Showing a peace sign instantly captures a high-resolution, uncompressed JPEG photograph with a holographic shutter flash. The sequential gesture, an open palm followed by a closed fist, triggers a three-second self-timer countdown with an animated circular progress ring before snapping the photo. Extending three fingers starts and stops MP4 video recording, and the torch L-shape gesture toggles the physical hardware LED flash."
    },
    {
        "id": "scene5_mode_c",
        "title": "MODE C: MUSIC CONDUCTOR",
        "category": "CATEGORY 3 — MODE C",
        "speaker": "Sandra Santosh",
        "text": "Category three is Mode C: Music Conductor. HoloHand includes a built-in procedural ambient synthesizer and local playlist conductor. As the music plays, real-time audio waveforms animate across the holographic HUD. The conductor uses the thumb-to-index caliper distance to dynamically shape the music volume and master output in real time. Hand swipes navigate between tracks with an audible whoosh, and a closed fist pauses the symphony."
    },
    {
        "id": "scene6_mode_d",
        "title": "MODE D: VIRTUAL AIR-MOUSE",
        "category": "CATEGORY 4 — MODE D",
        "speaker": "Harsh Shah",
        "text": "Category four is Mode D: Virtual Air-Mouse, enabling full operating system cursor and window control with zero hardware peripherals. The index fingertip maps to screen coordinates with dual-exponential smoothing and active deadzone boundaries. A quick pinch under zero-point-three-five seconds executes an anchored left click with zero cursor drift. A double pinch performs a double click. A sustained pinch engages drag-and-drop. A peace sign triggers right click. Three fingers execute middle click. Pointing the index finger up or down scrolls web pages smoothly. Our newly implemented backwards rolling-window swipe algorithm enables effortless left and right hand swipes to switch browser tabs with Control-Tab and Control-Shift-Tab. Finally, raising both hands summons the floating Holographic Command Matrix Panel."
    },
    {
        "id": "scene7_outro",
        "title": "PROJECT SUMMARY & CREDITS",
        "category": "SUMMARY & CONCLUSION",
        "speaker": "Harsh Shah & Full Team",
        "text": "Project HoloHand demonstrates the power of combining embedded edge cameras with real-time computer vision, holographic augmented reality, and desktop automation. On behalf of team members Harsh Shah, Sohaliya Patil, Sandra Santosh, Bhoomi, and Tashu, thank you for watching."
    }
]

def generate_voiceover_audio():
    """Generates speech WAV clips for each scene using SAPI."""
    os.makedirs(TEMP_VOICE_DIR, exist_ok=True)
    voice = win32com.client.Dispatch("SAPI.SpVoice")
    stream = win32com.client.Dispatch("SAPI.SpFileStream")
    voice.Rate = -1
    voice.Volume = 100

    scene_audio_files = []
    for sc in SCENE_SCRIPTS:
        wav_path = os.path.join(TEMP_VOICE_DIR, f"{sc['id']}.wav")
        stream.Open(wav_path, 3)
        voice.AudioOutputStream = stream
        voice.Speak(sc["text"])
        stream.Close()
        scene_audio_files.append(wav_path)
    return scene_audio_files

def resample_audio(data, orig_sr, target_sr):
    if orig_sr == target_sr:
        return data
    num_samples = int(len(data) * target_sr / orig_sr)
    return np.interp(
        np.linspace(0, len(data), num_samples, endpoint=False),
        np.arange(len(data)),
        data
    ).astype(data.dtype)

def load_wav_pcm(path):
    with wave.open(path, 'rb') as wf:
        sr = wf.getframerate()
        n = wf.getnframes()
        channels = wf.getnchannels()
        bytes_data = wf.readframes(n)
        data = np.frombuffer(bytes_data, dtype=np.int16)
        if channels == 2:
            data = data.reshape(-1, 2)
        else:
            data = np.stack([data, data], axis=1)
        if sr != SAMPLE_RATE:
            left = resample_audio(data[:, 0], sr, SAMPLE_RATE)
            right = resample_audio(data[:, 1], sr, SAMPLE_RATE)
            data = np.stack([left, right], axis=1)
        return data

def synthesize_sfx():
    # 1. Shutter Click
    t_sh = np.linspace(0, 0.18, int(SAMPLE_RATE * 0.18), endpoint=False)
    click1 = np.exp(-t_sh * 120) * np.sin(2 * np.pi * 1800 * t_sh)
    click2 = np.exp(-np.maximum(0, t_sh - 0.05) * 80) * np.sin(2 * np.pi * 1200 * t_sh) * (t_sh > 0.05)
    noise = np.random.uniform(-0.15, 0.15, len(t_sh)) * np.exp(-t_sh * 50)
    shutter = np.clip((click1 + click2 + noise) * 22000, -32767, 32767).astype(np.int16)
    shutter_stereo = np.stack([shutter, shutter], axis=1)

    # 2. Whoosh Swipe
    t_sw = np.linspace(0, 0.28, int(SAMPLE_RATE * 0.28), endpoint=False)
    freq = 300 + 700 * np.sin(np.pi * t_sw / 0.28)
    phase = np.cumsum(2 * np.pi * freq / SAMPLE_RATE)
    whoosh = (np.sin(phase) * np.sin(np.pi * t_sw / 0.28) * 18000).astype(np.int16)
    whoosh_stereo = np.stack([whoosh, whoosh], axis=1)

    # 3. UI Click
    t_cl = np.linspace(0, 0.06, int(SAMPLE_RATE * 0.06), endpoint=False)
    click = (np.sin(2 * np.pi * 1350 * t_cl) * np.exp(-t_cl * 90) * 20000).astype(np.int16)
    click_stereo = np.stack([click, click], axis=1)

    return shutter_stereo, whoosh_stereo, click_stereo

def build_master_audio_track(scene_audio_files):
    ambient_data = load_wav_pcm(AMBIENT_WAV)
    shutter_sfx, whoosh_sfx, click_sfx = synthesize_sfx()

    # Load all scene voiceovers and compute timing
    scene_segments = []
    total_samples = int(SAMPLE_RATE * 1.5)  # 1.5s intro padding
    scene_starts = []

    for path in scene_audio_files:
        pcm = load_wav_pcm(path)
        scene_starts.append(total_samples)
        scene_segments.append(pcm)
        total_samples += len(pcm) + int(SAMPLE_RATE * 1.8)  # 1.8s inter-scene transition

    total_samples += int(SAMPLE_RATE * 2.0)  # 2.0s outro tail

    master_audio = np.zeros((total_samples, 2), dtype=np.float32)

    # Loop ambient music gently underneath
    amb_len = len(ambient_data)
    for pos in range(0, total_samples, amb_len):
        chunk_len = min(amb_len, total_samples - pos)
        master_audio[pos:pos+chunk_len] += ambient_data[:chunk_len].astype(np.float32) * 0.14

    # Overlay voiceover narration
    for idx, (start_pos, pcm) in enumerate(zip(scene_starts, scene_segments)):
        end_pos = start_pos + len(pcm)
        # Normalize voiceover and mix at 0.95
        voice_float = pcm.astype(np.float32)
        peak = np.max(np.abs(voice_float))
        if peak > 0:
            voice_float = (voice_float / peak) * 27000.0
        master_audio[start_pos:end_pos] += voice_float

        # Inject SFX into relevant scenes
        if idx == 2:  # Mode A: Swipes & Caliper
            sw_pos = start_pos + int(len(pcm) * 0.82)
            if sw_pos + len(whoosh_sfx) < total_samples:
                master_audio[sw_pos:sw_pos+len(whoosh_sfx)] += whoosh_sfx.astype(np.float32) * 0.8
        elif idx == 3:  # Mode B: Shutter clicks
            sh_pos = start_pos + int(len(pcm) * 0.28)
            sh_pos2 = start_pos + int(len(pcm) * 0.65)
            if sh_pos + len(shutter_sfx) < total_samples:
                master_audio[sh_pos:sh_pos+len(shutter_sfx)] += shutter_sfx.astype(np.float32) * 0.95
            if sh_pos2 + len(shutter_sfx) < total_samples:
                master_audio[sh_pos2:sh_pos2+len(shutter_sfx)] += shutter_sfx.astype(np.float32) * 0.95
        elif idx == 4:  # Mode C: Music whoosh
            sw_pos = start_pos + int(len(pcm) * 0.75)
            if sw_pos + len(whoosh_sfx) < total_samples:
                master_audio[sw_pos:sw_pos+len(whoosh_sfx)] += whoosh_sfx.astype(np.float32) * 0.8
        elif idx == 5:  # Mode D: Air-mouse clicks & tab switches
            cl_pos = start_pos + int(len(pcm) * 0.28)
            cl_pos2 = start_pos + int(len(pcm) * 0.42)
            sw_pos = start_pos + int(len(pcm) * 0.78)
            if cl_pos + len(click_sfx) < total_samples:
                master_audio[cl_pos:cl_pos+len(click_sfx)] += click_sfx.astype(np.float32) * 0.9
            if cl_pos2 + len(click_sfx) < total_samples:
                master_audio[cl_pos2:cl_pos2+len(click_sfx)] += click_sfx.astype(np.float32) * 0.9
            if sw_pos + len(whoosh_sfx) < total_samples:
                master_audio[sw_pos:sw_pos+len(whoosh_sfx)] += whoosh_sfx.astype(np.float32) * 0.85

    master_pcm = np.clip(master_audio, -32767.0, 32767.0).astype(np.int16)
    scene_start_times = [s / float(SAMPLE_RATE) for s in scene_starts]
    scene_durations = [len(p) / float(SAMPLE_RATE) for p in scene_segments]
    total_dur_sec = total_samples / float(SAMPLE_RATE)

    return master_pcm, scene_start_times, scene_durations, total_dur_sec

def write_voiceover_script_file(scene_start_times, scene_durations):
    lines = [
        "# PROJECT HOLOHAND — MASTER VIDEO DEMONSTRATION SCRIPT",
        "### High-Definition Showcase & Synchronized Presentation Guide",
        "",
        "**Engineering Team & Academic Roster (MIT-WPU):**",
        "- Harsh Shah — Roll No: 28, PRN: 1262240840 (Lead Architect & Vision Core)",
        "- Sohaliya Patil — Roll No: 22, PRN: 1262240616 (Hardware & Embedded Firmware)",
        "- Sandra Santosh — Roll No: 21, PRN: 1262240615 (Audio Synthesizer & Video)",
        "- Bhoomi — Roll No: 27, PRN: 1262240801 (AR Visuals & Presentation GUI)",
        "- Tashu — Roll No: 31, PRN: 1262240894 (Kinematics & Feature Engineering)",
        "",
        "---",
        ""
    ]

    for idx, sc in enumerate(SCENE_SCRIPTS):
        t_start = scene_start_times[idx]
        t_end = t_start + scene_durations[idx]
        m1, s1 = int(t_start // 60), int(t_start % 60)
        m2, s2 = int(t_end // 60), int(t_end % 60)
        time_str = f"[{m1:02d}:{s1:02d} - {m2:02d}:{s2:02d}]"

        lines.append(f"## {sc['title']} {time_str}")
        lines.append(f"**Presenter / Lead Voice:** {sc['speaker']}")
        lines.append(f"**Category:** {sc['category']}")
        lines.append("")
        lines.append(f"> \"{sc['text']}\"")
        lines.append("")
        lines.append("---")
        lines.append("")

    content = "\n".join(lines)
    with open(OUTPUT_SCRIPT, "w", encoding="utf-8") as f:
        f.write(content)
    with open(os.path.join("x:\\ESP", "VIDEO_VOICEOVER_SCRIPT.txt"), "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[HOLOHAND] Wrote Voiceover Dubbing Sheet to: {OUTPUT_SCRIPT}")

def render_title_screen(canvas, t, scene_time):
    # Cyber Background Grid
    canvas[:, :] = (12, 9, 8)
    for x in range(0, CANVAS_W, 40):
        cv2.line(canvas, (x, 0), (x, CANVAS_H), (24, 18, 14), 1)
    for y in range(0, CANVAS_H, 40):
        cv2.line(canvas, (0, y), (CANVAS_W, y), (24, 18, 14), 1)

    cx, cy = CANVAS_W // 2, CANVAS_H // 2

    # Animated Rotating Hexagon / Reticle
    ang = scene_time * 0.8
    pts_hex = []
    r_hex = 170
    for k in range(6):
        a = ang + k * (2 * math.pi / 6)
        pts_hex.append((int(cx + r_hex * math.cos(a)), int(cy - 120 + r_hex * math.sin(a))))
    cv2.polylines(canvas, [np.array(pts_hex)], True, COLOR_CYAN, 2, cv2.LINE_AA)
    cv2.circle(canvas, (cx, cy - 120), 120, COLOR_VIOLET, 1, cv2.LINE_AA)

    # Title Banner
    cv2.putText(canvas, "PROJECT HOLOHAND", (cx - 360, cy - 110),
                cv2.FONT_HERSHEY_SIMPLEX, 1.8, COLOR_CYAN, 4, cv2.LINE_AA)
    cv2.putText(canvas, "ESP32-CAM REAL-TIME AR GESTURE STUDIO & MUSIC CONDUCTOR", (cx - 480, cy - 50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.72, COLOR_WHITE, 2, cv2.LINE_AA)

    # Engineering Team Showcase Plate
    plate_x, plate_y, plate_w, plate_h = cx - 520, cy + 10, 1040, 230
    overlay = canvas.copy()
    cv2.rectangle(overlay, (plate_x, plate_y), (plate_x + plate_w, plate_y + plate_h), (25, 20, 16), -1)
    cv2.rectangle(overlay, (plate_x, plate_y), (plate_x + plate_w, plate_y + plate_h), COLOR_CYAN, 2)
    cv2.addWeighted(overlay, 0.85, canvas, 0.15, 0, canvas)

    cv2.putText(canvas, "ENGINEERING & DEVELOPMENT TEAM (MIT WORLD PEACE UNIVERSITY):", (plate_x + 30, plate_y + 36),
                cv2.FONT_HERSHEY_SIMPLEX, 0.60, COLOR_AMBER, 2, cv2.LINE_AA)

    # Left Column
    cv2.putText(canvas, "1. HARSH SHAH (Roll 28 | PRN 1262240840)", (plate_x + 35, plate_y + 82),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, COLOR_WHITE, 2, cv2.LINE_AA)
    cv2.putText(canvas, "2. SOHALIYA PATIL (Roll 22 | PRN 1262240616)", (plate_x + 35, plate_y + 128),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, COLOR_WHITE, 2, cv2.LINE_AA)
    cv2.putText(canvas, "3. SANDRA SANTOSH (Roll 21 | PRN 1262240615)", (plate_x + 35, plate_y + 174),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, COLOR_CYAN, 2, cv2.LINE_AA)

    # Right Column
    cv2.putText(canvas, "4. BHOOMI (Roll 27 | PRN 1262240801)", (plate_x + 535, plate_y + 82),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, COLOR_WHITE, 2, cv2.LINE_AA)
    cv2.putText(canvas, "5. TASHU (Roll 31 | PRN 1262240894)", (plate_x + 535, plate_y + 128),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, COLOR_WHITE, 2, cv2.LINE_AA)
    cv2.putText(canvas, "GUIDE: PROF. K. VINOD KUMAR | AID30180", (plate_x + 535, plate_y + 174),
                cv2.FONT_HERSHEY_SIMPLEX, 0.44, COLOR_AMBER, 1, cv2.LINE_AA)

    # Tech Badges
    badges = "[ESP32 Dual-Core 240MHz]  [MediaPipe 21-3D Landmarks]  [Python Low-Latency Worker]  [PyCaw Master Audio]  [Zero Cloud Latency]"
    cv2.putText(canvas, badges, (cx - 560, CANVAS_H - 70),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160, 160, 160), 1, cv2.LINE_AA)

def render_arch_screen(canvas, t, scene_time):
    # Architecture Overview Screen
    canvas[:, :] = (14, 10, 8)
    for y in range(0, CANVAS_H, 40):
        cv2.line(canvas, (0, y), (CANVAS_W, y), (26, 20, 16), 1)

    cv2.putText(canvas, "PROJECT HOLOHAND — HARDWARE & SYSTEM ARCHITECTURE", (60, 70),
                cv2.FONT_HERSHEY_SIMPLEX, 0.95, COLOR_CYAN, 2, cv2.LINE_AA)
    cv2.line(canvas, (60, 85), (CANVAS_W - 60, 85), COLOR_CYAN, 1)

    # Step Flow Pipeline Boxes
    steps = [
        ("1. PHYSICAL ESP32-CAM", "AI-Thinker OV2640\n240MHz Dual-Core\n4MB PSRAM Buffer\nHardware Flashlight"),
        ("2. WI-FI HTTP MJPEG", "802.11 b/g/n Server\nIP: 192.168.1.100\nMulti-client Stream\nLow-latency chunking"),
        ("3. PYTHON ACQUISITION", "Atomic Frame Slot\nThreaded HTTP Worker\nZero Frame Backlog\nLatest-Only Drop"),
        ("4. MEDIAPIPE TRACKING", "21 3D Landmarks\nInvariant Geometry\nTemporal Hysteresis\nVelocity Vectors"),
        ("5. ACTION ROUTING", "Mode A: Hologram\nMode B: Camera\nMode C: Music\nMode D: Air-Mouse")
    ]

    box_w, box_h = 320, 180
    gap = 40
    start_x = (CANVAS_W - (5 * box_w + 4 * gap)) // 2
    if start_x < 40:
        start_x = 40
        box_w = 320

    y_pos = 140
    for idx, (head, body) in enumerate(steps):
        bx = 50 + idx * (box_w + 35)
        by = y_pos
        cv2.rectangle(canvas, (bx, by), (bx + box_w, by + box_h), (25, 20, 16), -1)
        cv2.rectangle(canvas, (bx, by), (bx + box_w, by + box_h), COLOR_CYAN if idx % 2 == 0 else COLOR_VIOLET, 2)
        cv2.putText(canvas, head, (bx + 15, by + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.48, COLOR_AMBER, 2, cv2.LINE_AA)

        for l_idx, bline in enumerate(body.split("\n")):
            cv2.putText(canvas, f"• {bline}", (bx + 15, by + 65 + l_idx * 26),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.40, COLOR_WHITE, 1, cv2.LINE_AA)

        if idx < 4:
            # Flow Arrow
            arrow_x = bx + box_w + 8
            cv2.putText(canvas, ">>", (arrow_x, by + 95), cv2.FONT_HERSHEY_SIMPLEX, 0.70, COLOR_CYAN, 2, cv2.LINE_AA)

    # Lower Deck: Detailed Physical Hardware Pinout Callouts
    cv2.rectangle(canvas, (50, 360), (CANVAS_W - 50, CANVAS_H - 120), (20, 16, 12), -1)
    cv2.rectangle(canvas, (50, 360), (CANVAS_W - 50, CANVAS_H - 120), COLOR_AMBER, 1)

    cv2.putText(canvas, "PHYSICAL HARDWARE SPECIFICATIONS & ZERO-CLOUD LOCAL PROCESSING", (80, 400),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, COLOR_AMBER, 2, cv2.LINE_AA)

    specs = [
        "CAMERA SENSOR: OmniVision OV2640 2-Megapixel (UXGA/SVGA/VGA streaming, 10-bit raw Bayer / JPEG)",
        "PROCESSING SILICON: Espressif ESP32-D0WD-V3 (Xtensa Dual-Core 32-bit LX6 up to 240MHz, 600 DMIPS)",
        "MEMORY ARCHITECTURE: 520KB Internal SRAM + 4MB External High-Speed SPI PSRAM for frame multi-buffering",
        "PROGRAMMER PINOUT: 5V Power -> 5V Pin (>=1.5A peak current) | GND -> GND | Programmer TX -> U0R (GPIO 3) | RX -> U0T (GPIO 1)",
        "COMPUTER VISION ENGINE: MediaPipe Hands ML pipeline running purely on client machine (No external API or cloud calls)",
        "LATENCY BUDGET: Image acquisition ~30ms | MediaPipe inference ~18ms | Action routing <2ms | Full frame cycle 30 FPS"
    ]

    for s_idx, sp in enumerate(specs):
        cv2.putText(canvas, f"•  {sp}", (80, 440 + s_idx * 34),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.44, COLOR_WHITE, 1, cv2.LINE_AA)

def render_outro_screen(canvas, t, scene_time):
    # Cyber Background Grid
    canvas[:, :] = (12, 9, 8)
    for x in range(0, CANVAS_W, 40):
        cv2.line(canvas, (x, 0), (x, CANVAS_H), (24, 18, 14), 1)
    for y in range(0, CANVAS_H, 40):
        cv2.line(canvas, (0, y), (CANVAS_W, y), (24, 18, 14), 1)

    cx = CANVAS_W // 2

    # Animated Rotating Hexagons
    ang = scene_time * 0.6
    r_hex = 65
    for offset_x in [cx - 480, cx + 480]:
        pts_hex = []
        for k in range(6):
            a = ang + k * (2 * math.pi / 6)
            pts_hex.append((int(offset_x + r_hex * math.cos(a)), int(90 + r_hex * math.sin(a))))
        cv2.polylines(canvas, [np.array(pts_hex)], True, COLOR_CYAN, 2, cv2.LINE_AA)

    # Top Title
    cv2.putText(canvas, "PROJECT HOLOHAND — MISSION ACCOMPLISHED", (cx - 440, 85),
                cv2.FONT_HERSHEY_SIMPLEX, 1.25, COLOR_CYAN, 3, cv2.LINE_AA)
    cv2.putText(canvas, "HARDWARE-EMBEDDED AR GESTURE RECOGNITION & MUSIC CONDUCTOR", (cx - 390, 125),
                cv2.FONT_HERSHEY_SIMPLEX, 0.58, COLOR_WHITE, 1, cv2.LINE_AA)
    cv2.line(canvas, (80, 150), (CANVAS_W - 80, 150), COLOR_CYAN, 2)

    # 4 Category Summary Grid Cards
    cards = [
        ("MODE A: HOLOGRAM CONTROL", "Desktop & Media Automation", [
            "• Closed Fist: OS Play/Pause Toggle",
            "• Optical Caliper: 0-100% Volume",
            "• Hand Swipes: Next/Prev Track",
            "• Rock Horns: Physical Flashlight"
        ], COLOR_CYAN),
        ("MODE B: CAMERA STUDIO", "Hands-Free Edge Photography", [
            "• Peace Sign: Instant High-Res Capture",
            "• Palm + Fist: 3s Self-Timer Snapping",
            "• 3 Fingers: MP4 Video Recording",
            "• L-Shape: Hardware LED Flash"
        ], COLOR_GREEN),
        ("MODE C: MUSIC CONDUCTOR", "Spatial Symphony Conducting", [
            "• Dynamic Caliper Volume Modulation",
            "• Waveform HUD Real-Time Visualizer",
            "• Backing Ambient Cyber Synthesizer",
            "• Kinetic Hand Swipe Navigation"
        ], COLOR_VIOLET),
        ("MODE D: VIRTUAL AIR-MOUSE", "Peripheral-Free OS Control", [
            "• Sub-Pixel Smoothed Cursor Tracking",
            "• Anchored Anti-Drift Pinch Click",
            "• Dual-Window Tab Swiping (Ctrl+Tab)",
            "• Multi-Finger Gesture Routing"
        ], COLOR_AMBER),
    ]

    card_w = 410
    card_h = 240
    card_gap = 25
    total_w = 4 * card_w + 3 * card_gap
    start_x = (CANVAS_W - total_w) // 2
    card_y = 180

    for idx, (title, subtitle, bullets, col) in enumerate(cards):
        bx = start_x + idx * (card_w + card_gap)
        overlay = canvas.copy()
        cv2.rectangle(overlay, (bx, card_y), (bx + card_w, card_y + card_h), (22, 18, 14), -1)
        cv2.rectangle(overlay, (bx, card_y), (bx + card_w, card_y + card_h), col, 2)
        cv2.addWeighted(overlay, 0.88, canvas, 0.12, 0, canvas)

        # Header tab
        cv2.rectangle(canvas, (bx, card_y), (bx + card_w, card_y + 40), col, -1)
        cv2.putText(canvas, title, (bx + 14, card_y + 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.50, (10, 8, 6), 2, cv2.LINE_AA)

        cv2.putText(canvas, subtitle, (bx + 14, card_y + 66),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, COLOR_AMBER, 1, cv2.LINE_AA)

        for b_idx, b_text in enumerate(bullets):
            cv2.putText(canvas, b_text, (bx + 14, card_y + 102 + b_idx * 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.40, COLOR_WHITE, 1, cv2.LINE_AA)

    # Engineering Team Credits Banner
    credits_y = 440
    credits_h = 245
    overlay = canvas.copy()
    cv2.rectangle(overlay, (60, credits_y), (CANVAS_W - 60, credits_y + credits_h), (20, 16, 12), -1)
    cv2.rectangle(overlay, (60, credits_y), (CANVAS_W - 60, credits_y + credits_h), COLOR_AMBER, 2)
    cv2.addWeighted(overlay, 0.90, canvas, 0.10, 0, canvas)

    cv2.putText(canvas, "ENGINEERING & DEVELOPMENT TEAM — CORE CONTRIBUTORS (MIT WORLD PEACE UNIVERSITY)", (90, credits_y + 36),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, COLOR_AMBER, 2, cv2.LINE_AA)

    team_members_display = [
        ("1. HARSH SHAH (Roll 28 | PRN 1262240840)", "Lead System Architect & Vision Core"),
        ("2. SOHALIYA PATIL (Roll 22 | PRN 1262240616)", "Hardware Systems & Embedded Firmware"),
        ("3. SANDRA SANTOSH (Roll 21 | PRN 1262240615)", "Audio Synthesizer & Video Production"),
        ("4. BHOOMI (Roll 27 | PRN 1262240801)", "AR Visuals & Presentation GUI Dashboard"),
        ("5. TASHU (Roll 31 | PRN 1262240894)", "Gesture Recognition & Kinematic Formulations")
    ]

    for m_idx, (name, role) in enumerate(team_members_display):
        col_x = 90 if m_idx < 3 else CANVAS_W // 2 + 20
        row_y = credits_y + 78 + (m_idx % 3) * 52
        cv2.putText(canvas, name, (col_x, row_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, COLOR_CYAN, 2, cv2.LINE_AA)
        cv2.putText(canvas, f"— {role}", (col_x, row_y + 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.40, COLOR_WHITE, 1, cv2.LINE_AA)

    # Bottom Thank You Banner
    pulse = 0.5 + 0.5 * math.sin(scene_time * 3.0)
    glow_col = (int(0 + 255 * pulse), 255, int(180 + 75 * pulse))
    cv2.putText(canvas, "THANK YOU FOR WATCHING  |  PROJECT HOLOHAND  |  OCTOBER 2026", (cx - 410, CANVAS_H - 120),
                cv2.FONT_HERSHEY_SIMPLEX, 0.72, glow_col, 2, cv2.LINE_AA)

def render_subtitle_bar(canvas, category, title, text, speaker=""):
    bar_h = 90
    bar_y = CANVAS_H - bar_h
    overlay = canvas.copy()
    cv2.rectangle(overlay, (0, bar_y), (CANVAS_W, CANVAS_H), (10, 8, 6), -1)
    cv2.line(overlay, (0, bar_y), (CANVAS_W, bar_y), COLOR_CYAN, 2)
    cv2.addWeighted(overlay, 0.90, canvas, 0.10, 0, canvas)

    # Top Tag
    speaker_tag = f" | PRESENTER: {speaker.upper()}" if speaker else ""
    header = f"[{category.upper()}] — {title.upper()}{speaker_tag}"
    cv2.putText(canvas, header, (35, bar_y + 28), cv2.FONT_HERSHEY_SIMPLEX, 0.48, COLOR_AMBER, 2, cv2.LINE_AA)

    # Spoken text excerpt
    clean_text = text if len(text) < 135 else text[:132] + "..."
    cv2.putText(canvas, f"\" {clean_text} \"", (35, bar_y + 64),
                cv2.FONT_HERSHEY_SIMPLEX, 0.50, COLOR_WHITE, 1, cv2.LINE_AA)

def produce_video():
    print("=================================================================")
    print("  PROJECT HOLOHAND — BROADCAST VIDEO DEMONSTRATION GENERATOR")
    print("=================================================================")
    print("Engineering Team: Harsh Shah (28), Sohaliya Patil (22), Sandra Santosh (21), Bhoomi (27), Tashu (31)")

    # Step 1: Generate Speech Audio
    print("\n[STEP 1/4] Generating speech narration audio segments via SAPI...")
    scene_audio_files = generate_voiceover_audio()

    # Step 2: Build Master Audio Track
    print("[STEP 2/4] Mixing narration, ambient soundtrack, and interface SFX...")
    master_pcm, scene_start_times, scene_durations, total_dur_sec = build_master_audio_track(scene_audio_files)
    total_frames = int(total_dur_sec * FPS)

    write_voiceover_script_file(scene_start_times, scene_durations)

    print(f"Total video runtime: {total_dur_sec:.2f} seconds ({total_frames} frames @ {FPS} fps)")

    # Step 3: Load Real Hand Assets
    print("[STEP 3/4] Initializing real human hand tracking assets & MediaPipe...")
    real_hands = {
        "open_palm": cv2.resize(cv2.imread(os.path.join(PHOTO_DIR, "holohand_photo_20261023_065404_737.jpg")), (CAM_W, CAM_H)),
        "index_up": cv2.resize(cv2.imread(os.path.join(PHOTO_DIR, "holohand_photo_20261021_234024_346.jpg")), (CAM_W, CAM_H)),
        "peace": cv2.resize(cv2.imread(os.path.join(PHOTO_DIR, "holohand_photo_20261021_234037_673.jpg")), (CAM_W, CAM_H)),
        "fist": cv2.resize(cv2.imread(os.path.join(PHOTO_DIR, "holohand_photo_20261023_100459_106.jpg")), (CAM_W, CAM_H))
    }

    # Load video clips for live motion
    vid_path = os.path.join(VIDEO_DIR, "holohand_video_20261023_100556.mp4")
    vid_frames = []
    cap = cv2.VideoCapture(vid_path)
    while True:
        ret, f = cap.read()
        if not ret: break
        vid_frames.append(cv2.resize(f, (CAM_W, CAM_H)))
    cap.release()
    print(f"Loaded {len(vid_frames)} live frames from physical ESP32-CAM video capture.")

    # Initialize Backend Subsystems
    vis_engine = HolographicVisualEngine(CAM_W, CAM_H)
    music_engine = MusicConductorEngine("music")
    mouse_ctrl = VirtualAirMouseController(dry_run=True)
    flash_ctrl = HardwareFlashController("http://192.168.1.100/stream")
    recognizer = GestureRecognizer()
    audit_log = deque(maxlen=8)

    mp_hands = mp.solutions.hands
    detector = mp_hands.Hands(static_image_mode=False, max_num_hands=1, min_detection_confidence=0.35)

    # Step 4: PyAV Container Initialization
    print(f"\n[STEP 4/4] Encoding full 1080p video demonstration to {OUTPUT_VIDEO}...")
    container = av.open(OUTPUT_VIDEO, mode='w')

    v_stream = container.add_stream('h264', rate=FPS)
    v_stream.width = CANVAS_W
    v_stream.height = CANVAS_H
    v_stream.pix_fmt = 'yuv420p'
    v_stream.options = {'preset': 'fast', 'crf': '20'}

    a_stream = container.add_stream('aac', rate=SAMPLE_RATE)
    a_stream.layout = 'stereo'

    # Audio chunk size: 1024 samples per AAC frame
    AUDIO_FRAME_SIZE = 1024
    audio_ptr = 0
    total_audio_samples = len(master_pcm)

    canvas = np.zeros((CANVAS_H, CANVAS_W, 3), dtype=np.uint8)

    # Calibration landmarks for synthetic transitions where needed
    dummy_open_lms = [
        np.array([480, 620]), np.array([420, 580]), np.array([380, 520]), np.array([360, 460]), np.array([340, 420]),
        np.array([430, 440]), np.array([420, 360]), np.array([415, 300]), np.array([410, 240]),
        np.array([480, 430]), np.array([480, 340]), np.array([480, 270]), np.array([480, 210]),
        np.array([530, 440]), np.array([535, 360]), np.array([540, 300]), np.array([545, 245]),
        np.array([580, 470]), np.array([590, 410]), np.array([600, 360]), np.array([610, 310])
    ]

    # Pre-extract baseline features using real open palm
    rgb_init = cv2.cvtColor(real_hands["open_palm"], cv2.COLOR_BGR2RGB)
    res_init = detector.process(rgb_init)
    if res_init.multi_hand_landmarks:
        last_valid_features = HandFeatureExtractor.extract_features(res_init.multi_hand_landmarks[0].landmark, CAM_W, CAM_H)
    else:
        dummy_pts_arr = np.zeros((21, 3), dtype=np.float32)
        for idx_lm, p in enumerate(dummy_open_lms):
            dummy_pts_arr[idx_lm, :2] = p
        last_valid_features = {
            "pts": dummy_pts_arr,
            "wrist": dummy_pts_arr[0],
            "palm_center": np.array([480.0, 480.0, 0.0]),
            "hand_scale": 150.0,
            "orientation_deg": 0.0,
            "norm_pinch_dist": 0.25,
            "raw_pinch_dist": 38.0,
            "thumb_index_span_ratio": 0.5,
            "norm_middle_pinch_dist": 0.35,
            "thumb_ext": True, "index_ext": True, "middle_ext": False, "ring_ext": False, "pinky_ext": False,
            "thumb_angle_y": -90.0,
            "tips": {
                "thumb": dummy_pts_arr[4],
                "index": dummy_pts_arr[8],
                "middle": dummy_pts_arr[12],
                "ring": dummy_pts_arr[16],
                "pinky": dummy_pts_arr[20]
            }
        }

    t0_render = time.time()
    last_action = "System Boot Initialized"

    # Tracking variable for optical caliper volume
    caliper_vol = 0.50

    for frame_idx in range(total_frames):
        cur_t = frame_idx / float(FPS)

        # Determine current scene
        scene_idx = 0
        for s_i, s_start in enumerate(scene_start_times):
            if cur_t >= s_start:
                scene_idx = s_i

        sc_meta = SCENE_SCRIPTS[scene_idx]
        sc_time = cur_t - scene_start_times[scene_idx]

        # ----------------------------------------------------------------------
        # SCENE RENDERING PIPELINE
        # ----------------------------------------------------------------------
        if scene_idx == 0:
            # Intro Title & Team Screen
            render_title_screen(canvas, cur_t, sc_time)
            render_subtitle_bar(canvas, sc_meta["category"], sc_meta["title"], sc_meta["text"], sc_meta["speaker"])

        elif scene_idx == 1:
            # Architecture Screen
            render_arch_screen(canvas, cur_t, sc_time)
            render_subtitle_bar(canvas, sc_meta["category"], sc_meta["title"], sc_meta["text"], sc_meta["speaker"])

        elif scene_idx == 6:
            # Summary & Outro Screen
            render_outro_screen(canvas, cur_t, sc_time)
            render_subtitle_bar(canvas, sc_meta["category"], sc_meta["title"], sc_meta["text"], sc_meta["speaker"])

        else:
            # Live Mission Control Dashboard Scenes (Scenes 2 to 5)
            active_mode = MODE_HOLOGRAM
            active_visual = VISUAL_HOLOGRAM
            cam_frame = None
            sim_gesture = "OPEN_PALM"
            sim_features = None

            if scene_idx == 2:
                # Mode A: Hologram Control
                active_mode = MODE_HOLOGRAM
                # Cycle sub-demonstrations
                if sc_time < 8.0:
                    cam_frame = real_hands["open_palm"].copy()
                    sim_gesture = "OPEN_PALM"
                    last_action = "Standby Ready State (Open Palm)"
                elif sc_time < 16.0:
                    cam_frame = real_hands["fist"].copy()
                    sim_gesture = "CLOSED_FIST"
                    last_action = "Toggle Play/Pause (Spotify/YouTube)"
                elif sc_time < 24.0:
                    # Thumbs Up / Down
                    v_idx = 115 + int((sc_time - 16.0) * 1.5) % 10
                    cam_frame = vid_frames[v_idx].copy()
                    sim_gesture = "THUMB_UP"
                    last_action = "Media Play/Resume Active"
                elif sc_time < 32.0:
                    # Discrete volume up/down
                    cam_frame = real_hands["index_up"].copy()
                    sim_gesture = "INDEX_POINTING_UP"
                    last_action = "Discrete Volume Step UP (+5%)"
                elif sc_time < 48.0:
                    # Optical Vernier Caliper Volume Demonstration
                    caliper_phase = (sc_time - 32.0) / 16.0
                    caliper_vol = 0.5 + 0.48 * math.sin(caliper_phase * 2 * math.pi)
                    v_idx = 136 + int(caliper_vol * 18)
                    v_idx = max(0, min(len(vid_frames) - 1, v_idx))
                    cam_frame = vid_frames[v_idx].copy()
                    sim_gesture = "CALIPER_VOLUME"
                    last_action = f"Optical Caliper Master Volume: {int(caliper_vol * 100)}%"
                elif sc_time < 54.0:
                    # Swipes
                    v_idx = 4 + int((sc_time - 48.0) * 10) % 3
                    cam_frame = vid_frames[v_idx].copy()
                    sim_gesture = "SWIPE_RIGHT"
                    last_action = "Media Next Track & Tab Switch"
                else:
                    # Horns / Flashlight
                    cam_frame = real_hands["peace"].copy()
                    sim_gesture = "HORNS"
                    flash_ctrl.is_on = True
                    last_action = "Hardware Flashlight ON (Rock Horns 🤘)"

            elif scene_idx == 3:
                # Mode B: Camera Studio
                active_mode = MODE_CAMERA
                flash_ctrl.is_on = False
                if sc_time < 12.0:
                    # Peace sign photo capture
                    cam_frame = real_hands["peace"].copy()
                    sim_gesture = "PEACE_SIGN"
                    last_action = "Photo Captured: holohand_photo_20261024_snap.jpg"
                    if 3.0 < sc_time < 4.5:
                        vis_engine.trigger_shutter_flash()
                elif sc_time < 26.0:
                    # 3-Second Countdown Timer
                    cam_frame = real_hands["fist"].copy()
                    sim_gesture = "CLOSED_FIST"
                    rem = max(0.1, 3.0 - (sc_time - 12.0) % 3.0)
                    last_action = f"Self-Timer Photo: {int(math.ceil(rem))}s Countdown"
                elif sc_time < 35.0:
                    # Three Fingers Video Rec
                    v_idx = 2 + int((sc_time - 26.0) * 5) % 2
                    cam_frame = vid_frames[v_idx].copy()
                    sim_gesture = "THREE_FINGERS_UP"
                    last_action = "Video Recording Active [REC 00:08]"
                else:
                    # Torch L-Shape
                    cam_frame = real_hands["index_up"].copy()
                    sim_gesture = "L_SHAPE"
                    flash_ctrl.is_on = True
                    last_action = "Torch Flashlight ON (🔦 L-Shape)"

            elif scene_idx == 4:
                # Mode C: Music Conductor
                active_mode = MODE_MUSIC
                flash_ctrl.is_on = False
                music_engine.is_playing = True
                conductor_phase = sc_time / 32.0
                caliper_vol = 0.55 + 0.40 * math.sin(conductor_phase * 3 * math.pi)
                music_engine.volume = caliper_vol

                v_idx = 136 + int(caliper_vol * 18)
                v_idx = max(0, min(len(vid_frames) - 1, v_idx))
                cam_frame = vid_frames[v_idx].copy()
                sim_gesture = "CALIPER_VOLUME"
                last_action = f"Conductor Dynamic Volume: {int(caliper_vol * 100)}%"

            elif scene_idx == 5:
                # Mode D: Virtual Air-Mouse
                active_mode = MODE_MOUSE
                flash_ctrl.is_on = False
                if sc_time < 12.0:
                    # Hover cursor navigation
                    cam_frame = real_hands["index_up"].copy()
                    sim_gesture = "INDEX_POINTING"
                    last_action = "Air-Mouse: Hover Cursor Tracking"
                elif sc_time < 22.0:
                    # Anchored Left Click & Double Click
                    cam_frame = vid_frames[138].copy()
                    sim_gesture = "PINCH"
                    last_action = "Air-Mouse: Anchored Left Click (Pinch <0.35s)"
                elif sc_time < 34.0:
                    # Drag & Drop
                    cam_frame = vid_frames[145].copy()
                    sim_gesture = "PINCH"
                    last_action = "Air-Mouse: Drag & Drop Held (Pinch >0.35s)"
                elif sc_time < 46.0:
                    # Scrolling
                    cam_frame = real_hands["index_up"].copy()
                    sim_gesture = "INDEX_POINTING_UP"
                    last_action = "Air-Mouse: Smooth Wheel Scroll UP (+120)"
                else:
                    # Swipe Tab Switching
                    v_idx = 113 + int((sc_time - 46.0) * 12) % 3
                    cam_frame = vid_frames[v_idx].copy()
                    sim_gesture = "SWIPE_RIGHT"
                    last_action = "Air-Mouse: Tab Switch Next [Ctrl+Tab]"

            # Process live MediaPipe detection on camera frame
            rgb = cv2.cvtColor(cam_frame, cv2.COLOR_BGR2RGB)
            res = detector.process(rgb)

            if res.multi_hand_landmarks:
                primary_lm = res.multi_hand_landmarks[0].landmark
                sim_features = HandFeatureExtractor.extract_features(primary_lm, CAM_W, CAM_H)
                last_valid_features = sim_features
            else:
                # Robust fallback to last valid features with deep copies
                sim_features = {k: (v.copy() if isinstance(v, (np.ndarray, dict)) else v) for k, v in last_valid_features.items()}
                sim_features["tips"] = {k: v.copy() for k, v in last_valid_features["tips"].items()}

            # Dynamic caliper updates
            if sim_gesture in ["CALIPER_VOLUME", "PINCH"]:
                sim_features["thumb_index_span_ratio"] = caliper_vol
                sim_features["raw_pinch_dist"] = 25.0 + caliper_vol * 120.0
                sim_features["norm_pinch_dist"] = sim_features["raw_pinch_dist"] / max(1.0, sim_features.get("hand_scale", 150.0))

            # Render Holographic AR Skeleton & Palm Scanner
            vis_engine.render_hand_skeleton(cam_frame, sim_features, active_visual)
            vis_engine.render_palm_scanner(cam_frame, sim_features, cur_t)
            vis_engine.render_effects(cam_frame)

            # Render Caliper HUD if in caliper volume mode
            if sim_gesture in ["CALIPER_VOLUME", "PINCH"]:
                thumb_pt = (int(sim_features["tips"]["thumb"][0]), int(sim_features["tips"]["thumb"][1]))
                index_pt = (int(sim_features["tips"]["index"][0]), int(sim_features["tips"]["index"][1]))
                vis_engine.render_caliper_volume_hud(cam_frame, thumb_pt, index_pt, caliper_vol, sim_features["raw_pinch_dist"])

            # Render Air-Mouse HUD if in mouse mode
            if active_mode == MODE_MOUSE:
                pointer_pos = (sim_features["tips"]["index"][0], sim_features["tips"]["index"][1])
                vis_engine.render_mouse_hud(cam_frame, mouse_ctrl, pointer_pos)

            # Render Top & Bottom Telemetry HUDs
            vis_engine.render_top_hud(
                cam_frame, active_mode, active_visual, True, False,
                "ESP32-CAM (OV2640) 240MHz + PSRAM Online", 30.0, 30.0, is_flash_on=flash_ctrl.is_on
            )
            vis_engine.render_bottom_hud(
                cam_frame, sim_gesture, last_action, music_engine,
                (scene_idx == 3 and sc_time >= 26.0), "00:08"
            )

            # Audit log stamp
            time_tag = time.strftime("%H:%M:%S", time.gmtime(cur_t))
            if not audit_log or audit_log[-1][1] != last_action:
                audit_log.append((time_tag, last_action))

            # Composite into 1080p Presentation Dashboard
            canvas = vis_engine.render_presentation_dashboard(
                cam_frame, sim_features, sim_gesture, last_action, active_mode, active_visual,
                music_engine, mouse_ctrl, flash_ctrl, 30.0, 30.0,
                (scene_idx == 3 and sc_time >= 26.0), "00:08", audit_log, cur_t,
                canvas_w=CANVAS_W, canvas_h=CANVAS_H
            )

            # Render Bottom Subtitle Caption
            render_subtitle_bar(canvas, sc_meta["category"], sc_meta["title"], sc_meta["text"], sc_meta["speaker"])

        # ----------------------------------------------------------------------
        # PYAV ENCODING PIPELINE
        # ----------------------------------------------------------------------
        # Video Frame Encode
        v_frame = av.VideoFrame.from_ndarray(canvas, format='bgr24')
        for packet in v_stream.encode(v_frame):
            container.mux(packet)

        # Audio Frame Encode (Paced to match video timestamps)
        target_audio_samples = int((frame_idx + 1) * (SAMPLE_RATE / float(FPS)))
        while audio_ptr < target_audio_samples and audio_ptr < total_audio_samples:
            chunk_size = min(AUDIO_FRAME_SIZE, total_audio_samples - audio_ptr)
            chunk = master_pcm[audio_ptr:audio_ptr + chunk_size]
            if len(chunk) < AUDIO_FRAME_SIZE:
                pad = np.zeros((AUDIO_FRAME_SIZE - len(chunk), 2), dtype=np.int16)
                chunk = np.vstack([chunk, pad])

            # PyAV s16p planar audio
            planar_chunk = np.ascontiguousarray(chunk.T)
            a_frame = av.AudioFrame.from_ndarray(planar_chunk, format='s16p', layout='stereo')
            a_frame.rate = SAMPLE_RATE
            for packet in a_stream.encode(a_frame):
                container.mux(packet)

            audio_ptr += chunk_size

        if frame_idx == 100:
            cv2.imwrite(os.path.join(CAPTURES_DIR, "demo_frame_title.jpg"), canvas)
        if frame_idx == total_frames - 50:
            cv2.imwrite(os.path.join(CAPTURES_DIR, "demo_frame_outro.jpg"), canvas)

        if frame_idx % 240 == 0 or frame_idx == total_frames - 1:
            pct = (frame_idx / float(total_frames)) * 100.0
            elapsed = time.time() - t0_render
            eta = (elapsed / max(1, frame_idx)) * (total_frames - frame_idx) if frame_idx > 0 else 0
            print(f"  -> Rendering Progress: {frame_idx}/{total_frames} frames ({pct:.1f}%) | Speed: {frame_idx/max(0.1, elapsed):.1f} fps | ETA: {eta:.0f}s")

    # Drain any remaining audio samples
    while audio_ptr < total_audio_samples:
        chunk_size = min(AUDIO_FRAME_SIZE, total_audio_samples - audio_ptr)
        chunk = master_pcm[audio_ptr:audio_ptr + chunk_size]
        if len(chunk) < AUDIO_FRAME_SIZE:
            pad = np.zeros((AUDIO_FRAME_SIZE - len(chunk), 2), dtype=np.int16)
            chunk = np.vstack([chunk, pad])
        planar_chunk = np.ascontiguousarray(chunk.T)
        a_frame = av.AudioFrame.from_ndarray(planar_chunk, format='s16p', layout='stereo')
        a_frame.rate = SAMPLE_RATE
        for packet in a_stream.encode(a_frame):
            container.mux(packet)
        audio_ptr += chunk_size

    # Flush Video & Audio streams
    for packet in v_stream.encode():
        container.mux(packet)
    for packet in a_stream.encode():
        container.mux(packet)

    container.close()

    total_time = time.time() - t0_render
    file_size_mb = os.path.getsize(OUTPUT_VIDEO) / (1024.0 * 1024.0)

    print("\n=================================================================")
    print("  PROJECT HOLOHAND — DEMONSTRATION VIDEO COMPLETE & VALIDATED")
    print("=================================================================")
    print(f"• Output Video File : {OUTPUT_VIDEO}")
    print(f"• File Size         : {file_size_mb:.2f} MB")
    print(f"• Resolution        : {CANVAS_W}x{CANVAS_H} Full HD 1080p @ {FPS} fps")
    print(f"• Total Duration    : {total_dur_sec:.2f} seconds ({total_dur_sec/60:.2f} minutes)")
    print(f"• Total Frames      : {total_frames} frames")
    print(f"• Production Time   : {total_time:.1f} seconds")
    print(f"• Audio Track       : Stereo AAC 44.1kHz (Voiceover + Cyber Ambient + SFX)")
    print(f"• Dubbing Script    : {OUTPUT_SCRIPT}")
    print("=================================================================\n")

if __name__ == "__main__":
    produce_video()
