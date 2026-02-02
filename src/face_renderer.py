import pygame
import socket
import threading
import json
import time
import random
import math
import os
import sys
import io

# --- CONFIGURATION ---
UDP_IP = "127.0.0.1"
CMD_PORT = 5005      # Json Commands
VIDEO_PORT = 5006    # Raw JPEG Stream

# --- RESOLUTION FIX ---
# Back to Native 1024x600 to ensure the Face displays correctly.
SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 600
# ----------------------

# --- PALETTE ---
COLOR_BG = (10, 10, 20)      
COLOR_CYAN = (0, 255, 255)   
COLOR_AMBER = (255, 180, 0)  
COLOR_RED = (255, 50, 50)    
COLOR_GREEN = (50, 255, 50)  
COLOR_FRAME = (40, 40, 60)   
COLOR_SLEEP = (100, 100, 140) 

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
    "last_update": time.time(),
    "error_msg": None,
    "error_time": 0,
    "running": True,
    "view_mode": "face", # 'face' or 'camera'
    "latest_frame": None # Stores the latest video surface
}

# --- CONTROL SERVER (Port 5005) ---
def cmd_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind((UDP_IP, CMD_PORT))
    except OSError:
        print(f"⚠️ Port {CMD_PORT} busy. Exiting.")
        current_state["running"] = False
        return
    
    while current_state["running"]:
        try:
            data, addr = sock.recvfrom(1024)
            msg = json.loads(data.decode())
            
            if "command" in msg:
                cmd = msg["command"]
                if cmd == "shutdown":
                    current_state["running"] = False
                    break
                if cmd == "view_camera":
                    current_state["view_mode"] = "camera"
                if cmd == "view_face":
                    current_state["view_mode"] = "face"

            if "mouth" in msg: current_state["mouth_open"] = float(msg["mouth"])
            if "emotion" in msg: current_state["emotion"] = msg["emotion"]
            if "error" in msg:
                current_state["error_msg"] = msg["error"]
                current_state["error_time"] = time.time()
            current_state["last_update"] = time.time()
        except: pass
    sock.close()

# --- VIDEO SERVER (Port 5006) ---
def video_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind((UDP_IP, VIDEO_PORT))
    except:
        return

    while current_state["running"]:
        try:
            data, _ = sock.recvfrom(65535) 
            if len(data) > 0:
                image_file = io.BytesIO(data)
                frame_surf = pygame.image.load(image_file, "jpg")
                current_state["latest_frame"] = frame_surf
        except: pass
    sock.close()


def get_color(emotion):
    if emotion == "thinking": return COLOR_AMBER
    if emotion == "angry": return COLOR_RED
    if emotion == "happy": return COLOR_GREEN
    if emotion == "sleep": return COLOR_SLEEP
    return COLOR_CYAN

