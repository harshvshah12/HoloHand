import os
import math
import numpy as np
import cv2

CARDS_DIR = os.path.join("x:\\ESP", "captures", "gesture_cards")
os.makedirs(CARDS_DIR, exist_ok=True)

# Color Palette (BGR)
COLOR_BG        = (16, 12, 10)
COLOR_DARK_BOX  = (28, 22, 18)
COLOR_CYAN      = (240, 215, 0)
COLOR_VIOLET    = (210, 50, 180)
COLOR_WHITE     = (255, 255, 255)
COLOR_GREEN     = (80, 240, 80)
COLOR_AMBER     = (0, 180, 255)
COLOR_RED       = (60, 60, 240)
COLOR_GRAY      = (120, 110, 100)

BONES = [
    (0, 1), (1, 2), (2, 3), (3, 4),        # Thumb
    (0, 5), (5, 6), (6, 7), (7, 8),        # Index
    (0, 9), (9, 10), (10, 11), (11, 12),   # Middle
    (0, 13), (13, 14), (14, 15), (15, 16), # Ring
    (0, 17), (17, 18), (18, 19), (19, 20), # Pinky
    (5, 9), (9, 13), (13, 17)              # Palm Knuckle Arch
]

def generate_hand_joints(gesture_name):
    """
    Returns 21 landmark 2D coordinates (x, y) centered around (200, 230) for a 640x360 card.
    """
    wrist = np.array([200.0, 310.0])
    pts = np.zeros((21, 2))
    pts[0] = wrist

    # Base MCPs
    pts[5] = wrist + np.array([-40.0, -100.0])  # Index MCP
    pts[9] = wrist + np.array([-10.0, -112.0])  # Middle MCP
    pts[13] = wrist + np.array([18.0, -105.0])  # Ring MCP
    pts[17] = wrist + np.array([44.0, -88.0])   # Pinky MCP

    # Thumb CMC
    pts[1] = wrist + np.array([-32.0, -38.0])
    pts[2] = pts[1] + np.array([-25.0, -28.0])  # Thumb MCP

    # Helper to generate straight or folded finger joints
    def build_finger(mcp_idx, base_angle_deg, is_extended, length_scale=1.0, is_pointing_down=False):
        mcp = pts[mcp_idx]
        if is_pointing_down:
            rad = math.radians(90.0)  # Downward
            p1 = mcp + np.array([math.cos(rad), math.sin(rad)]) * (36.0 * length_scale)
            p2 = p1 + np.array([math.cos(rad), math.sin(rad)]) * (30.0 * length_scale)
            p3 = p2 + np.array([math.cos(rad), math.sin(rad)]) * (26.0 * length_scale)
            pts[mcp_idx + 1] = p1
            pts[mcp_idx + 2] = p2
            pts[mcp_idx + 3] = p3
            return

        rad = math.radians(base_angle_deg)
        if is_extended:
            p1 = mcp + np.array([math.cos(rad), math.sin(rad)]) * (38.0 * length_scale)
            p2 = p1 + np.array([math.cos(rad), math.sin(rad)]) * (32.0 * length_scale)
            p3 = p2 + np.array([math.cos(rad), math.sin(rad)]) * (28.0 * length_scale)
        else:
            # Folded into palm
            p1 = mcp + np.array([math.cos(rad), math.sin(rad)]) * 20.0
            p2 = p1 + np.array([math.cos(rad + 0.9), math.sin(rad + 0.9)]) * 18.0
            p3 = p2 + np.array([0.0, 16.0])  # Tucked inward
        pts[mcp_idx + 1] = p1
        pts[mcp_idx + 2] = p2
        pts[mcp_idx + 3] = p3

    # Default extensions
    thumb_mode = "fist"  # fist, up, down, pinch, open
    i_ext, m_ext, r_ext, p_ext = False, False, False, False
    idx_down = False

    if gesture_name == "OPEN_PALM":
        thumb_mode = "open"
        i_ext, m_ext, r_ext, p_ext = True, True, True, True
    elif gesture_name == "CLOSED_FIST":
        thumb_mode = "fist"
        i_ext, m_ext, r_ext, p_ext = False, False, False, False
    elif gesture_name == "THUMB_UP":
        thumb_mode = "up"
        i_ext, m_ext, r_ext, p_ext = False, False, False, False
    elif gesture_name == "THUMB_DOWN":
        thumb_mode = "down"
        i_ext, m_ext, r_ext, p_ext = False, False, False, False
    elif gesture_name == "INDEX_UP":
        thumb_mode = "fist"
        i_ext, m_ext, r_ext, p_ext = True, False, False, False
    elif gesture_name == "INDEX_DOWN":
        thumb_mode = "fist"
        i_ext, m_ext, r_ext, p_ext = True, False, False, False
        idx_down = True
    elif gesture_name == "PINCH":
        thumb_mode = "pinch"
        i_ext, m_ext, r_ext, p_ext = False, False, False, False
    elif gesture_name == "PEACE_SIGN":
        thumb_mode = "fist"
        i_ext, m_ext, r_ext, p_ext = True, True, False, False
    elif gesture_name == "HORNS":
        thumb_mode = "fist"
        i_ext, m_ext, r_ext, p_ext = True, False, False, True
    elif gesture_name == "L_SHAPE":
        thumb_mode = "up"
        i_ext, m_ext, r_ext, p_ext = True, False, False, False
    elif gesture_name == "THREE_FINGERS":
        thumb_mode = "fist"
        i_ext, m_ext, r_ext, p_ext = True, True, True, False
    elif gesture_name == "AIR_MOUSE":
        thumb_mode = "fist"
        i_ext, m_ext, r_ext, p_ext = True, False, False, False

    # Build 4 fingers
    build_finger(5, -100.0, i_ext, length_scale=1.0, is_pointing_down=idx_down)
    build_finger(9, -92.0, m_ext, length_scale=1.05)
    build_finger(13, -84.0, r_ext, length_scale=0.98)
    build_finger(17, -74.0, p_ext, length_scale=0.85)

    # Build Thumb
    mcp_t = pts[2]
    if thumb_mode == "open":
        rad_t = math.radians(-145.0)
        pts[3] = mcp_t + np.array([math.cos(rad_t), math.sin(rad_t)]) * 32.0
        pts[4] = pts[3] + np.array([math.cos(rad_t), math.sin(rad_t)]) * 30.0
    elif thumb_mode == "up":
        rad_t = math.radians(-90.0)
        pts[3] = mcp_t + np.array([math.cos(rad_t), math.sin(rad_t)]) * 36.0
        pts[4] = pts[3] + np.array([math.cos(rad_t), math.sin(rad_t)]) * 34.0
    elif thumb_mode == "down":
        rad_t = math.radians(85.0)
        pts[3] = mcp_t + np.array([math.cos(rad_t), math.sin(rad_t)]) * 36.0
        pts[4] = pts[3] + np.array([math.cos(rad_t), math.sin(rad_t)]) * 34.0
    elif thumb_mode == "pinch":
        # Thumb and index tips meet at specific pinch coordinate
        pinch_contact = pts[5] + np.array([0.0, -60.0])
        pts[3] = (mcp_t + pinch_contact) / 2.0
        pts[4] = pinch_contact
        # Bend index tip to contact
        pts[6] = pts[5] + np.array([-10.0, -28.0])
        pts[7] = pts[6] + np.array([8.0, -22.0])
        pts[8] = pinch_contact + np.array([2.0, -1.0])
    else:  # fist
        pts[3] = mcp_t + np.array([18.0, -10.0])
        pts[4] = pts[3] + np.array([16.0, 5.0])

    return pts

