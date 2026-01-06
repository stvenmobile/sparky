#include <Arduino.h>
#include <TFT_eSPI.h> // Hardware-specific library
#include <SPI.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <FastLED.h>

// --- WIFI & MQTT CONFIGURATION ---
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
const char* mqtt_server = "192.168.1.40"; // IP of your Jetson
const int mqtt_port = 1883;

// --- LED RING CONFIGURATION ---
#define LED_PIN_DATA  27
#define LED_PIN_CLOCK 22
#define NUM_LEDS      12
#define BRIGHTNESS    40
#define LED_TYPE      APA102 // The Sipeed Ring uses this or SK9822
#define COLOR_ORDER   BGR    // Try BGR first, change to RGB if colors look weird

// --- OBJECTS ---
TFT_eSPI gfx = TFT_eSPI(); 
WiFiClient espClient;
PubSubClient client(espClient);
CRGB leds[NUM_LEDS];

// --- STATE VARIABLES ---
String currentLedState = "idle";
bool g_isSleeping = false;
unsigned long lastEyeBlink = 0;
int blinkInterval = 3000;

// ==========================================
//   HELPER FUNCTIONS: LED RING
// ==========================================
void updateLedRing() {
  // We use millis() for non-blocking animations
  unsigned long now = millis();
  
  if (currentLedState == "speak") {
    // Green "VU Meter" Scatter
    fadeToBlackBy(leds, NUM_LEDS, 60); // Fast fade
    if (random(10) > 3) { // Flicker effect
        int pos = random(NUM_LEDS);
        leds[pos] = CRGB::Green;
    }
  } 
  else if (currentLedState == "think") {
    // Spinning Purple
    fadeToBlackBy(leds, NUM_LEDS, 40); // Leave a trail
    int pos = (now / 80) % NUM_LEDS;   // Speed of spin
    leds[pos] = CRGB::Purple;
  }
  else if (currentLedState == "listen") {
    // Breathing Cyan
    float breath = (exp(sin(now/2000.0*PI)) - 0.36787944)*108.0;
    fill_solid(leds, NUM_LEDS, CHSV(130, 255, breath)); // Hue 130 is Cyan
  }
  else if (currentLedState == "sleep") {
    // Off (or very dim red heartbeat if you prefer)
    fill_solid(leds, NUM_LEDS, CRGB::Black);
  }
  else {
    // IDLE: Slow Blue Spin (Tony Stark Arc Reactor style)
    fadeToBlackBy(leds, NUM_LEDS, 10);
    int pos = (now / 200) % NUM_LEDS;
    leds[pos] = CRGB::Blue;
  }
  
  FastLED.show();
}

// ==========================================
//   HELPER FUNCTIONS: ROBOT FACE
// ==========================================

// Helper to erase the "Sleep Lines" before opening eyes
static void clearSleepEyes() {
  int y = 110; // Adjust Y to match your screen center
  int w = 80; 
  int gap = 20; 
  int h = 6;
  
  int centerX = gfx.width() / 2;
  int xLeft = centerX - (gap/2) - w;
  int xRight = centerX + (gap/2);

  // Paint Black to erase
  gfx.fillRect(xLeft, y, w, h, TFT_BLACK);
  gfx.fillRect(xRight, y, w, h, TFT_BLACK);
}

void drawSleepEyes() {
  gfx.fillScreen(TFT_BLACK);
  
  int y = 110; 
  int w = 80; 
  int gap = 20; 
  int h = 6;
  
  int centerX = gfx.width() / 2;
  int xLeft = centerX - (gap/2) - w;
  int xRight = centerX + (gap/2);

  // Draw Cyan Lines
  gfx.fillRect(xLeft, y, w, h, TFT_CYAN);
  gfx.fillRect(xRight, y, w, h, TFT_CYAN);
}

