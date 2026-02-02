import cv2
import threading
import time
import socket
import numpy as np
from ultralytics import YOLO

# Settings for Video Stream
UDP_IP = "127.0.0.1"
VIDEO_PORT = 5006 

class SparkyVision:
    def __init__(self, camera_index=0, model_size='s'):
        print(f"👁️ Initializing Vision System (YOLOv8{model_size})...")
        self.camera_index = camera_index
        self.running = False
        self.streaming = False 
        self.latest_detections = []
        self.lock = threading.Lock()
        self.thread = None
        
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        try:
            model_name = f'yolov8{model_size}.pt'
            print(f"   - Loading {model_name}...")
            self.model = YOLO(model_name)
        except Exception as e:
            print(f"❌ Vision Error: {e}")
            self.camera_active = False
            return

        self.cap = cv2.VideoCapture(self.camera_index)
        
        # Camera Resolution: 720p (Good balance of quality vs speed)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        
        if not self.cap.isOpened():
            print("⚠️ Vision Warning: Camera not found.")
            self.camera_active = False
        else:
            print(f"✅ Vision System Online (Res: {int(self.cap.get(3))}x{int(self.cap.get(4))})")
            self.camera_active = True

    def start(self):
        if not self.camera_active: return
        self.running = True
        self.thread = threading.Thread(target=self._update_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Stops the thread safely to prevent crashes on exit."""
        self.running = False
        if self.thread and self.thread.is_alive():
            # Wait up to 1 second for the loop to finish its current cycle
            self.thread.join(timeout=1.0)
        
        if self.camera_active:
            self.cap.release()

    def set_streaming(self, active):
        self.streaming = active
        print(f"👁️ Video Streaming: {'ON' if active else 'OFF'}")

    def _update_loop(self):
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.1); continue

            # 1. INFERENCE
            # We use a low base confidence (0.35) so we don't miss people
            results = self.model(frame, verbose=False, conf=0.35)
            
            # 2. SMART FILTERING
            current_objects = []
            r = results[0]
            
            for box in r.boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                label = self.model.names[cls_id]
                
                # Rule A: Ignore cell phones/remotes unless > 60% sure
                if label in ["cell phone", "remote"] and conf < 0.60:
                    continue 
                
                # Rule B: Ignore "dining table"
                if label == "dining table":
                    continue
                
                current_objects.append(label)

            with self.lock:
                self.latest_detections = current_objects

            # 3. STREAMING (Optimized 1024 width)
            if self.streaming:
                try:
                    annotated_frame = results[0].plot()
                    # Resize to fit screen width exactly (1024x576 is standard 16:9)
                    display_frame = cv2.resize(annotated_frame, (1024, 576))
                    _, buffer = cv2.imencode('.jpg', display_frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
                    
                    if len(buffer) < 65000:
                        self.sock.sendto(buffer.tobytes(), (UDP_IP, VIDEO_PORT))
                except Exception as e:
                    print(f"Stream Error: {e}")

            time.sleep(0.03) # ~30 FPS

    def get_what_i_see(self):
        with self.lock:
            objs = self.latest_detections
        
        if not objs:
            return "I am looking, but I don't see any familiar objects."
        
        counts = {}
        for obj in objs:
            counts[obj] = counts.get(obj, 0) + 1
            
        desc_parts = []
        
        # --- PRIORITY 1: ALWAYS SAY PERSON FIRST ---
        if "person" in counts:
            count = counts.pop("person")
            # Using "1 person" as requested
            desc_parts.append(f"{count} person{'s' if count > 1 else ''}")

        # --- PRIORITY 2: EVERYTHING ELSE ---
        # Sort remaining items alphabetically so the list is stable
        for obj in sorted(counts.keys()):
            count = counts[obj]
            s = "s" if count > 1 else ""
            desc_parts.append(f"{count} {obj}{s}")
            
        # --- GRAMMAR FORMATTING ---
        if not desc_parts:
            return "I am looking, but I don't see any familiar objects."
        
        if len(desc_parts) == 1:
            return "I can see " + desc_parts[0] + "."
        else:
            # Join with commas, but use "and" for the last item
            # Example: "1 person, 1 cell phone and 1 cup"
            all_but_last = ", ".join(desc_parts[:-1])
            last_item = desc_parts[-1]
            return f"I can see {all_but_last} and {last_item}."