def render_gesture_card(gesture_key, title, subtitle, mode_actions, specs, badge_color=COLOR_CYAN):
    w, h = 680, 360
    card = np.full((h, w, 3), COLOR_BG, dtype=np.uint8)

    # Subtle background tech grid
    for x in range(0, w, 30):
        cv2.line(card, (x, 0), (x, h), (24, 18, 14), 1)
    for y in range(0, h, 30):
        cv2.line(card, (0, y), (w, y), (24, 18, 14), 1)

    # Left Viewport Box (Hand Wireframe HUD)
    cv2.rectangle(card, (20, 20), (320, h - 20), COLOR_DARK_BOX, -1)
    cv2.rectangle(card, (20, 20), (320, h - 20), COLOR_CYAN, 1)

    # Tech Corner brackets on Hand Viewport
    brk_len = 12
    for bx, by in [(20, 20), (320, 20), (20, h - 20), (320, h - 20)]:
        dx = brk_len if bx == 20 else -brk_len
        dy = brk_len if by == 20 else -brk_len
        cv2.line(card, (bx, by), (bx + dx, by), COLOR_WHITE, 2)
        cv2.line(card, (bx, by), (bx, by + dy), COLOR_WHITE, 2)

    # Hand Skeleton Rendering
    pts = generate_hand_joints(gesture_key)

    # Palm Reticle Scanner behind joints
    cx, cy = int(pts[9][0]), int(pts[9][1] + 10)
    cv2.circle(card, (cx, cy), 46, (40, 30, 22), 2)
    cv2.ellipse(card, (cx, cy), (54, 54), 25, 0, 90, COLOR_CYAN, 1, cv2.LINE_AA)
    cv2.ellipse(card, (cx, cy), (54, 54), 25, 180, 270, COLOR_CYAN, 1, cv2.LINE_AA)
    cv2.ellipse(card, (cx, cy), (38, 38), -40, 0, 120, COLOR_VIOLET, 1, cv2.LINE_AA)

    # Bones
    for b1, b2 in BONES:
        p1 = (int(pts[b1][0]), int(pts[b1][1]))
        p2 = (int(pts[b2][0]), int(pts[b2][1]))
        cv2.line(card, p1, p2, COLOR_CYAN, 2, cv2.LINE_AA)

    # Joints
    for i in range(21):
        p = (int(pts[i][0]), int(pts[i][1]))
        cv2.circle(card, p, 3, COLOR_VIOLET, -1, cv2.LINE_AA)
        cv2.circle(card, p, 5, COLOR_WHITE, 1, cv2.LINE_AA)

    # Fingertips (4, 8, 12, 16, 20)
    for tip_idx in [4, 8, 12, 16, 20]:
        p = (int(pts[tip_idx][0]), int(pts[tip_idx][1]))
        cv2.circle(card, p, 6, badge_color, 2, cv2.LINE_AA)
        cv2.circle(card, p, 2, COLOR_WHITE, -1, cv2.LINE_AA)

    # Special Visual Overlay for Pinch
    if gesture_key == "PINCH":
        contact_pt = (int(pts[4][0]), int(pts[4][1]))
        cv2.circle(card, contact_pt, 14, COLOR_AMBER, 2, cv2.LINE_AA)
        cv2.line(card, (contact_pt[0] - 25, contact_pt[1]), (contact_pt[0] + 25, contact_pt[1]), COLOR_AMBER, 1, cv2.LINE_AA)
        cv2.line(card, (contact_pt[0], contact_pt[1] - 40), (contact_pt[0], contact_pt[1] + 40), COLOR_AMBER, 2, cv2.LINE_AA)
        cv2.putText(card, "VERTICAL SLIDER", (contact_pt[0] - 65, contact_pt[1] - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.38, COLOR_AMBER, 1, cv2.LINE_AA)

    # Viewport label
    cv2.putText(card, "21-DOF SKELETON MODEL", (32, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.35, COLOR_CYAN, 1, cv2.LINE_AA)
    cv2.putText(card, f"TARGET: {gesture_key}", (32, h - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.38, COLOR_WHITE, 1, cv2.LINE_AA)

    # RIGHT PANEL: Technical Specifications & Operating Mode Table
    rx = 345

    # Badge & Title
    cv2.rectangle(card, (rx, 22), (rx + 110, 42), badge_color, 1)
    cv2.putText(card, "GESTURE SPEC", (rx + 10, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.35, badge_color, 1, cv2.LINE_AA)

    cv2.putText(card, title, (rx, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.65, COLOR_WHITE, 2, cv2.LINE_AA)
    cv2.putText(card, subtitle, (rx, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.40, COLOR_CYAN, 1, cv2.LINE_AA)
    cv2.line(card, (rx, 102), (w - 20, 102), (60, 50, 42), 1)

    # Mode Mappings Box
    cur_y = 125
    modes = [
        ("MODE A (HOLOGRAM):", mode_actions.get("A", "N/A"), COLOR_CYAN),
        ("MODE B (CAMERA):", mode_actions.get("B", "N/A"), COLOR_AMBER),
        ("MODE C (CONDUCTOR):", mode_actions.get("C", "N/A"), COLOR_VIOLET)
    ]
    for mode_title, action_text, col in modes:
        cv2.putText(card, mode_title, (rx, cur_y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, col, 1, cv2.LINE_AA)
        cv2.putText(card, action_text, (rx + 140, cur_y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, COLOR_WHITE, 1, cv2.LINE_AA)
        cur_y += 24

    cv2.line(card, (rx, cur_y), (w - 20, cur_y), (60, 50, 42), 1)
    cur_y += 18

    # Hardware & Kinematics Telemetry Grid
    for k, v in specs.items():
        cv2.putText(card, f"{k}:", (rx, cur_y), cv2.FONT_HERSHEY_SIMPLEX, 0.35, COLOR_GRAY, 1, cv2.LINE_AA)
        cv2.putText(card, str(v), (rx + 120, cur_y), cv2.FONT_HERSHEY_SIMPLEX, 0.35, COLOR_GREEN, 1, cv2.LINE_AA)
        cur_y += 18

    # Border around entire card
    cv2.rectangle(card, (0, 0), (w - 1, h - 1), (50, 40, 32), 1)

    out_path = os.path.join(CARDS_DIR, f"card_{gesture_key.lower()}.png")
    cv2.imwrite(out_path, card)
    return out_path

# Generate All Cards
card_data = [
    {
        "key": "OPEN_PALM",
        "title": "OPEN PALM (🖐)",
        "subtitle": "Kinematic Radar Tracking & Neutral Standby",
        "actions": {
            "A": "System Hover, Reticle Scan & Standby",
            "B": "Pre-arms Sequential Countdown Timer",
            "C": "Neutral Baton Position / Ready state"
        },
        "specs": {
            "Fingers Extended": "5 of 5 [T:1, I:1, M:1, R:1, P:1]",
            "Dwell Window": "3 Frames (100 ms confirmation)",
            "Cooldown": "None (Continuous Tracking)"
        },
        "color": COLOR_CYAN
    },
    {
        "key": "CLOSED_FIST",
        "title": "CLOSED FIST (✊)",
        "subtitle": "Universal Play / Pause & Execution Grip",
        "actions": {
            "A": "Toggles Desktop Media & Internal Music",
            "B": "If preceded by Palm: Starts 3s Photo Timer",
            "C": "Conductor Master Stop / Resume Toggle"
        },
        "specs": {
            "Fingers Extended": "0 of 5 [T:0, I:0, M:0, R:0, P:0]",
            "Sequential Trigger": "< 2.2s after Open Palm -> 3s Timer",
            "Cooldown": "0.80s debounce guard"
        },
        "color": COLOR_VIOLET
    },
    {
        "key": "THUMB_UP",
        "title": "THUMBS UP (👍)",
        "subtitle": "Audio Resume & Media Affirmation",
        "actions": {
            "A": "Resumes Desktop Media Player & Synthesizer",
            "B": "Camera Ready State Confirmation",
            "C": "Music Conductor: Play Active Track"
        },
        "specs": {
            "Fingers Extended": "Thumb only [T:1, I:0, M:0, R:0, P:0]",
            "Angular Vector": "-150° < Angle < -30° (Straight Up)",
            "Cooldown": "0.60s debounce"
        },
        "color": COLOR_GREEN
    },
    {
        "key": "THUMB_DOWN",
        "title": "THUMBS DOWN (👎)",
        "subtitle": "Audio Silence & Media Pause",
        "actions": {
            "A": "Pauses Desktop Media Player & Synthesizer",
            "B": "Cancel Pending Photo Timer",
            "C": "Music Conductor: Pause Active Track"
        },
        "specs": {
            "Fingers Extended": "Thumb only [T:1, I:0, M:0, R:0, P:0]",
            "Angular Vector": "+30° < Angle < +150° (Straight Down)",
            "Cooldown": "0.60s debounce"
        },
        "color": COLOR_RED
    },
    {
        "key": "INDEX_UP",
        "title": "INDEX POINTING UP (☝)",
        "subtitle": "Volume Increment (+5%) & Conductor Forte",
        "actions": {
            "A": "Volume UP (+5%) & Desktop Vol Key",
            "B": "Camera Exposure / EV Step Up",
            "C": "Conductor Forte: Volume UP (+5%)"
        },
        "specs": {
            "Fingers Extended": "Index only [I:1, M:0, R:0, P:0]",
            "Orientation": "Tip.Y < MCP.Y (-150° to -30°)",
            "Step Rate": "180 ms rapid-repeat pacing"
        },
        "color": COLOR_CYAN
    },
    {
        "key": "INDEX_DOWN",
        "title": "INDEX POINTING DOWN (👇)",
        "subtitle": "Volume Decrement (-5%) & Conductor Piano",
        "actions": {
            "A": "Volume DOWN (-5%) & Desktop Vol Key",
            "B": "Camera Exposure / EV Step Down",
            "C": "Conductor Piano: Volume DOWN (-5%)"
        },
        "specs": {
            "Fingers Extended": "Index only [I:1, M:0, R:0, P:0]",
            "Orientation": "Tip.Y > MCP.Y (+30° to +150°)",
            "Step Rate": "180 ms rapid-repeat pacing"
        },
        "color": COLOR_AMBER
    },
    {
        "key": "PINCH",
        "title": "VERTICAL PINCH SLIDER (🤏)",
        "subtitle": "Continuous Spatial Height Volume Modulation",
        "actions": {
            "A": "Continuous OS & Synthesizer Volume Modulation",
            "B": "Focus / Zoom Level Fine Adjustment",
            "C": "Spatial Baton Height -> Direct 0% to 100% Vol"
        },
        "specs": {
            "Normalized Distance": "Thumb-to-Index Tip < 0.24 Hand Scale",
            "Hysteresis Release": "Release confirmed at > 0.32 Hand Scale",
            "Vertical Range": "Screen Bottom (0%) to Screen Top (100%)"
        },
        "color": COLOR_AMBER
    },
    {
        "key": "PEACE_SIGN",
        "title": "PEACE SIGN (✌)",
        "subtitle": "Instant Photo Capture & Conductor Mute",
        "actions": {
            "A": "Toggles Audio Mute & Navigates Prev Slide",
            "B": "SNAPS INSTANT HIGH-RES PHOTO to disk",
            "C": "Conductor: Toggle Audio Mute State"
        },
        "specs": {
            "Fingers Extended": "Index + Middle [I:1, M:1, R:0, P:0]",
            "Dwell Confirmation": "3 consecutive frames",
            "Cooldown": "1.50s shutter debounce"
        },
        "color": COLOR_GREEN
    },
    {
        "key": "HORNS",
        "title": "ROCK ON / HORNS (🤘)",
        "subtitle": "ESP32-CAM Hardware Flashlight Toggle",
        "actions": {
            "A": "Toggles ESP32 Onboard Flash LED via REST",
            "B": "Toggles ESP32 Studio Lighting Flashlight",
            "C": "Toggles ESP32 Hardware Flashlight"
        },
        "specs": {
            "Fingers Extended": "Index + Pinky [I:1, M:0, R:0, P:1]",
            "Hardware Endpoint": "POST /flash?state=toggle on GPIO 4",
            "Cooldown": "1.20s thermal protection debounce"
        },
        "color": COLOR_AMBER
    },
    {
        "key": "L_SHAPE",
        "title": "L-SHAPE TORCH GUN (👉/🔦)",
        "subtitle": "Secondary Hardware Spotlight Toggle",
        "actions": {
            "A": "Presentation Next Slide / Forward Focus",
            "B": "Toggles ESP32 Flashlight (Torch Mode)",
            "C": "Fast-Forward Active Synthesizer"
        },
        "specs": {
            "Fingers Extended": "Thumb + Index [T:1, I:1, M:0, R:0, P:0]",
            "Angle Alignment": "Index horizontal, Thumb perpendicular",
            "Cooldown": "1.20s debounce"
        },
        "color": COLOR_CYAN
    },
    {
        "key": "THREE_FINGERS",
        "title": "THREE FINGERS UP (3️⃣)",
        "subtitle": "Asynchronous High-FPS Video Recording",
        "actions": {
            "A": "AR Hologram HUD Color Theme Cycle",
            "B": "STARTS / STOPS 1080p MP4 Video Recording",
            "C": "Conductor: Toggle Preset Soundstage"
        },
        "specs": {
            "Fingers Extended": "Index, Middle, Ring [I:1, M:1, R:1, P:0]",
            "Encoding Pipeline": "Non-blocking Threaded VideoWriter Queue",
            "Cooldown": "1.80s recording buffer lock"
        },
        "color": COLOR_RED
    },
    {
        "key": "AIR_MOUSE",
        "title": "VIRTUAL AIR-MOUSE (🖱️)",
        "subtitle": "Direct Spatial Pointer, Anchored Clicks & Tab Swipes",
        "actions": {
            "A": "Desktop: Full System Mouse, Click & Drag & Drop",
            "B": "Browser: Kinetic Swipe Left/Right to Switch Tabs",
            "C": "Tabs/Links: Middle Click (3 Fingers) to Open/Close Tabs"
        },
        "specs": {
            "Pointer Tracking": "Index tip mapped to 1920x1080 with Dual-Exponential Filter",
            "Anchored Left Click": "Quick Pinch (<0.35s) freezes cursor on target to eliminate drift",
            "Swipe Tab Switch": "Hand Swipe Right = Next Tab [Ctrl+Tab] | Left = Prev [Ctrl+Shift+Tab]"
        },
        "color": COLOR_AMBER
    }
]

for item in card_data:
    path = render_gesture_card(item["key"], item["title"], item["subtitle"], item["actions"], item["specs"], item["color"])
    print(f"Generated: {path}")

print("All gesture cards generated successfully!")