void drawOpenEyes() {
  int eyeRadius = 45;
  int gap = 20;
  int y = 110;
  int centerX = gfx.width() / 2;

  // Clear screen if coming from sleep to ensure clean background
  // (Or just erase the lines using clearSleepEyes if mixing)
  
  // Left Eye
  gfx.fillCircle(centerX - eyeRadius - (gap/2), y, eyeRadius, TFT_CYAN);
  // Right Eye
  gfx.fillCircle(centerX + eyeRadius + (gap/2), y, eyeRadius, TFT_CYAN);
}

void blinkEyes() {
  if (g_isSleeping) return; // Don't blink if sleeping

  // Close
  gfx.fillScreen(TFT_BLACK);
  drawSleepEyes(); // Briefly look like sleep lines
  delay(100);
  
  // Open
  clearSleepEyes();
  drawOpenEyes();
}

// ==========================================
//   MQTT CALLBACK
// ==========================================
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String msg = "";
  for (unsigned int i = 0; i < length; i++) {
    msg += (char)payload[i];
  }
  String topicStr = String(topic);

  // --- HANDLE LED COMMANDS ---
  if (topicStr == "robot/leds") {
    currentLedState = msg; // "listen", "think", "speak", "sleep", "idle"
  }

  // --- HANDLE FACE COMMANDS ---
  if (topicStr == "robot/emotion") {
    if (msg == "sleep") {
      g_isSleeping = true;
      currentLedState = "sleep"; // Auto-sync LED
      drawSleepEyes();
    }
    else if (msg == "wake") {
      if (g_isSleeping) {
        clearSleepEyes();
        g_isSleeping = false;
        currentLedState = "idle"; // Auto-sync LED
        drawOpenEyes();
      }
    }
    else if (msg == "happy") {
      // Just ensure eyes are open
      if (g_isSleeping) {
         clearSleepEyes();
         g_isSleeping = false;
      }
      drawOpenEyes();
    }
  }
  
  // --- HANDLE SPEAKING STATE (Animation) ---
  if (topicStr == "robot/state") {
     if (msg == "speaking") {
        // You could add a "mouth moving" animation here later
        // For now, we rely on the LEDs to show speaking
     }
  }
}

void reconnect() {
  while (!client.connected()) {
    if (client.connect("SparkyFace")) {
      // Subscribe to topics
      client.subscribe("robot/emotion");
      client.subscribe("robot/state");
      client.subscribe("robot/leds"); 
    } else {
      delay(2000);
    }
  }
}

// ==========================================
//   SETUP & LOOP
// ==========================================
void setup() {
  // 1. Init Display
  pinMode(21, OUTPUT);    // Define the backlight pin
  digitalWrite(21, HIGH); // Turn it ON!

  gfx.init();
  gfx.setRotation(1); // Landscape
  gfx.fillScreen(TFT_BLACK);
  
  // 2. Init LEDs
  FastLED.addLeds<LED_TYPE, LED_PIN_DATA, LED_PIN_CLOCK, COLOR_ORDER>(leds, NUM_LEDS);
  FastLED.setBrightness(BRIGHTNESS);
  
  // Test LEDs (Red Flash)
  fill_solid(leds, NUM_LEDS, CRGB::Red);
  FastLED.show();
  delay(500);
  fill_solid(leds, NUM_LEDS, CRGB::Black);
  FastLED.show();

  // 3. Init WiFi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
  }

  // 4. Init MQTT
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(mqttCallback);
  
  // Start in Sleep Mode
  g_isSleeping = true;
  drawSleepEyes();
  currentLedState = "sleep";
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  // 1. Update LED Animations (every frame)
  updateLedRing();

  // 2. Handle Blinking (only if awake)
  if (!g_isSleeping) {
    if (millis() - lastEyeBlink > blinkInterval) {
      blinkEyes();
      lastEyeBlink = millis();
      blinkInterval = random(2000, 6000); // Random blink time
    }
  }
}