# ... (Draw helpers) ...
def draw_head_frame(surface, cx, cy, width, height, color):
    rect = pygame.Rect(cx - width//2, cy - height//2 - 30, width, height)
    pygame.draw.rect(surface, color, rect, width=8, border_radius=40)
    pygame.draw.line(surface, color, (rect.left + 20, rect.top + 40), (rect.left + 40, rect.top + 20), 3)
    pygame.draw.line(surface, color, (rect.right - 20, rect.bottom - 40), (rect.right - 40, rect.bottom - 20), 3)

def draw_eye(surface, x, y, width, height, emotion, blink_progress, eyebrow_kind="default"):
    color = get_color(emotion)
    if emotion == "sleep":
        pygame.draw.line(surface, color, (x - width//2, y), (x + width//2, y), 5)
        return
    current_h = height * (1 - blink_progress)
    brow_y = y - height//2 - 20 
    cx = surface.get_width() // 2
    if emotion == "thinking":
        pygame.draw.line(surface, color, (x - width//2, brow_y - 30), (x + width//2, brow_y - 30), 5)
    elif emotion == "angry":
        slant = 20
        if x < cx: pygame.draw.line(surface, color, (x - width//2, brow_y - slant), (x + width//2, brow_y + slant), 8)
        else: pygame.draw.line(surface, color, (x - width//2, brow_y + slant), (x + width//2, brow_y - slant), 8)
    else:
        use_arch = (eyebrow_kind == "arched") or (emotion == "happy")
        if use_arch:
            rect = pygame.Rect(x - width//2, brow_y - 30, width, 50)
            pygame.draw.arc(surface, color, rect, 0, 3.14, 5)
        else:
            pygame.draw.line(surface, color, (x - width//2, brow_y), (x + width//2, brow_y), 5)

    if current_h < 5: pygame.draw.line(surface, color, (x - width//2, y), (x + width//2, y), 5)
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
    num_bars = 11; bar_width = 15; spacing = 8
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
        if openness > 0.05: bar_h += random.randint(-5, 5) 
        x = start_x + (i * (bar_width + spacing))
        y = center_y - (bar_h // 2)
        r = pygame.Rect(x, y, bar_width, bar_h)
        pygame.draw.rect(surface, color, r, border_radius=2)

def draw_status_bar(surface, font_large, font_small):
    if current_state["emotion"] == "sleep":
        dots = "." * (int(time.time()) % 4)
        text_surf = font_large.render(f"Zzz{dots}", True, COLOR_SLEEP)
        rect = text_surf.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT - 40))
        surface.blit(text_surf, rect)

    if current_state["error_msg"] and (time.time() - current_state["error_time"] < 10): 
        text_surf = font_small.render(f"⚠️ {current_state['error_msg']}", True, COLOR_RED)
        rect = text_surf.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT - 40))
        bg_rect = rect.inflate(20, 10)
        pygame.draw.rect(surface, (0,0,0), bg_rect)
        surface.blit(text_surf, rect)

def main():
    os.environ['SDL_VIDEO_CENTERED'] = '1'
    pygame.init()
    pygame.font.init() 
    
    font_large = pygame.font.SysFont("monospace", 40, bold=True)
    font_small = pygame.font.SysFont("monospace", 24)

    try:
        screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN)
    except:
        screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        
    pygame.display.set_caption("Sparky Face V2")
    pygame.mouse.set_visible(False)
    clock = pygame.time.Clock()

    # Start Threads
    threading.Thread(target=cmd_server, daemon=True).start()
    threading.Thread(target=video_server, daemon=True).start()
    
    # Wait for UDP check
    time.sleep(0.5)
    if not current_state["running"]:
        pygame.quit(); sys.exit(0)

    # Animation State
    last_blink = time.time(); next_blink_interval = 3.0; is_blinking = False; blink_start = 0; blink_progress = 0.0 
    current_mouth_pattern = "symmetric"; last_pattern_change = time.time(); pattern_interval = 0.08 
    current_eyebrow_shape = "flat"; last_eyebrow_change = time.time(); eyebrow_interval = 0.2
    eyebrow_options = ["flat", "arched"]

    while current_state["running"]:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: current_state["running"] = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: current_state["running"] = False

        screen.fill(COLOR_BG)
        
        # --- 1. VISION MODE (Scaled to fit 1024x600) ---
        if current_state["view_mode"] == "camera":
            if current_state["latest_frame"]:
                frame = current_state["latest_frame"]
                
                # Get dimensions of incoming frame (likely 1024x576 from sparky_vision)
                img_w, img_h = frame.get_size()
                
                # Aspect Ratio Logic: Fit Inside 1024x600
                scale_w = SCREEN_WIDTH / img_w
                scale_h = SCREEN_HEIGHT / img_h
                scale = min(scale_w, scale_h) 
                
                new_w = int(img_w * scale)
                new_h = int(img_h * scale)
                
                frame = pygame.transform.scale(frame, (new_w, new_h))
                
                # Center the image
                x_pos = (SCREEN_WIDTH - new_w) // 2
                y_pos = (SCREEN_HEIGHT - new_h) // 2
                
                screen.blit(frame, (x_pos, y_pos))
                
                # Overlay Text
                lbl = font_large.render("VISION MODE", True, (0, 255, 0))
                screen.blit(lbl, (20, 20))
            else:
                lbl = font_large.render("WAITING FOR VIDEO...", True, COLOR_RED)
                screen.blit(lbl, (SCREEN_WIDTH//2 - 200, SCREEN_HEIGHT//2))
        
        # --- 2. FACE MODE ---
        else:
            now = time.time()
            is_talking = current_state["mouth_open"] > 0.1
            
            if is_talking:
                if now - last_pattern_change > pattern_interval:
                    current_mouth_pattern = random.choice(PATTERN_KEYS); last_pattern_change = now
                if now - last_eyebrow_change > eyebrow_interval:
                    current_eyebrow_shape = random.choice(eyebrow_options); last_eyebrow_change = now
            else:
                current_mouth_pattern = "symmetric"; current_eyebrow_shape = "flat"

            if not is_blinking:
                if now - last_blink > next_blink_interval: is_blinking = True; blink_start = now
            else:
                dur = 0.15; p = (now - blink_start) / dur
                if p >= 1: is_blinking = False; last_blink = now; next_blink_interval = random.uniform(1.0, 5.0); blink_progress = 0.0 
                else: blink_progress = p * 2 if p < 0.5 else 2 - (p * 2)

            cx, cy = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
            draw_head_frame(screen, cx, cy, 600, 500, COLOR_FRAME) 
            emo = current_state["emotion"]
            draw_eye(screen, cx - 140, cy - 90, 110, 130, emo, blink_progress, current_eyebrow_shape)
            draw_eye(screen, cx + 140, cy - 90, 110, 130, emo, blink_progress, current_eyebrow_shape)
            draw_waveform_mouth(screen, cx, cy + 110, current_state["mouth_open"], emo, current_mouth_pattern)

        # Draw Status Bar
        draw_status_bar(screen, font_large, font_small)

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit(0)

if __name__ == "__main__":
    main()