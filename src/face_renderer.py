import pygame
import socket
import threading
import json
import time
import random
import math
import os

# --- CONFIGURATION ---
UDP_IP = "127.0.0.1"
UDP_PORT = 5005
SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 600

# --- PALETTE ---
COLOR_BG = (10, 10, 20)      # Deep Space Blue
COLOR_CYAN = (0, 255, 255)   # Neutral
COLOR_AMBER = (255, 180, 0)  # Thinking
COLOR_RED = (255, 50, 50)    # Angry
COLOR_GREEN = (50, 255, 50)  # Happy
COLOR_FRAME = (40, 40, 60)   # Dark Gray/Blue for the head outline
COLOR_SLEEP = (100, 100, 140) # Moonlight Blue

# --- MOUTH SHAPES ---
MOUTH_PATTERNS = {
    "symmetric":  [0.1, 0.2, 0.4, 0.6, 0.9, 1.0, 0.9, 0.6, 0.4, 0.2, 0.1],
    "left_skew":  [0.1, 0.3, 0.6, 0.8, 1.0, 0.8, 0.6, 0.4, 0.3, 0.2, 0.1],
    "right_skew": [0.1, 0.2, 0.3, 0.4, 0.6, 0.8, 1.0, 0.8, 0.6, 0.3, 0.1],
    "jagged_a":   [0.3, 0.8, 0.2, 0.9, 0.3, 0.8, 0.2, 0.9, 0.3, 0.8, 0.2],
    "jagged_b":   [0.8, 0.2, 0.9, 0.2, 0.9, 0.2, 0.9, 0.2, 0.9, 0.2, 0.8],
    "blocky":     [0.5, 0.5, 0.8, 0.8, 1.0, 1.0, 1.0, 0.8, 0.8, 0.5, 0.5],
}
PATTERN_KEYS = list(MOUTH_PATTERNS.keys())

# --- GLOBAL STATE ---
current_state = {
    "mouth_open": 0.0,
    "emotion": "neutral",
    "last_update": time.time()
}

def udp_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    print(f"Face listening on {UDP_IP}:{UDP_PORT}")
    
    while True:
        data, addr = sock.recvfrom(1024)
        try:
            msg = json.loads(data.decode())
            if "mouth" in msg:
                current_state["mouth_open"] = float(msg["mouth"])
            if "emotion" in msg:
                current_state["emotion"] = msg["emotion"]
            current_state["last_update"] = time.time()
        except:
            pass

def get_color(emotion):
    if emotion == "thinking": return COLOR_AMBER
    if emotion == "angry": return COLOR_RED
    if emotion == "happy": return COLOR_GREEN
    if emotion == "sleep": return COLOR_SLEEP
    return COLOR_CYAN

