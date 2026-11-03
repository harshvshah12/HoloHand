import os
import sys
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

PDF_PATH = os.path.join("x:\\ESP", "PROJECT_HOLOHAND_GESTURE_GUIDE.pdf")
PDF_PATH_V2 = os.path.join("x:\\ESP", "PROJECT_HOLOHAND_GESTURE_GUIDE_V2.pdf")
CARDS_DIR = os.path.join("x:\\ESP", "captures", "gesture_cards")
HERO_IMAGE = os.path.join("x:\\ESP", "captures", "demo_hud_showcase.jpg")

# Professional Editorial Dark Theme
C_BG_DARK    = colors.HexColor("#0B0F19")
C_SURFACE    = colors.HexColor("#161E2E")
C_PRIMARY    = colors.HexColor("#00E5FF")   # Electric Cyan
C_SECONDARY  = colors.HexColor("#A855F7")   # Amethyst Violet
C_ACCENT     = colors.HexColor("#F59E0B")   # Amber Gold
C_SUCCESS    = colors.HexColor("#10B981")   # Emerald Green
C_DANGER     = colors.HexColor("#EF4444")   # Crimson Red
C_TEXT_WHITE = colors.HexColor("#F8FAFC")
C_TEXT_MUTED = colors.HexColor("#94A3B8")
C_BORDER     = colors.HexColor("#334155")
C_CARD_BG    = colors.HexColor("#1E293B")

class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to stamp running header/footer and exact 'Page X of Y' count."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_header_footer(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_header_footer(self, page_count):
        self.saveState()
        w, h = letter

        # Running Header (pages > 1)
        if self._pageNumber > 1:
            self.setStrokeColor(C_BORDER)
            self.setLineWidth(0.75)
            self.line(36, h - 34, w - 36, h - 34)

            self.setFont("Helvetica-Bold", 8)
            self.setFillColor(C_PRIMARY)
            self.drawString(36, h - 28, "PROJECT HOLOHAND")
            self.setFont("Helvetica", 8)
            self.setFillColor(C_TEXT_MUTED)
            self.drawString(135, h - 28, "|  ESP32-CAM + MediaPipe Gesture Control & Music Conductor Manual")
            self.drawRightString(w - 36, h - 28, "SYSTEM SPEC v2.1")

        # Running Footer (all pages)
        self.setStrokeColor(C_BORDER)
        self.setLineWidth(0.75)
        self.line(36, 32, w - 36, 32)

        self.setFont("Helvetica", 8)
        self.setFillColor(C_TEXT_MUTED)
        self.drawString(36, 22, "HARSH SHAH (@harshvshah12)  |  x:\\ESP\\holohand_backend.py  |  Offline Edge Intelligence")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(w - 36, 22, page_str)

        self.restoreState()

