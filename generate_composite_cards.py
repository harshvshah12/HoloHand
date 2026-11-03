import os
import math
import numpy as np
import cv2

CARDS_DIR = os.path.join("x:\\ESP", "captures", "gesture_cards")

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
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (0, 9), (9, 10), (10, 11), (11, 12),
    (0, 13), (13, 14), (14, 15), (15, 16),
    (0, 17), (17, 18), (18, 19), (19, 20),
    (5, 9), (9, 13), (13, 17)
]

def render_composite_palm_fist_card():
    w, h = 680, 360
    card = np.full((h, w, 3), COLOR_BG, dtype=np.uint8)

    # Grid
    for x in range(0, w, 30):
        cv2.line(card, (x, 0), (x, h), (24, 18, 14), 1)
    for y in range(0, h, 30):
        cv2.line(card, (0, y), (w, y), (24, 18, 14), 1)

    # Title Banner
    cv2.rectangle(card, (20, 15), (180, 35), COLOR_AMBER, 1)
    cv2.putText(card, "SEQUENTIAL GESTURE", (30, 29), cv2.FONT_HERSHEY_SIMPLEX, 0.35, COLOR_AMBER, 1, cv2.LINE_AA)
    cv2.putText(card, "OPEN PALM -> CLOSED FIST (🖐 -> ✊)", (20, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.65, COLOR_WHITE, 2, cv2.LINE_AA)
    cv2.putText(card, "Automated 3-Second Studio Photo Timer Snapshot", (20, 82), cv2.FONT_HERSHEY_SIMPLEX, 0.40, COLOR_CYAN, 1, cv2.LINE_AA)
    cv2.line(card, (20, 95), (w - 20, 95), (60, 50, 42), 1)

    # 3-Stage Diagram:
    # Step 1: Open Palm Box (x: 20 to 200)
    cv2.rectangle(card, (25, 115), (195, 335), COLOR_DARK_BOX, -1)
    cv2.rectangle(card, (25, 115), (195, 335), COLOR_CYAN, 1)
    cv2.putText(card, "STEP 1: OPEN PALM", (35, 138), cv2.FONT_HERSHEY_SIMPLEX, 0.38, COLOR_CYAN, 1, cv2.LINE_AA)
    cv2.circle(card, (110, 210), 38, (45, 35, 25), 2)
    cv2.putText(card, "🖐", (90, 222), cv2.FONT_HERSHEY_SIMPLEX, 1.2, COLOR_WHITE, 2, cv2.LINE_AA)
    cv2.putText(card, "Arm Timer Ready", (45, 275), cv2.FONT_HERSHEY_SIMPLEX, 0.35, COLOR_WHITE, 1, cv2.LINE_AA)
    cv2.putText(card, "Timestamp Logged", (42, 295), cv2.FONT_HERSHEY_SIMPLEX, 0.33, COLOR_GRAY, 1, cv2.LINE_AA)

    # Arrow 1 -> 2
    cv2.arrowedLine(card, (205, 225), (235, 225), COLOR_AMBER, 3, tipLength=0.35)
    cv2.putText(card, "< 2.2s", (202, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.32, COLOR_AMBER, 1, cv2.LINE_AA)

    # Step 2: Closed Fist Box (x: 245 to 415)
    cv2.rectangle(card, (245, 115), (415, 335), COLOR_DARK_BOX, -1)
    cv2.rectangle(card, (245, 115), (415, 335), COLOR_VIOLET, 1)
    cv2.putText(card, "STEP 2: CLENCH FIST", (255, 138), cv2.FONT_HERSHEY_SIMPLEX, 0.38, COLOR_VIOLET, 1, cv2.LINE_AA)
    cv2.circle(card, (330, 210), 38, (45, 25, 45), 2)
    cv2.putText(card, "✊", (310, 222), cv2.FONT_HERSHEY_SIMPLEX, 1.2, COLOR_WHITE, 2, cv2.LINE_AA)
    cv2.putText(card, "Clench within 2.2s", (265, 275), cv2.FONT_HERSHEY_SIMPLEX, 0.35, COLOR_WHITE, 1, cv2.LINE_AA)
    cv2.putText(card, "Triggers Countdown", (262, 295), cv2.FONT_HERSHEY_SIMPLEX, 0.33, COLOR_GRAY, 1, cv2.LINE_AA)

    # Arrow 2 -> 3
    cv2.arrowedLine(card, (425, 225), (455, 225), COLOR_CYAN, 3, tipLength=0.35)

    # Step 3: Countdown HUD (x: 465 to 655)
    cv2.rectangle(card, (465, 115), (655, 335), COLOR_DARK_BOX, -1)
    cv2.rectangle(card, (465, 115), (655, 335), COLOR_GREEN, 1)
    cv2.putText(card, "STEP 3: 3s TIMER", (480, 138), cv2.FONT_HERSHEY_SIMPLEX, 0.38, COLOR_GREEN, 1, cv2.LINE_AA)

    # Countdown circular graphic
    ccx, ccy = 560, 210
    cv2.circle(card, (ccx, ccy), 44, COLOR_CYAN, 2, cv2.LINE_AA)
    cv2.ellipse(card, (ccx, ccy), (44, 44), -90, 0, 240, COLOR_AMBER, 4, cv2.LINE_AA)
    cv2.putText(card, "3", (ccx - 14, ccy + 16), cv2.FONT_HERSHEY_SIMPLEX, 1.4, COLOR_WHITE, 3, cv2.LINE_AA)
    cv2.putText(card, "3... 2... 1... SNAP!", (485, 275), cv2.FONT_HERSHEY_SIMPLEX, 0.35, COLOR_GREEN, 1, cv2.LINE_AA)
    cv2.putText(card, "Saves full-res JPEG", (488, 295), cv2.FONT_HERSHEY_SIMPLEX, 0.33, COLOR_GRAY, 1, cv2.LINE_AA)

    out_path = os.path.join(CARDS_DIR, "card_palm_fist_seq.png")
    cv2.imwrite(out_path, card)
    print(f"Generated: {out_path}")

def render_swipe_card():
    w, h = 680, 360
    card = np.full((h, w, 3), COLOR_BG, dtype=np.uint8)

    for x in range(0, w, 30):
        cv2.line(card, (x, 0), (x, h), (24, 18, 14), 1)
    for y in range(0, h, 30):
        cv2.line(card, (0, y), (w, y), (24, 18, 14), 1)

    cv2.rectangle(card, (20, 15), (180, 35), COLOR_VIOLET, 1)
    cv2.putText(card, "KINETIC VELOCITY", (30, 29), cv2.FONT_HERSHEY_SIMPLEX, 0.35, COLOR_VIOLET, 1, cv2.LINE_AA)
    cv2.putText(card, "KINETIC HORIZONTAL SWIPES (👈 / 👉)", (20, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.65, COLOR_WHITE, 2, cv2.LINE_AA)
    cv2.putText(card, "Motion History Buffer & Track Navigation", (20, 82), cv2.FONT_HERSHEY_SIMPLEX, 0.40, COLOR_CYAN, 1, cv2.LINE_AA)
    cv2.line(card, (20, 95), (w - 20, 95), (60, 50, 42), 1)

    # Left: Swipe Left Box
    cv2.rectangle(card, (25, 115), (325, 335), COLOR_DARK_BOX, -1)
    cv2.rectangle(card, (25, 115), (325, 335), COLOR_CYAN, 1)
    cv2.putText(card, "SWIPE LEFT: << PREV TRACK", (40, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.40, COLOR_CYAN, 1, cv2.LINE_AA)

    # Motion trail dots
    for i in range(5):
        alpha_x = 240 - i * 35
        cv2.circle(card, (alpha_x, 210), 10 - i, (120, 80 + i * 20, 240), -1)
    cv2.arrowedLine(card, (250, 210), (80, 210), COLOR_CYAN, 3, tipLength=0.25)
    cv2.putText(card, "Displacement > 0.15 Screen Width", (45, 270), cv2.FONT_HERSHEY_SIMPLEX, 0.34, COLOR_WHITE, 1, cv2.LINE_AA)
    cv2.putText(card, "Plays previous playlist track", (45, 290), cv2.FONT_HERSHEY_SIMPLEX, 0.34, COLOR_GRAY, 1, cv2.LINE_AA)

    # Right: Swipe Right Box
    cv2.rectangle(card, (355, 115), (655, 335), COLOR_DARK_BOX, -1)
    cv2.rectangle(card, (355, 115), (655, 335), COLOR_AMBER, 1)
    cv2.putText(card, "SWIPE RIGHT: NEXT TRACK >>", (370, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.40, COLOR_AMBER, 1, cv2.LINE_AA)

    # Motion trail dots
    for i in range(5):
        alpha_x = 440 + i * 35
        cv2.circle(card, (alpha_x, 210), 10 - i, (80, 160, 255 - i * 20), -1)
    cv2.arrowedLine(card, (430, 210), (600, 210), COLOR_AMBER, 3, tipLength=0.25)
    cv2.putText(card, "Velocity > 0.55 screen width / sec", (375, 270), cv2.FONT_HERSHEY_SIMPLEX, 0.34, COLOR_WHITE, 1, cv2.LINE_AA)
    cv2.putText(card, "Advances to next track in queue", (375, 290), cv2.FONT_HERSHEY_SIMPLEX, 0.34, COLOR_GRAY, 1, cv2.LINE_AA)

    out_path = os.path.join(CARDS_DIR, "card_swipes.png")
    cv2.imwrite(out_path, card)
    print(f"Generated: {out_path}")

def render_two_hand_card():
    w, h = 680, 360
    card = np.full((h, w, 3), COLOR_BG, dtype=np.uint8)

    for x in range(0, w, 30):
        cv2.line(card, (x, 0), (x, h), (24, 18, 14), 1)
    for y in range(0, h, 30):
        cv2.line(card, (0, y), (w, y), (24, 18, 14), 1)

    cv2.rectangle(card, (20, 15), (180, 35), COLOR_GREEN, 1)
    cv2.putText(card, "MULTI-HAND SPATIAL", (30, 29), cv2.FONT_HERSHEY_SIMPLEX, 0.35, COLOR_GREEN, 1, cv2.LINE_AA)
    cv2.putText(card, "TWO-HAND OPEN PALM (🖐🖐)", (20, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.65, COLOR_WHITE, 2, cv2.LINE_AA)
    cv2.putText(card, "Invokes Holographic Command Matrix AR Overlay", (20, 82), cv2.FONT_HERSHEY_SIMPLEX, 0.40, COLOR_CYAN, 1, cv2.LINE_AA)
    cv2.line(card, (20, 95), (w - 20, 95), (60, 50, 42), 1)

    # Virtual Control Panel representation
    cv2.rectangle(card, (40, 115), (640, 335), COLOR_DARK_BOX, -1)
    cv2.rectangle(card, (40, 115), (640, 335), COLOR_CYAN, 1)

    # Draw simulated matrix buttons
    btn_w, btn_h = 160, 38
    btns = [
        ("[1] MODE: HOLO", 60, 140, COLOR_CYAN),
        ("[2] MODE: CAM", 250, 140, COLOR_AMBER),
        ("[3] MODE: MUSIC", 440, 140, COLOR_VIOLET),
        ("PLAY / PAUSE", 60, 195, COLOR_WHITE),
        ("PREV TRACK", 250, 195, COLOR_WHITE),
        ("NEXT TRACK", 440, 195, COLOR_WHITE),
        ("VOLUME -", 60, 250, COLOR_WHITE),
        ("VOLUME +", 250, 250, COLOR_WHITE),
        ("SNAP PHOTO", 440, 250, COLOR_GREEN),
    ]
    for lbl, bx, by, col in btns:
        cv2.rectangle(card, (bx, by), (bx + btn_w, by + btn_h), (38, 30, 24), -1)
        cv2.rectangle(card, (bx, by), (bx + btn_w, by + btn_h), col, 1)
        cv2.putText(card, lbl, (bx + 18, by + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.38, col, 1, cv2.LINE_AA)

    cv2.putText(card, "Trigger: Both hands simultaneously present with open fingers | Touchless Hover & Dwell to Click",
                (45, 315), cv2.FONT_HERSHEY_SIMPLEX, 0.32, COLOR_CYAN, 1, cv2.LINE_AA)

    out_path = os.path.join(CARDS_DIR, "card_two_hand_matrix.png")
    cv2.imwrite(out_path, card)
    print(f"Generated: {out_path}")

render_composite_palm_fist_card()
render_swipe_card()
render_two_hand_card()