def draw_head_frame(surface, cx, cy, width, height, color):
    rect = pygame.Rect(cx - width//2, cy - height//2, width, height)
    pygame.draw.rect(surface, color, rect, width=8, border_radius=40)
    pygame.draw.line(surface, color, (rect.left + 20, rect.top + 40), (rect.left + 40, rect.top + 20), 3)
    pygame.draw.line(surface, color, (rect.right - 20, rect.bottom - 40), (rect.right - 40, rect.bottom - 20), 3)

def draw_eye(surface, x, y, width, height, emotion, blink_progress, eyebrow_kind="default"):
    color = get_color(emotion)
    
    # SLEEP
    if emotion == "sleep":
        pygame.draw.line(surface, color, (x - width//2, y), (x + width//2, y), 5)
        return

    current_h = height * (1 - blink_progress)
    brow_y = y - height//2 - 20 
    cx = surface.get_width() // 2
    
    # --- EYEBROWS ---
    
    # 1. THINKING: Symmetric High Raise
    if emotion == "thinking":
        pygame.draw.line(surface, color, (x - width//2, brow_y - 30), (x + width//2, brow_y - 30), 5)
        
    # 2. ANGRY: Slanted
    elif emotion == "angry":
        slant = 20
        if x < cx: # Left Eye
            pygame.draw.line(surface, color, (x - width//2, brow_y - slant), (x + width//2, brow_y + slant), 8)
        else:      # Right Eye
            pygame.draw.line(surface, color, (x - width//2, brow_y + slant), (x + width//2, brow_y - slant), 8)
            
    # 3. NEUTRAL / SPEAKING
    else:
        # Check if we should arch (Explicit animation OR Happy static)
        use_arch = (eyebrow_kind == "arched") or (emotion == "happy")
        
        if use_arch:
            # Upside down curve (Arch)
            rect = pygame.Rect(x - width//2, brow_y - 30, width, 50)
            pygame.draw.arc(surface, color, rect, 0, 3.14, 5)
        else:
            # Flat line at standard height
            pygame.draw.line(surface, color, (x - width//2, brow_y), (x + width//2, brow_y), 5)

    # --- EYE PUPIL/SHAPE ---
    if current_h < 5:
        pygame.draw.line(surface, color, (x - width//2, y), (x + width//2, y), 5)
    else:
        rect = pygame.Rect(x - width//2, y - current_h//2, width, current_h)
        pygame.draw.ellipse(surface, color, rect, 4)
        
        if emotion == "thinking":
            offset_x = math.sin(time.time() * 8) * (width * 0.25)
            pygame.draw.circle(surface, color, (x + int(offset_x), y), 8)
        else:
            pygame.draw.circle(surface, color, (x, y), 10)

def draw_waveform_mouth(surface, center_x, center_y, openness, emotion, pattern_name):
    color = get_color(emotion)
    
    num_bars = 11 
    bar_width = 15
    spacing = 8
    
    total_w = (num_bars * bar_width) + ((num_bars - 1) * spacing)
    start_x = center_x - (total_w // 2)

    if openness < 0.1:
        arc_h = 40 
        arc_rect = pygame.Rect(start_x, center_y - arc_h, total_w, arc_h * 2)
        pygame.draw.arc(surface, color, arc_rect, 3.4, 6.0, 4)
        return

    pattern = MOUTH_PATTERNS.get(pattern_name, MOUTH_PATTERNS["symmetric"])
    
    for i in range(num_bars):
        shape_factor = pattern[i]
        bar_h = 4 + (130 * openness * shape_factor)
        
        if openness > 0.05:
            bar_h += random.randint(-5, 5) 
        
        x = start_x + (i * (bar_width + spacing))
        y = center_y - (bar_h // 2)
        
        r = pygame.Rect(x, y, bar_width, bar_h)
        pygame.draw.rect(surface, color, r, border_radius=2)

def main():
    os.environ['SDL_VIDEO_CENTERED'] = '1'
    pygame.init()
    try:
        screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN)
    except:
        screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        
    pygame.display.set_caption("Sparky Face V2")
    pygame.mouse.set_visible(False)
    clock = pygame.time.Clock()

    t = threading.Thread(target=udp_server, daemon=True)
    t.start()

    # Blink Logic
    last_blink = time.time()
    next_blink_interval = 3.0
    is_blinking = False
    blink_start = 0
    blink_progress = 0.0 # FIX: Initialized here

    # Mouth Animation Logic
    current_mouth_pattern = "symmetric"
    last_pattern_change = time.time()
    pattern_interval = 0.08 
    
    # Eyebrow Animation Logic
    current_eyebrow_shape = "flat"
    last_eyebrow_change = time.time()
    eyebrow_interval = 0.2
    eyebrow_options = ["flat", "arched"]

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: running = False
                if event.key == pygame.K_1: current_state["emotion"] = "neutral"
                if event.key == pygame.K_2: current_state["emotion"] = "happy"
                if event.key == pygame.K_3: current_state["emotion"] = "angry"
                if event.key == pygame.K_4: current_state["emotion"] = "thinking"
                if event.key == pygame.K_5: current_state["emotion"] = "sleep"

        # Update Timers
        now = time.time()
        
        # 1. Update Animation States
        is_talking = current_state["mouth_open"] > 0.1
        
        if is_talking:
            # Mouth Shuffle
            if now - last_pattern_change > pattern_interval:
                current_mouth_pattern = random.choice(PATTERN_KEYS)
                last_pattern_change = now
            
            # Eyebrow Shuffle
            if now - last_eyebrow_change > eyebrow_interval:
                current_eyebrow_shape = random.choice(eyebrow_options)
                last_eyebrow_change = now
        else:
            current_mouth_pattern = "symmetric"
            current_eyebrow_shape = "flat"

        # 2. Update Blink
        if not is_blinking:
            if now - last_blink > next_blink_interval:
                is_blinking = True
                blink_start = now
        else:
            dur = 0.15
            p = (now - blink_start) / dur
            if p >= 1:
                is_blinking = False
                last_blink = now
                next_blink_interval = random.uniform(1.0, 5.0)
                blink_progress = 0.0 # Reset progress
            else:
                blink_progress = p * 2 if p < 0.5 else 2 - (p * 2)

        # Draw
        screen.fill(COLOR_BG)
        cx, cy = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        
        draw_head_frame(screen, cx, cy + 30, 600, 540, COLOR_FRAME)

        # Eyes
        emo = current_state["emotion"]
        draw_eye(screen, cx - 140, cy - 60, 110, 130, emo, blink_progress, current_eyebrow_shape)
        draw_eye(screen, cx + 140, cy - 60, 110, 130, emo, blink_progress, current_eyebrow_shape)
        
        # Mouth
        draw_waveform_mouth(screen, cx, cy + 140, current_state["mouth_open"], emo, current_mouth_pattern)

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

if __name__ == "__main__":
    main()