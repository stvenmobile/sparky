#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <LovyanGFX.hpp>
#include "lgfx_cyd28.hpp"      
#include "eyes.h"
#include "mouth_patterns.h"

// ================= NETWORK CONFIG =================
// ⚠️ UPDATE THESE FOR YOUR NETWORK
const char* WIFI_SSID = "googlewifi";
const char* WIFI_PASS = "abc123def456";
const char* MQTT_BROKER = "192.168.1.40"; // Sentinel/Jetson IP
const int   MQTT_PORT   = 1883;

// ================= HARDWARE CONFIG ================
static LGFX gfx;
static Eyes::State  EYES;
static Eyes::Layout E_LAYOUT;

// ================= FACE GLOBALS ===================
static constexpr float   MOUTH_WIDTH_FACTOR    = 0.55f * (2.0f/3.0f);
static constexpr int     MOUTH_BASELINE_OFFSET = 48;
static constexpr int     MOUTH_EXTRA_DOWN      = 0;
static constexpr uint32_t TALK_SWAP_MS_BASE    = 160;
static constexpr uint32_t TALK_SWAP_JITTER     = 40;

// Speeds: Slower eyes when talking looks more natural
static constexpr float EYES_DT_IDLE   = 1.0f;
static constexpr float EYES_DT_TALK   = 0.65f;

enum class SpeechState : uint8_t { Silent=0, Talking };
static SpeechState g_speech = SpeechState::Silent;
static MouthMood g_currMood = MouthMood::Neutral;

static uint32_t g_nextMouthSwapMs = 0;
static int      g_currTalkIdx     = 0;
static int      g_mouthY = -1;
static int      g_mouthW = -1;

WiFiClient espClient;
PubSubClient client(espClient);

static inline uint32_t nowMs(){ return millis(); }

// ----------------- DRAWING HELPERS -----------------
static void drawMouthFrame(int baseY, int mouthW, const MouthFrame& mf) {
  const int W = gfx.width();
  const int mouthX = (W - mouthW) / 2;
  const int clearY0 = baseY - MOUTH_MAX_DY - MOUTH_CLEAR_PAD;
  const int clearY1 = baseY + MOUTH_MAX_DY + MOUTH_CLEAR_PAD;
  gfx.fillRect(mouthX, clearY0, mouthW, clearY1 - clearY0 + 1, TFT_BLACK);

  gfx.drawFastHLine(mouthX, baseY, ANCHOR_PX, TFT_WHITE);
  gfx.drawFastHLine(mouthX + mouthW - ANCHOR_PX, baseY, ANCHOR_PX, TFT_WHITE);

  const int innerW = mouthW - 2*ANCHOR_PX;
  if (innerW <= 0) return;
  const int segW   = max(1, innerW / MOUTH_SEGMENTS);
  const int rem    = innerW - segW * MOUTH_SEGMENTS;
  int x = mouthX + ANCHOR_PX;

  for (int i = 0; i < MOUTH_SEGMENTS; ++i) {
    int w  = segW + ((i == MOUTH_SEGMENTS - 1) ? rem : 0);
    int uy = constrain(mf.upper[i], -MOUTH_MAX_DY, MOUTH_MAX_DY);
    int ly = constrain(mf.lower[i], -MOUTH_MAX_DY, MOUTH_MAX_DY);
    gfx.drawFastHLine(x, baseY - uy, w, TFT_WHITE);
    gfx.drawFastHLine(x, baseY - ly, w, TFT_WHITE);
    x += w;
  }
}

static void drawMouthMood(MouthMood mood) {
  drawMouthFrame(g_mouthY, g_mouthW, moodToFrame(mood));
}

static void drawMouthTalkIdx(int idx) {
  idx = (idx % NUM_TALK_FRAMES + NUM_TALK_FRAMES) % NUM_TALK_FRAMES;
  drawMouthFrame(g_mouthY, g_mouthW, TALK_FRAMES[idx]);
}

// ----------------- STATE MANAGERS -----------------
static void enterSilent(){
  g_speech = SpeechState::Silent;
  gfx.startWrite();
  drawMouthMood(g_currMood);
  gfx.endWrite();
}