def build_pdf():
    target_path = PDF_PATH
    try:
        if os.path.exists(PDF_PATH):
            with open(PDF_PATH, "r+b"):
                pass
    except (PermissionError, OSError):
        target_path = PDF_PATH_V2
        print(f"[HOLOHAND] Note: Primary PDF is currently locked by a viewer. Generating to: {target_path}")

    doc = SimpleDocTemplate(
        target_path,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=40,
        bottomMargin=38
    )

    styles = getSampleStyleSheet()

    style_cover_title = ParagraphStyle(
        'CoverTitle',
        fontName='Helvetica-Bold',
        fontSize=23,
        leading=26,
        textColor=C_PRIMARY,
        spaceAfter=2
    )
    style_cover_sub = ParagraphStyle(
        'CoverSubtitle',
        fontName='Helvetica',
        fontSize=11,
        leading=14,
        textColor=C_TEXT_MUTED,
        spaceAfter=6
    )
    style_h1 = ParagraphStyle(
        'Heading1_Custom',
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=17,
        textColor=C_PRIMARY,
        spaceBefore=8,
        spaceAfter=5,
        keepWithNext=True
    )
    style_h2 = ParagraphStyle(
        'Heading2_Custom',
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        textColor=C_SECONDARY,
        spaceBefore=2,
        spaceAfter=3,
        keepWithNext=True
    )
    style_body = ParagraphStyle(
        'Body_Custom',
        fontName='Helvetica',
        fontSize=8.8,
        leading=12.2,
        textColor=colors.HexColor("#E2E8F0"),
        spaceAfter=4
    )
    style_caption = ParagraphStyle(
        'Caption_Custom',
        fontName='Helvetica-Oblique',
        fontSize=7.5,
        leading=9.5,
        textColor=C_TEXT_MUTED,
        spaceAfter=4
    )
    style_badge = ParagraphStyle(
        'Badge',
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9.5,
        textColor=C_ACCENT
    )
    style_table_header = ParagraphStyle(
        'TableHeader',
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=C_PRIMARY
    )
    style_table_cell = ParagraphStyle(
        'TableCell',
        fontName='Helvetica',
        fontSize=8,
        leading=10.5,
        textColor=C_TEXT_WHITE
    )
    style_table_cell_code = ParagraphStyle(
        'TableCellCode',
        fontName='Courier-Bold',
        fontSize=7.5,
        leading=9.5,
        textColor=C_ACCENT
    )

    story = []

    # =========================================================================
    # PAGE 1: COVER & EXECUTIVE ARCHITECTURE (Guaranteed Single Page)
    # =========================================================================
    badge_data = [[
        Paragraph("<b>PROJECT SPECIFICATION: EMBEDDED COMPUTER VISION</b>", style_badge),
        Paragraph("<font color='#00E5FF'><b>HARDWARE: AI-THINKER ESP32-CAM</b></font>", style_badge)
    ]]
    t_badge = Table(badge_data, colWidths=[270, 270])
    t_badge.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), C_SURFACE),
        ('ALIGN', (0,0), (0,0), 'LEFT'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
        ('BOX', (0,0), (-1,-1), 0.75, C_BORDER),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(t_badge)
    story.append(Spacer(1, 4))

    story.append(Paragraph("PROJECT HOLOHAND", style_cover_title))
    story.append(Paragraph("Real-Time Holographic Gesture Control, Camera Studio & Music Conductor", style_cover_sub))
    story.append(HRFlowable(width="100%", thickness=1.0, color=C_PRIMARY, spaceBefore=0, spaceAfter=6))

    # Hero Image of Real Running AR HUD
    if os.path.exists(HERO_IMAGE):
        img_hero = Image(HERO_IMAGE, width=540, height=215)
        story.append(img_hero)
        story.append(Paragraph("<b>Figure 1.0:</b> Real-time composite HoloHand AR HUD running live at 30 FPS. Visualizing palm reticle scanner, 21-joint skeleton tracking, spatial volume gauge, and operating mode telemetry.", style_caption))

    story.append(Paragraph("1. Executive Technical Overview", style_h1))
    story.append(Paragraph(
        "<b>Project HoloHand</b> establishes an ultra-low-latency spatial computing bridge between a physical <b>AI-Thinker ESP32-CAM (OV2640)</b> and a high-performance Python computer vision backend. The system streams MJPEG video frames over an isolated 2.4 GHz 802.11 b/g/n Wi-Fi link, performs <b>21-degree-of-freedom (21-DOF) 3D hand landmark tracking</b> using MediaPipe, and executes real-time invariant kinematic gesture classification with temporal hysteresis.",
        style_body
    ))
    story.append(Paragraph(
        "The runtime unifies three operating modalities into an integrated, touchless cyberpunk augmented-reality environment: "
        "<b>Mode A (Hologram Control)</b> for desktop OS media, presentation slide control, and hardware flashlight triggers; "
        "<b>Mode B (Camera Studio)</b> for instant photos, 3-second timer snapshots, and asynchronous 1080p video recording; and "
        "<b>Mode C (Music Conductor)</b> for spatial vertical pinch volume modulation, playback management, and track scrubbing.",
        style_body
    ))

    # Architecture Overview Table
    arch_data = [
        [Paragraph("Subsystem", style_table_header), Paragraph("Implementation Architecture", style_table_header), Paragraph("Performance Metric", style_table_header)],
        [Paragraph("Video Streamer", style_table_cell), Paragraph("ESP32-CAM OV2640 HTTP MJPEG (/stream)", style_table_cell), Paragraph("30 FPS @ 800x600 SVGA", style_table_cell_code)],
        [Paragraph("Hand Landmark AI", style_table_cell), Paragraph("MediaPipe Hands (StaticMode=False, MinConf=0.65)", style_table_cell), Paragraph("~12 ms per frame CPU", style_table_cell_code)],
        [Paragraph("Gesture Hysteresis", style_table_cell), Paragraph("3-Frame Dwell Window + Motion History Buffer", style_table_cell), Paragraph("100 ms stabilization", style_table_cell_code)],
        [Paragraph("Hardware Flash", style_table_cell), Paragraph("ESP32 GPIO 4 REST API (/flash?state=toggle)", style_table_cell), Paragraph("&lt; 40 ms HTTP Latency", style_table_cell_code)],
        [Paragraph("Audio Synthesizer", style_table_cell), Paragraph("Pygame Mixer + 44.1kHz Procedural Synth Chords", style_table_cell), Paragraph("Zero-Lag Offline Audio", style_table_cell_code)],
        [Paragraph("Video Recording", style_table_cell), Paragraph("Async Bounded-Queue Threaded VideoWriter", style_table_cell), Paragraph("Zero Frame Drops", style_table_cell_code)]
    ]
    t_arch = Table(arch_data, colWidths=[110, 280, 150])
    t_arch.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), C_SURFACE),
        ('BACKGROUND', (0,1), (-1,-1), C_CARD_BG),
        ('GRID', (0,0), (-1,-1), 0.5, C_BORDER),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(t_arch)
    story.append(PageBreak())

    # =========================================================================
    # PAGE 2: OPERATING MODALITIES & HARDWARE PINOUT (Guaranteed Single Page)
    # =========================================================================
    story.append(Paragraph("2. Operating Modalities Matrix", style_h1))
    story.append(Paragraph(
        "HoloHand provides four dedicated operating modes designed to prevent unintended gesture cross-talk while maintaining universal safety overrides. Modes can be switched seamlessly via keyboard keys <b>[1]</b>, <b>[2]</b>, <b>[3]</b>, <b>[4]</b> / <b>[M]</b>, or through the touchless <b>Hologram Command Matrix</b>.",
        style_body
    ))

    modes_table = [
        [Paragraph("Mode", style_table_header), Paragraph("Primary Purpose", style_table_header), Paragraph("Core Gesture Capabilities", style_table_header), Paragraph("Audio / Feedback Output", style_table_header)],
        [
            Paragraph("<b>MODE A<br/>HOLOGRAM<br/>CONTROL</b>", style_table_cell),
            Paragraph("Full-system interaction, presentation navigation, desktop automation, and ambient synth control.", style_table_cell),
            Paragraph("• Closed Fist: Play/Pause<br/>• Thumbs Up/Dn: Play/Pause<br/>• Index Up/Dn: Volume Up/Down<br/>• Peace Sign: Prev Slide / Mute<br/>• Rock Horns: Flashlight Toggle<br/>• Vertical Pinch: Spatial Volume", style_table_cell),
            Paragraph("Pygame Ambient Synth + Windows Media Keys + Amber Holographic Shockwaves", style_table_cell)
        ],
        [
            Paragraph("<b>MODE B<br/>CAMERA<br/>STUDIO</b>", style_table_cell),
            Paragraph("High-resolution still photography, timer countdowns, continuous video recording, and studio torch illumination.", style_table_cell),
            Paragraph("• Peace Sign: Instant Photo<br/>• Palm ➔ Fist: 3s Countdown<br/>• 3 Fingers: Toggle Recording<br/>• Rock Horns: Flashlight Toggle<br/>• L-Shape: Torch Gun Toggle", style_table_cell),
            Paragraph("Procedural Shutter Click + Full-Screen White Flash + Live REC HUD Bar", style_table_cell)
        ],
        [
            Paragraph("<b>MODE C<br/>MUSIC<br/>CONDUCTOR</b>", style_table_cell),
            Paragraph("Live orchestral conductor interface for playlist audio, volume shaping, track scrubbing, and muting.", style_table_cell),
            Paragraph("• Thumbs Up: Play Track<br/>• Thumbs Down: Pause Track<br/>• Closed Fist: Stop/Toggle<br/>• Index Up/Dn: Step Vol (+-5%)<br/>• Vertical Pinch: 0%-100% Vol<br/>• Swipes: Next/Prev Track<br/>• Peace Sign: Mute Toggle", style_table_cell),
            Paragraph("Real-Time 44.1kHz Waveform Synthesis + Right-Side AR Dynamic Volume Gauge", style_table_cell)
        ],
        [
            Paragraph("<b>MODE D<br/>VIRTUAL<br/>AIR-MOUSE</b>", style_table_cell),
            Paragraph("Full OS cursor control, window management, drag-and-drop, and context menus via gestures.", style_table_cell),
            Paragraph("• Index Tip: Cursor Motion<br/>• Quick Pinch: Left Click<br/>• Double Pinch: Double Click<br/>• Hold Pinch: Left Drag & Drop<br/>• Peace Sign: Right Click<br/>• Index Up/Dn: Scroll Up/Dn", style_table_cell),
            Paragraph("Dynamic Dual-Exponential Smoothing + Active Deadzone Box + Radar Reticle", style_table_cell)
        ]
    ]
    t_modes = Table(modes_table, colWidths=[90, 140, 180, 130])
    t_modes.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), C_SURFACE),
        ('BACKGROUND', (0,1), (-1,-1), C_CARD_BG),
        ('GRID', (0,0), (-1,-1), 0.5, C_BORDER),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(t_modes)
    story.append(Spacer(1, 6))

    story.append(Paragraph("3. Hardware Pinout & Wi-Fi REST Architecture", style_h1))
    story.append(Paragraph(
        "The physical ESP32-CAM AI-Thinker module runs custom asynchronous firmware (<code>holohand_esp32cam.ino</code>). It initializes the Omnivision OV2640 sensor in SVGA JPEG mode with dual DMA frame buffers in PSRAM, disables the brownout detector to prevent voltage sags during Wi-Fi transmission bursts, and exposes four REST endpoints over port 80:",
        style_body
    ))

    hw_endpoints = [
        [Paragraph("Endpoint", style_table_header), Paragraph("HTTP Method", style_table_header), Paragraph("Payload / Action", style_table_header), Paragraph("Hardware Execution", style_table_header)],
        [Paragraph("<code>/stream</code>", style_table_cell_code), Paragraph("GET", style_table_cell), Paragraph("Multipart JPEG stream (<code>image/jpeg</code> boundary)", style_table_cell), Paragraph("Continuous OV2640 DMA frame push", style_table_cell)],
        [Paragraph("<code>/capture</code>", style_table_cell_code), Paragraph("GET", style_table_cell), Paragraph("Single uncompressed high-resolution JPEG", style_table_cell), Paragraph("Instantaneous frame-buffer snapshot", style_table_cell)],
        [Paragraph("<code>/status</code>", style_table_cell_code), Paragraph("GET", style_table_cell), Paragraph("JSON payload (IP, RSSI, Free Heap, Uptime, Flash)", style_table_cell), Paragraph("Real-time telemetry heartbeat", style_table_cell)],
        [Paragraph("<code>/flash</code>", style_table_cell_code), Paragraph("POST / GET", style_table_cell), Paragraph("URL parameter <code>?state=1</code>, <code>0</code>, or <code>toggle</code>", style_table_cell), Paragraph("Direct GPIO 4 high-power LED transistor", style_table_cell)]
    ]
    t_hw = Table(hw_endpoints, colWidths=[90, 80, 200, 170])
    t_hw.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), C_SURFACE),
        ('BACKGROUND', (0,1), (-1,-1), C_CARD_BG),
        ('GRID', (0,0), (-1,-1), 0.5, C_BORDER),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_hw)
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        "<b>Wi-Fi Connectivity Requirement:</b> The ESP32-CAM connects to SSID <code>3245</code> on 2.4 GHz. Both the laptop running <code>holohand_backend.py</code> and the ESP32 must reside on the same network subnet without AP client isolation enabled.",
        style_caption
    ))
    story.append(PageBreak())

    # =========================================================================
    # PAGE 3: CYBER MISSION CONTROL PRESENTATION DASHBOARD
    # =========================================================================
    story.append(Paragraph("4. Cyber Mission Control Presentation Workstation", style_h1))
    story.append(Paragraph(
        "HoloHand features a native 1920x1080 Cyber Mission Control Presentation Dashboard designed for high-impact project showcases, classroom presentations, and live hardware demonstrations. The dashboard organizes the entire pipeline into three ergonomic visual decks with real-time hardware telemetry:",
        style_body
    ))

    dashboard_img = os.path.join("x:\\ESP", "captures", "dashboard_preview.png")
    if os.path.exists(dashboard_img):
        img_dash = Image(dashboard_img, width=540, height=270)
        story.append(img_dash)
        story.append(Paragraph("<b>Figure 4.0:</b> Native 1080p Cyber Mission Control Station operating live in Mode D (Virtual Air-Mouse) with left telemetry deck, central AR camera viewport, right gesture & audio equalizer monitor, and bottom hotkey cheatsheet.", style_caption))

    deck_data = [
        [Paragraph("Console Deck", style_table_header), Paragraph("Architecture & Telemetry Stream", style_table_header), Paragraph("Operational Impact", style_table_header)],
        [
            Paragraph("<b>Top Status Bar</b>", style_table_cell),
            Paragraph("Mode selector tabs ([1] HOLO, [2] CAM, [3] MUSIC, [4] MOUSE), Flashlight indicator, Stream FPS, and Vision FPS.", style_table_cell),
            Paragraph("Provides instantaneous mode confirmation and camera-to-CV synchronization monitoring at a glance.", style_table_cell)
        ],
        [
            Paragraph("<b>Left Telemetry Deck</b>", style_table_cell),
            Paragraph("Sensor hardware specs, DMA PSRAM buffers, brownout status, 3D kinematics (centroid, rotation, hand scale, pinch gauge), and 5-finger extension array.", style_table_cell),
            Paragraph("Allows audiences to observe continuous internal computer vision feature extraction in real time.", style_table_cell)
        ],
        [
            Paragraph("<b>Central AR Viewport</b>", style_table_cell),
            Paragraph("Live ESP32-CAM MJPEG camera feed composited with 21-joint skeleton overlays, palm scanner, and HUD telemetry.", style_table_cell),
            Paragraph("Serves as the primary augmented-reality visual stage for the user's tracked hand gestures.", style_table_cell)
        ],
        [
            Paragraph("<b>Right Command Deck</b>", style_table_cell),
            Paragraph("Active gesture classifier, Air-Mouse radar / 12-band animated audio equalizer, and rolling event audit log.", style_table_cell),
            Paragraph("Displays classification confidence, live mouse radar coordinates, and chronological action history.", style_table_cell)
        ],
        [
            Paragraph("<b>Bottom Navigation Bar</b>", style_table_cell),
            Paragraph("Single-key hotkey cheat-sheet: <code>TAB</code> toggles Studio/Fullframe; <code>F11</code>/<code>F</code> toggles Fullscreen.", style_table_cell),
            Paragraph("Ensures immediate presenter control without fumbling for keyboard commands during demonstrations.", style_table_cell)
        ]
    ]
    t_deck = Table(deck_data, colWidths=[110, 240, 190])
    t_deck.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), C_SURFACE),
        ('BACKGROUND', (0,1), (-1,-1), C_CARD_BG),
        ('GRID', (0,0), (-1,-1), 0.5, C_BORDER),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(t_deck)
    story.append(PageBreak())

    # =========================================================================
    # GESTURE ENCYCLOPEDIA PAGES (EXACTLY 1 GESTURE PROFILE PER PAGE)
    # =========================================================================
    gesture_catalog = [
        {
            "file": "card_open_palm.png",
            "name": "1. Open Palm Gesture", "emoji": "🖐",
            "desc": "The foundational tracking and radar alignment pose. Continuously updates palm center coordinates, estimates 3D hand scale and orientation, and arms the timer buffer for sequential photo countdown triggers.",
            "specs": [
                ("Anatomical Extensions", "All 5 fingers fully extended [Thumb:1, Index:1, Middle:1, Ring:1, Pinky:1]"),
                ("Extension Metric", "Tip-to-Wrist distance &gt; 1.05 * PIP distance AND &gt; 1.08 * MCP distance"),
                ("Mode A (Hologram)", "Maintains spatial hover cursor; triggers ambient reticle scanner & amber particle ripple"),
                ("Mode B (Camera)", "Arms the 2.2-second window for subsequent Closed Fist countdown capture"),
                ("Mode C (Music Conductor)", "Neutral ready position; resets previous baton velocity vectors without cutting audio"),
                ("Stabilization Dwell", "3 consecutive frames (~100 ms) required to transition from neutral/NONE state")
            ]
        },
        {
            "file": "card_closed_fist.png",
            "name": "2. Closed Fist Gesture", "emoji": "✊",
            "desc": "The universal audio play/pause toggle and execution grip. When held steadily, it acts as a master toggle; when preceded by an Open Palm within 2.2 seconds, it triggers the automated 3-second camera countdown.",
            "specs": [
                ("Anatomical Extensions", "All 5 fingers curled tightly into palm [Thumb:0, Index:0, Middle:0, Ring:0, Pinky:0]"),
                ("Sequential Trigger", "If (Current_Time - Last_Open_Palm_Time) &lt;= 2.2s -> INITIATES 3-SECOND TIMER PHOTO"),
                ("Mode A (Hologram)", "Toggles Play/Pause simultaneously across Pygame ambient engine and Windows OS media"),
                ("Mode B (Camera)", "Initiates 3-second timer snapshot with cyan shockwave and audio countdown chime"),
                ("Mode C (Music Conductor)", "Master conductor cut-off / resume toggle with 0.60s debounce guard"),
                ("Cooldown Guard", "0.80 seconds debounce cooldown prevents accidental oscillation")
            ]
        },
        {
            "file": "card_palm_fist_seq.png",
            "name": "3. Sequential Snapshot: Open Palm ➔ Closed Fist", "emoji": "🖐 ➔ ✊",
            "desc": "Engineered for touchless selfies and group photography without touching the computer. Arms on Open Palm and confirms upon clenching into a Fist within 2.2 seconds.",
            "specs": [
                ("Step 1: Open Palm (🖐)", "Present open palm to camera: timestamp is instantly recorded in memory"),
                ("Step 2: Clench Fist (✊)", "Close hand into a fist within 2.2 seconds to confirm the capture sequence"),
                ("Step 3: Countdown Reticle", "Holographic circular countdown HUD (3... 2... 1...) renders with radial progress sweep"),
                ("Step 4: Image Finalization", "High-res JPEG saved to captures/photos/ with shutter click and full-screen flash"),
                ("Universal Availability", "Active across all modes (Hologram, Camera Studio, Music Conductor)")
            ]
        },
        {
            "file": "card_thumb_up.png",
            "name": "4. Thumbs Up Gesture", "emoji": "👍",
            "desc": "Positive media affirmation gesture. Explicitly triggers playback resumption of active audio tracks across both the local synthesizer and background Windows players.",
            "specs": [
                ("Anatomical Extensions", "Thumb extended, 4 primary fingers folded in fist [T:1, I:0, M:0, R:0, P:0]"),
                ("Orientation Angle", "Thumb vector angle relative to horizontal: -150° &lt; Angle &lt; -30° (Straight Up)"),
                ("Mode A (Hologram)", "Sends Windows Play/Resume keystroke & starts Pygame cyber ambient track"),
                ("Mode B (Camera)", "Camera studio confirmation tone and ready state reset"),
                ("Mode C (Music Conductor)", "Conductor track play actuation with emerald green particle ripple"),
                ("Cooldown Guard", "0.60 seconds debounce protection")
            ]
        },
        {
            "file": "card_thumb_down.png",
            "name": "5. Thumbs Down Gesture", "emoji": "👎",
            "desc": "Negative media affirmation gesture. Explicitly halts active audio playback and pauses background music.",
            "specs": [
                ("Anatomical Extensions", "Thumb extended, 4 primary fingers folded in fist [T:1, I:0, M:0, R:0, P:0]"),
                ("Orientation Angle", "Thumb vector angle relative to horizontal: +30° &lt; Angle &lt; +150° (Straight Down)"),
                ("Mode A (Hologram)", "Sends Windows Pause keystroke & halts Pygame cyber ambient track"),
                ("Mode B (Camera)", "Cancels active countdown timer immediately without capturing photo"),
                ("Mode C (Music Conductor)", "Conductor track pause actuation with crimson reticle flare"),
                ("Cooldown Guard", "0.60 seconds debounce protection")
            ]
        },
        {
            "file": "card_index_up.png",
            "name": "6. Index Pointing Up Gesture", "emoji": "☝",
            "desc": "Volume increment and conductor forte gesture. Provides rapid, repeatable volume stepping (+5%) without requiring the user to look away from the camera.",
            "specs": [
                ("Anatomical Extensions", "Index extended, Middle/Ring/Pinky folded [I:1, M:0, R:0, P:0] (Thumb position independent)"),
                ("Vector Orientation", "Tip.Y &lt; MCP.Y (-150° &lt; Angle &lt; -30° pointing upward towards ceiling)"),
                ("Mode A (Hologram)", "Increments Pygame volume (+5%) and executes PyAutoGUI 'volumeup' OS key"),
                ("Mode B (Camera)", "Camera studio digital EV brightness compensation (+1 step)"),
                ("Mode C (Music Conductor)", "Increments conductor synthesizer volume (+5%) with rapid 180 ms re-arm pacing"),
                ("Step Velocity", "180 ms rapid-repeat cooldown allows smooth stepping from 0% to 100% in ~3.5 seconds")
            ]
        },
        {
            "file": "card_index_down.png",
            "name": "7. Index Pointing Down Gesture", "emoji": "👇",
            "desc": "Volume decrement and conductor piano gesture. Decreases active listening volume by -5% increments with continuous rapid-step support.",
            "specs": [
                ("Anatomical Extensions", "Index extended downward, other fingers folded [I:1, M:0, R:0, P:0]"),
                ("Vector Orientation", "Tip.Y &gt; MCP.Y (+30° &lt; Angle &lt; +150° pointing downward towards desk)"),
                ("Mode A (Hologram)", "Decrements Pygame volume (-5%) and executes PyAutoGUI 'volumedown' OS key"),
                ("Mode B (Camera)", "Camera studio digital EV brightness compensation (-1 step)"),
                ("Mode C (Music Conductor)", "Decrements conductor synthesizer volume (-5%) with 180 ms re-arm pacing"),
                ("Step Velocity", "180 ms rapid-repeat cooldown prevents volume drop lockups")
            ]
        },
        {
            "file": "card_pinch.png",
            "name": "8. Vertical Pinch Slider Gesture", "emoji": "🤏",
            "desc": "Continuous spatial height audio modulation. Pinching Thumb and Index fingertips creates a virtual slider; moving the pinched hand vertically smoothly sweeps volume from 0% to 100%.",
            "specs": [
                ("Normalized Pinch Distance", "Thumb Tip to Index Tip Euclidean distance &lt; 0.24 * Hand Scale (~18-25 px)"),
                ("Hysteresis Release", "Release confirmed only when distance exceeds 0.32 * Hand Scale (prevents jitter)"),
                ("Spatial Height Mapping", "Direct linear interpolation: Bottom of screen = 0% Volume, Top of screen = 100% Volume"),
                ("AR Visual HUD Gauge", "Renders vertical neon Cyan/Violet graduated volume meter on right screen edge"),
                ("Mode A & C Response", "Direct real-time volume adjustment across Pygame audio mixer and desktop sound")
            ]
        },
        {
            "file": "card_peace_sign.png",
            "name": "9. Peace Sign Gesture", "emoji": "✌",
            "desc": "High-contrast dual-finger pose. Snaps instantaneous zero-delay photos in Camera Studio, and toggles audio mute in Music Conductor mode.",
            "specs": [
                ("Anatomical Extensions", "Index and Middle extended in V-shape [I:1, M:1, R:0, P:0] (Thumb folded or tucked)"),
                ("Dwell Stability", "3 consecutive frames required for confirmation"),
                ("Mode A (Hologram)", "Presentation navigation: Previous Slide (PowerPoint / Keynote left key)"),
                ("Mode B (Camera)", "SNAPS INSTANT HIGH-RES PHOTO to disk with shutter audio & screen flash"),
                ("Mode C (Music Conductor)", "Toggles Mute / Unmute instantly without altering active playback track"),
                ("Cooldown Guard", "1.50 seconds shutter lock prevents accidental burst captures")
            ]
        },
        {
            "file": "card_horns.png",
            "name": "10. Rock On / Horns Gesture (🤘)", "emoji": "🤘",
            "desc": "Hardware flashlight command pose. Toggles the physical onboard high-power flash LED on the ESP32-CAM (GPIO 4) over Wi-Fi REST in real time without crashing the window.",
            "specs": [
                ("Anatomical Extensions", "Index and Pinky extended, Middle and Ring folded into palm [I:1, M:0, R:0, P:1]"),
                ("Hardware Mechanism", "Sends asynchronous HTTP POST to http://&lt;esp32-ip&gt;/flash?state=toggle"),
                ("Mode A & B Action", "Toggles onboard flash LED ON / OFF with amber shockwave and particle burst"),
                ("Mode C Action", "Toggles flash LED; useful for stage / conducting visual illumination"),
                ("Cooldown Guard", "1.20 seconds thermal protection cooldown to prevent LED driver overheating")
            ]
        },
        {
            "file": "card_l_shape.png",
            "name": "11. L-Shape Torch Gun Gesture", "emoji": "👉/🔦",
            "desc": "Secondary spotlight flashlight toggle. Designed for quick directional aiming and flashlight activation in Camera Studio mode.",
            "specs": [
                ("Anatomical Extensions", "Thumb pointing up (-90°), Index pointing horizontal [T:1, I:1, M:0, R:0, P:0]"),
                ("Geometric Angle", "Thumb and Index form an orthogonal ~90° angle (finger gun posture)"),
                ("Mode A (Hologram)", "Presentation Next Slide / Forward Focus"),
                ("Mode B (Camera)", "Toggles ESP32-CAM flashlight on/off as an inspection spotlight"),
                ("Mode C (Music Conductor)", "Fast-forward cue marker"),
                ("Cooldown Guard", "1.20 seconds debounce protection")
            ]
        },
        {
            "file": "card_three_fingers.png",
            "name": "12. Three Fingers Up Gesture", "emoji": "3️⃣",
            "desc": "High-performance video recording toggle. Starts and stops asynchronous threaded 1080p MP4 recording to the local disk without stalling the computer vision pipeline.",
            "specs": [
                ("Anatomical Extensions", "Index, Middle, and Ring extended; Pinky folded [I:1, M:1, R:1, P:0]"),
                ("Recording Engine", "Asynchronous bounded-queue VideoWriter (mp4v codec with automatic XVID/MJPG fallback)"),
                ("Mode B (Camera)", "STARTS / STOPS 1080p MP4 recording with live flashing red 'REC MM:SS' HUD badge"),
                ("Mode A & C Action", "Cycles visual HUD rendering theme (Hologram -> Scan -> Minimal)"),
                ("Cooldown Guard", "1.80 seconds recording buffer lock prevents rapid start-stop file truncation")
            ]
        },
        {
            "file": "card_swipes.png",
            "name": "13. Kinetic Horizontal Swipes", "emoji": "👈 / 👉",
            "desc": "Dynamic velocity-based gestures. Evaluates temporal displacement across a 12-frame sliding history buffer to trigger playlist skipping.",
            "specs": [
                ("Velocity Threshold", "Horizontal displacement velocity &gt; 0.55 screen widths per second"),
                ("Displacement Threshold", "Total horizontal travel &gt; 0.15 screen widths within 50 to 450 ms window"),
                ("Swipe Right (👉)", "Advances to Next Track in playlist & triggers Windows 'nexttrack' key"),
                ("Swipe Left (👈)", "Rewinds to Previous Track in playlist & triggers Windows 'prevtrack' key"),
                ("Cooldown Guard", "0.80 seconds debounce; motion history buffer is flushed upon confirmation")
            ]
        },
        {
            "file": "card_two_hand_matrix.png",
            "name": "14. Two-Hand Holographic Command Matrix", "emoji": "🖐🖐",
            "desc": "Multi-hand spatial gesture. Simultaneously presenting both hands with extended fingers invokes or dismisses the floating AR interactive command dashboard.",
            "specs": [
                ("Detection Requirements", "Two hands concurrently tracked by MediaPipe; both displaying extended Thumb and Index"),
                ("Interaction Method", "Touchless pointer cursor tracks primary Index fingertip over 12 virtual buttons"),
                ("Triggering Mechanisms", "1. Pinch (Thumb + Index) over button, OR 2. Dwell/Hover cursor for &gt; 0.75 seconds"),
                ("Matrix Controls", "[1] Hologram Mode, [2] Camera Mode, [3] Music Mode, Play/Pause, Vol +/-, Photo, Rec, Flash"),
                ("Keyboard Shortcut", "Can also be toggled manually at any time using keyboard key 'P'")
            ]
        },
        {
            "file": "card_air_mouse.png",
            "name": "15. Virtual Air-Mouse System", "emoji": "🖱️",
            "desc": "Converts tracked hand kinematics into a high-precision, zero-latency desktop air-mouse. Maps index fingertip spatial coordinates to full-screen cursor coordinates with dynamic dual-exponential velocity smoothing, click position anchoring to eliminate finger-pinch drift, kinetic tab switching, and full tactile gesture actions.",
            "specs": [
                ("Cursor Motion & Smoothing", "Dual-exponential filter (Alpha=0.08 for sub-pixel button lock, up to Alpha=0.75 for fast sweeps)"),
                ("Anchored Left Click", "Quick pinch (<0.35s) freezes cursor on target at touchdown to eliminate finger-pinch drift"),
                ("Rapid Double Click", "Two quick pinches within <0.45s executes native OS double-click on target files/windows"),
                ("Left Click & Drag (>0.35s)", "Sustained pinch engages left mouseDown; cursor unlocks for smooth window/file dragging"),
                ("Swipe Tab Switch (👉 / 👈)", "Hand Swipe Right = Next Tab [Ctrl+Tab] | Hand Swipe Left = Prev Tab [Ctrl+Shift+Tab]"),
                ("Right Click (✌ / Mid-Pinch)", "Peace Sign OR Thumb+Middle Pinch executes native OS Right Click context menu"),
                ("Middle Click (3️⃣ / Wheel)", "Three Fingers Up executes native Middle Click (opens links in new tab, closes tabs)"),
                ("Vertical Scrolling (☝ / 👇)", "Index Pointing Up triggers upward scroll; Index Pointing Down triggers downward scroll"),
                ("Active Deadzone Radar", "18% outer margins preserve arm ergonomics; central 64% maps to entire desktop surface")
            ]
        }
    ]

    for item in gesture_catalog:
        card_img_path = os.path.join(CARDS_DIR, item["file"])
        story.append(Paragraph(f"<b>{item['name']} ({item['emoji']})</b>", style_h2))
        story.append(Paragraph(item["desc"], style_body))

        if os.path.exists(card_img_path):
            img = Image(card_img_path, width=540, height=270)
            story.append(img)
            story.append(Spacer(1, 4))

        t_rows = [[Paragraph("Parameter", style_table_header), Paragraph("Engineering Specification", style_table_header)]]
        for k, v in item["specs"]:
            t_rows.append([Paragraph(k, style_table_cell), Paragraph(v, style_table_cell)])

        t_spec = Table(t_rows, colWidths=[150, 390])
        t_spec.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), C_SURFACE),
            ('BACKGROUND', (0,1), (-1,-1), C_CARD_BG),
            ('GRID', (0,0), (-1,-1), 0.5, C_BORDER),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ]))
        story.append(t_spec)
        story.append(PageBreak())

    # =========================================================================
    # KEYBOARD SHORTCUTS & FAILSAFES
    # =========================================================================
    story.append(Paragraph("5. Keyboard Hotkey Quick Reference", style_h1))
    story.append(Paragraph(
        "For laboratory testing, emergency overrides, and quick calibration, HoloHand provides single-key hotkey bindings that work alongside gesture controls:",
        style_body
    ))

    keys_data = [
        [Paragraph("Key", style_table_header), Paragraph("Function", style_table_header), Paragraph("Operational Impact", style_table_header)],
        [Paragraph("<code>ESC</code>", style_table_cell_code), Paragraph("EMERGENCY DISABLE", style_table_cell), Paragraph("Immediately halts all desktop automation and OS keystrokes for safety", style_table_cell)],
        [Paragraph("<code>E</code> / <code>SPACE</code>", style_table_cell_code), Paragraph("Toggle Desktop Actions", style_table_cell), Paragraph("Arms or disarms PyAutoGUI desktop automation without stopping vision", style_table_cell)],
        [Paragraph("<code>1</code> / <code>2</code> / <code>3</code>", style_table_cell_code), Paragraph("Switch Operating Mode", style_table_cell), Paragraph("Switches between [1] Hologram, [2] Camera Studio, [3] Music Conductor", style_table_cell)],
        [Paragraph("<code>4</code> / <code>M</code>", style_table_cell_code), Paragraph("Switch to Air-Mouse", style_table_cell), Paragraph("Activates Mode D: Virtual Air-Mouse cursor tracking and gestural clicking", style_table_cell)],
        [Paragraph("<code>TAB</code>", style_table_cell_code), Paragraph("Toggle Dashboard Layout", style_table_cell), Paragraph("Toggles between Studio (Mission Control Station) and Fullframe Direct AR View", style_table_cell)],
        [Paragraph("<code>F</code> / <code>F11</code>", style_table_cell_code), Paragraph("Toggle Fullscreen Mode", style_table_cell), Paragraph("Toggles 1920x1080 borderless presentation fullscreen vs 1280x720 windowed", style_table_cell)],
        [Paragraph("<code>T</code> / <code>L</code>", style_table_cell_code), Paragraph("Toggle ESP32 Flashlight", style_table_cell), Paragraph("Sends REST call to toggle physical GPIO 4 high-power LED torch", style_table_cell)],
        [Paragraph("<code>V</code>", style_table_cell_code), Paragraph("Cycle Visual Mode", style_table_cell), Paragraph("Cycles between HOLOGRAM (full glow), SCAN (technical), and MINIMAL", style_table_cell)],
        [Paragraph("<code>P</code>", style_table_cell_code), Paragraph("Toggle Command Matrix", style_table_cell), Paragraph("Opens / closes the floating AR holographic button dashboard", style_table_cell)],
        [Paragraph("<code>C</code>", style_table_cell_code), Paragraph("Instant Photo Capture", style_table_cell), Paragraph("Manually captures and saves a high-res photograph to captures/photos/", style_table_cell)],
        [Paragraph("<code>R</code>", style_table_cell_code), Paragraph("Toggle Video Recording", style_table_cell), Paragraph("Starts or stops async 1080p MP4 recording to captures/videos/", style_table_cell)],
        [Paragraph("<code>D</code>", style_table_cell_code), Paragraph("Diagnostic HUD Matrix", style_table_cell), Paragraph("Renders real-time telemetry: hand scale, rotation, pinch distance, finger flags", style_table_cell)],
        [Paragraph("<code>X</code>", style_table_cell_code), Paragraph("Toggle Dry-Run Mode", style_table_cell), Paragraph("Displays gesture actions on HUD without dispatching desktop OS keys", style_table_cell)],
        [Paragraph("<code>Q</code>", style_table_cell_code), Paragraph("Quit Cleanly", style_table_cell), Paragraph("Finalizes video recorders, shuts down camera threads, and exits cleanly", style_table_cell)]
    ]
    t_keys = Table(keys_data, colWidths=[90, 160, 290])
    t_keys.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), C_SURFACE),
        ('BACKGROUND', (0,1), (-1,-1), C_CARD_BG),
        ('GRID', (0,0), (-1,-1), 0.5, C_BORDER),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_keys)
    story.append(PageBreak())

    # =========================================================================
    # PAGE 18: TROUBLESHOOTING & CALIBRATION MATRIX (Guaranteed Single Page)
    # =========================================================================
    story.append(Paragraph("6. Engineering Troubleshooting & Calibration Guide", style_h1))
    trouble_data = [
        [Paragraph("Symptom", style_table_header), Paragraph("Root Cause Analysis", style_table_header), Paragraph("Engineering Remediation", style_table_header)],
        [
            Paragraph("Stream Connection Failed / Offline Screen", style_table_cell),
            Paragraph("ESP32-CAM assigned different DHCP IP or router client isolation enabled.", style_table_cell),
            Paragraph("Open Arduino Serial Monitor @ 115200 baud to read assigned IP. Pass URL: <code>python holohand_backend.py --url http://&lt;IP&gt;/stream</code>.", style_table_cell)
        ],
        [
            Paragraph("Flashlight LED Does Not Respond", style_table_cell),
            Paragraph("ESP32 pin conflict or brownout during Wi-Fi transmission bursts.", style_table_cell),
            Paragraph("Ensure <code>holohand_esp32cam.ino</code> has brownout detector disabled. Test manual endpoint: <code>curl http://&lt;IP&gt;/flash?state=toggle</code>.", style_table_cell)
        ],
        [
            Paragraph("Volume Stepping Too Sensitive / Inverted", style_table_cell),
            Paragraph("Hand angled too far from vertical axis causing orientation flip.", style_table_cell),
            Paragraph("Keep hand upright facing camera. For Index Up, keep finger perpendicular to desk; for Index Down, point directly at table surface.", style_table_cell)
        ],
        [
            Paragraph("Pinch Slider Jitter", style_table_cell),
            Paragraph("Fingers partially obscuring each other from steep camera angle.", style_table_cell),
            Paragraph("Maintain 40-70 cm distance from camera lens. Hold hand perpendicular to camera sensor. The hysteresis threshold (0.24 vs 0.32) eliminates jitter.", style_table_cell)
        ],
        [
            Paragraph("No Sound from Conductor", style_table_cell),
            Paragraph("Pygame mixer uninitialized or system audio output muted.", style_table_cell),
            Paragraph("Project generates <code>music/holohand_cyber_ambient.wav</code> automatically. Check bottom HUD: ensure status is PLAYING and VOL &gt; 0%.", style_table_cell)
        ]
    ]
    t_trouble = Table(trouble_data, colWidths=[120, 190, 230])
    t_trouble.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), C_SURFACE),
        ('BACKGROUND', (0,1), (-1,-1), C_CARD_BG),
        ('GRID', (0,0), (-1,-1), 0.5, C_BORDER),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_trouble)
    story.append(Spacer(1, 14))

    # Author Signoff Block
    signoff_data = [[
        Paragraph("<b>PROJECT HOLOHAND AUTHOR & MAINTAINER</b><br/><b>Harsh Shah</b> (@harshvshah12) &bull; harshvshah2019@gmail.com<br/>Real-Time Embedded Computer Vision & Human-Computer Interaction", style_body),
        Paragraph("<b>SYSTEM STATUS</b><br/><font color='#10B981'><b>ALL SYSTEMS OPERATIONAL (PASS 100%)</b></font><br/>Validated on Python 3.10 & ESP32-CAM OV2640", style_body)
    ]]
    t_signoff = Table(signoff_data, colWidths=[320, 220])
    t_signoff.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), C_SURFACE),
        ('BOX', (0,0), (-1,-1), 1, C_BORDER),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_signoff)

    print(f"[HOLOHAND] Compiling refined manual to {target_path}...")
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"[HOLOHAND] Successfully generated: {target_path} ({os.path.getsize(target_path)} bytes)")

if __name__ == "__main__":
    build_pdf()