static void enterTalking(){
  g_speech = SpeechState::Talking;
  g_currTalkIdx = random(NUM_TALK_FRAMES);
  g_nextMouthSwapMs = nowMs() + TALK_SWAP_MS_BASE;
  gfx.startWrite();
  drawMouthTalkIdx(g_currTalkIdx);
  gfx.endWrite();
}

static void setMood(MouthMood m) {
  g_currMood = m;
  if (g_speech == SpeechState::Silent) {
    enterSilent(); // Redraw immediately
  }
}

// ----------------- MQTT LOGIC -----------------
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String msg;
  for (int i = 0; i < length; i++) msg += (char)payload[i];
  msg.toLowerCase();
  String strTopic = String(topic);

  // Debug Print
  Serial.print("MQTT ["); Serial.print(topic); Serial.print("]: "); Serial.println(msg);

  // 1. Robot State
  if (strTopic == "robot/state") {
    if (msg == "speaking") enterTalking();
    else enterSilent(); 
  }
  // 2. Robot Emotion
  else if (strTopic == "robot/emotion") {
    if (msg == "happy" || msg == "smile") setMood(MouthMood::Smile);
    else if (msg == "sad" || msg == "frown") setMood(MouthMood::Frown);
    else if (msg == "surprise" || msg == "oooh") setMood(MouthMood::Oooh);
    else if (msg == "confused" || msg == "puzzled") setMood(MouthMood::Puzzled);
    else setMood(MouthMood::Neutral);
  }
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("Connecting to MQTT...");
    // Connect with Client ID "SparkyFace"
    if (client.connect("SparkyFace")) {
      Serial.println("connected");
      client.subscribe("robot/#"); // Subscribe to all robot topics
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" retrying in 5s");
      delay(5000);
    }
  }
}

// ----------------- MAIN SETUP -----------------
void setup() {
  Serial.begin(115200);
  
  // 1. Display Init
  gfx.init();
  gfx.setRotation(3); // USB ports on right
  gfx.fillScreen(TFT_BLACK);
  
  // 2. WiFi Setup
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Connecting WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi Connected.");

  // 3. MQTT Setup
  client.setServer(MQTT_BROKER, MQTT_PORT);
  client.setCallback(mqttCallback);

  // 4. Face Init
  Eyes::init(gfx, EYES, E_LAYOUT);
  int H = gfx.height();
  g_mouthY = H - MOUTH_BASELINE_OFFSET - MOUTH_EXTRA_DOWN;
  g_mouthW = (int)roundf(gfx.width() * MOUTH_WIDTH_FACTOR);

  // 5. Default State
  setMood(MouthMood::Neutral);
  enterSilent();
}

// ----------------- MAIN LOOP -----------------
void loop() {
  // 1. Network Housekeeping
  if (!client.connected()) reconnect();
  client.loop();

  // 2. Timing
  static uint32_t lastMs = nowMs();
  uint32_t tNow = nowMs();
  uint32_t dtMs = tNow - lastMs;
  if (dtMs > 100) dtMs = 100;
  lastMs = tNow;

  // 3. Eye Physics (Autonomous)
  float eyeScale = (g_speech == SpeechState::Talking) ? EYES_DT_TALK : EYES_DT_IDLE;
  Eyes::update(gfx, EYES, eyeScale * (dtMs / 1000.0f));

  // 4. Mouth Animation (Only when Talking)
  if (g_speech == SpeechState::Talking && tNow >= g_nextMouthSwapMs) {
    int nextIdx = g_currTalkIdx;
    while (nextIdx == g_currTalkIdx) nextIdx = random(NUM_TALK_FRAMES);
    g_currTalkIdx = nextIdx;

    gfx.startWrite();
    drawMouthTalkIdx(g_currTalkIdx);
    gfx.endWrite();

    g_nextMouthSwapMs = tNow + TALK_SWAP_MS_BASE + random(TALK_SWAP_JITTER*2) - TALK_SWAP_JITTER;
  }

  delay(16); // ~60 FPS Cap
}