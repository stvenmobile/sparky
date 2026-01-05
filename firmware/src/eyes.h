#pragma once
#include <Arduino.h>
#include <LovyanGFX.hpp>

// ===== Eyes module: handles geometry, gaze, drift/saccades, blink, lids, pupils =====
namespace Eyes {

// ---------- Tunables ----------
static constexpr int   FPS_DEFAULT            = 40;

static constexpr float BASE_UPPER_LID         = 0.48f;  // baseline oval lids
static constexpr float BASE_LOWER_LID         = 0.38f;

static constexpr float LOWER_LID_RATIO        = 0.30f;  // lower-lid follows upper lid at this ratio
static constexpr int   BLINK_INTERVAL_MIN_MS  = 3000;
static constexpr int   BLINK_INTERVAL_MAX_MS  = 8000;
static constexpr int   BLINK_DUR_MS           = 240;
static constexpr int   BLINK_EYE_OFFSET_MS    = 30;
static constexpr int   LID_OVERLAP_PX         = 1;

static constexpr float MICRO_DRIFT_AMP_PX     = 0.7f;
static constexpr float MICRO_DRIFT_HZ         = 0.7f;
static constexpr float MICRO_SACCADE_RATE     = 0.15f;  // prob/sec
static constexpr int   MICRO_SACCADE_PX       = 2;

static constexpr int   FIXATE_MS_MIN          = 350;
static constexpr int   FIXATE_MS_MAX          = 1000;
static constexpr int   SACCADE_MS_MIN         = 60;
static constexpr int   SACCADE_MS_MAX         = 120;
static constexpr int   PURSUIT_MS_MIN         = 1500;
static constexpr int   PURSUIT_MS_MAX         = 3000;
static constexpr float PURSUIT_SPEED_PX_S     = 10.0f;
static constexpr int   PURSUIT_CHANCE_PCT     = 35;
static constexpr int   VERT_OFFSET_MIN        = -8;
static constexpr int   VERT_OFFSET_MAX        = +8;

// Layout knobs (you can pass in overrides at init)
struct Layout {
  int  cxL =  83, cy = 120, cxR = 237;
  int  rWhite = 26;            // sclera radius
  int  rPupil = 11;            // pupil radius
  int  maxOffset = 26;         // pupil horizon from center
  int  targetLidTopMargin = 45;// px from top to TOP of upper lid baseline
  int  eyeNudgeDownPx = 15;    // additional global nudge
};

struct Eye {
  int   cx = 0, cy = 0, rWhite = 0, rPupil = 0, maxOffset = 0;
  int   px = 0, py = 0;
  float lidU = 0.f, lidU_prev = 0.f;
  float lidL = 0.f, lidL_prev = 0.f;

  Eye() = default;
  Eye(int _cx, int _cy, int _rWhite, int _rPupil, int _maxOffset)
  : cx(_cx), cy(_cy), rWhite(_rWhite), rPupil(_rPupil), maxOffset(_maxOffset) {}
};

enum class GazeState { FIXATE, SACCADE, PURSUIT };

struct GazeCtl {
  GazeState state = GazeState::FIXATE;
  float posX = 0.f, posY = 0.f, startX = 0.f, startY = 0.f, targetX = 0.f, targetY = 0.f;
  uint32_t stateStartMs = 0, stateDurMs = 600;
  float driftPhase = 0.f;
};

struct BlinkCtl {
  uint32_t nextTriggerMsL = 0, nextTriggerMsR = 0;
  uint32_t startMsL = 0, startMsR = 0;
  bool activeL = false, activeR = false;
};

struct State {
  Eye L;
  Eye R;
  GazeCtl gaze;
  BlinkCtl blink;
  int oldCy = 120; // for mouth placement deltas (optional)
};

static inline int   clampi(int v, int a, int b){ return v < a ? a : (v > b ? b : v); }
static inline float clampf(float v, float a, float b){ return v < a ? a : (v > b ? b : v); }
static inline uint32_t nowMs(){ return millis(); }
static inline int randRange(int lo, int hi){ return lo + (int)(random(0x7fffffff) % (uint32_t)(hi - lo + 1)); }
static inline float easeInOutCubic(float t){ t = t<0?0:(t>1?1:t); return (t<0.5f)?4*t*t*t:1 - powf(-2*t+2,3)/2; }

// ===== Rendering helpers =====
static void drawEyeRim(LGFX& g, const Eye& e){
  g.fillCircle(e.cx, e.cy, e.rWhite, TFT_WHITE);
  g.drawCircle(e.cx, e.cy, e.rWhite, TFT_DARKGREY);
}

static void paintScleraHBandCircle(LGFX& g, const Eye& e, int yStart, int yEnd) {
  yStart = max(yStart, e.cy - e.rWhite);
  yEnd   = min(yEnd,   e.cy + e.rWhite);
  for (int y = yStart; y < yEnd; ++y) {
    const int dy = y - e.cy;
    const int r2 = e.rWhite * e.rWhite;
    const int maxdx = (int)floorf(sqrtf((float)max(0, r2 - dy*dy)));
    g.drawFastHLine(e.cx - maxdx, y, maxdx * 2 + 1, TFT_WHITE);
  }
}

static void updateUpperLid(LGFX& g, Eye& e, float newLidU) {
  newLidU = clampf(newLidU, 0.f, 1.f);
  const int x0 = e.cx - e.rWhite;
  const int w  = e.rWhite * 2;
  const int yU = e.cy - e.rWhite;
  const int oldH = (int)(e.rWhite * e.lidU_prev);
  const int newH = (int)(e.rWhite * newLidU);
  if (newH == oldH) { e.lidU_prev = e.lidU = newLidU; return; }

  if (newH > oldH) {
    const int y = yU + max(0, oldH - LID_OVERLAP_PX);
    const int h = (newH - oldH) + LID_OVERLAP_PX * 2;
    g.setClipRect(x0, y, w, min(h, (yU + e.rWhite) - y + 1));
    g.fillRect(x0, y, w, min(h, (yU + e.rWhite) - y + 1), TFT_BLACK);
    g.clearClipRect();
  } else {
    paintScleraHBandCircle(g, e, yU + max(0, newH - LID_OVERLAP_PX), yU + oldH + LID_OVERLAP_PX);
  }
  e.lidU_prev = e.lidU = newLidU;
}

static void updateLowerLid(LGFX& g, Eye& e, float newLidL) {
  newLidL = clampf(newLidL, 0.f, 1.f);
  const int x0 = e.cx - e.rWhite;
  const int w  = e.rWhite * 2;
  const int yL = e.cy + e.rWhite;
  const int oldH = (int)(e.rWhite * e.lidL_prev);
  const int newH = (int)(e.rWhite * newLidL);
  if (newH == oldH) { e.lidL_prev = e.lidL = newLidL; return; }

  if (newH > oldH) {
    const int y = yL - newH - LID_OVERLAP_PX;
    const int h = (newH - oldH) + LID_OVERLAP_PX * 2;
    const int yClip = max(y, yL - e.rWhite);
    g.setClipRect(x0, yClip, w, min(h, yL - yClip));
    g.fillRect(x0, yClip, w, min(h, yL - yClip), TFT_BLACK);
    g.clearClipRect();
  } else {
    paintScleraHBandCircle(g, e, yL - oldH - LID_OVERLAP_PX, yL - newH + LID_OVERLAP_PX);
  }
  e.lidL_prev = e.lidL = newLidL;
}

static void movePupil(LGFX& g, Eye& e, int newPx, int newPy) {
  if (newPx == e.px && newPy == e.py) return;

  const int minx = min(e.px, newPx) - e.rPupil - 2;
  const int maxx = max(e.px, newPx) + e.rPupil + 2;
  const int miny = min(e.py, newPy) - e.rPupil - 2;
  const int maxy = max(e.py, newPy) + e.rPupil + 2;

  g.setClipRect(minx, miny, maxx - minx + 1, maxy - miny + 1);
  if (e.px || e.py) g.fillCircle(e.px, e.py, e.rPupil, TFT_WHITE);
  g.fillCircle(newPx, newPy, e.rPupil, TFT_BLACK);
  g.clearClipRect();

  e.px = newPx; e.py = newPy;
}

// ===== Gaze/blink FSM =====
static void enterFixate(State& s, int maxH){
  s.gaze.state=GazeState::FIXATE; s.gaze.stateStartMs=nowMs();
  s.gaze.stateDurMs=randRange(FIXATE_MS_MIN,FIXATE_MS_MAX);
  s.gaze.posY = (float)clampi(randRange(VERT_OFFSET_MIN, VERT_OFFSET_MAX), -maxH, +maxH);
}
static void enterSaccade(State& s, int maxH){
  s.gaze.state=GazeState::SACCADE; s.gaze.stateStartMs=nowMs();
  s.gaze.stateDurMs=randRange(SACCADE_MS_MIN,SACCADE_MS_MAX);
  s.gaze.startX=s.gaze.posX; s.gaze.startY=s.gaze.posY;
  s.gaze.targetX=(float)randRange(-maxH,+maxH);
  s.gaze.targetY=(float)clampi(randRange(VERT_OFFSET_MIN,VERT_OFFSET_MAX),-maxH,+maxH);
}
static void enterPursuit(State& s, int maxH){
  s.gaze.state=GazeState::PURSUIT; s.gaze.stateStartMs=nowMs();
  s.gaze.stateDurMs=randRange(PURSUIT_MS_MIN,PURSUIT_MS_MAX);
  s.gaze.startX=s.gaze.posX; s.gaze.startY=s.gaze.posY;
  s.gaze.targetX=(float)randRange(-maxH,+maxH);
  s.gaze.targetY=(float)clampi(randRange(VERT_OFFSET_MIN,VERT_OFFSET_MAX),-maxH,+maxH);
}
static void scheduleNextBlink(State& s){
  const uint32_t n=nowMs();
  s.blink.nextTriggerMsL = n + randRange(BLINK_INTERVAL_MIN_MS, BLINK_INTERVAL_MAX_MS);
  s.blink.nextTriggerMsR = s.blink.nextTriggerMsL + BLINK_EYE_OFFSET_MS;
}

// ===== Public API =====
static void init(LGFX& g, State& s, const Layout& lay) {
  s.L = Eye(lay.cxL, lay.cy, lay.rWhite, lay.rPupil, lay.maxOffset);
  s.R = Eye(lay.cxR, lay.cy, lay.rWhite, lay.rPupil, lay.maxOffset);
  s.oldCy = s.L.cy;

  // compute eye vertical position from top-of-lid margin + nudge
  int newCy = lay.targetLidTopMargin + (int)lrintf(lay.rWhite * (1.0f - BASE_UPPER_LID));
  newCy += lay.eyeNudgeDownPx;
  s.L.cy = newCy; s.R.cy = newCy;

  // safety: clamp pupil horizon vs rim
  const int safeL = max(0, s.L.rWhite - s.L.rPupil - 4);
  const int safeR = max(0, s.R.rWhite - s.R.rPupil - 4);
  s.L.maxOffset = min(s.L.maxOffset, safeL);
  s.R.maxOffset = min(s.R.maxOffset, safeR);

  drawEyeRim(g, s.L); drawEyeRim(g, s.R);

  s.L.px=s.L.cx; s.L.py=s.L.cy; s.R.px=s.R.cx; s.R.py=s.R.cy;
  g.fillCircle(s.L.px, s.L.py, s.L.rPupil, TFT_BLACK);
  g.fillCircle(s.R.px, s.R.py, s.R.rPupil, TFT_BLACK);

  s.L.lidU_prev = s.L.lidL_prev = 0.f;
  s.R.lidU_prev = s.R.lidL_prev = 0.f;

  g.startWrite();
  updateUpperLid(g, s.L, BASE_UPPER_LID); updateLowerLid(g, s.L, BASE_LOWER_LID);
  updateUpperLid(g, s.R, BASE_UPPER_LID); updateLowerLid(g, s.R, BASE_LOWER_LID);
  g.drawCircle(s.L.cx, s.L.cy, s.L.rWhite, TFT_DARKGREY);
  g.drawCircle(s.R.cx, s.R.cy, s.R.rWhite, TFT_DARKGREY);
  g.endWrite();

  s.L.lidU = s.L.lidU_prev = BASE_UPPER_LID; s.L.lidL = s.L.lidL_prev = BASE_LOWER_LID;
  s.R.lidU = s.R.lidU_prev = BASE_UPPER_LID; s.R.lidL = s.R.lidL_prev = BASE_LOWER_LID;

  s.gaze.posX=0.f; s.gaze.posY=0.f; s.gaze.driftPhase=0.f; enterFixate(s, s.L.maxOffset);
  scheduleNextBlink(s);
}

// one frame update (call at fixed cadence). Returns newCy if you need it for mouth placement.
static int update(LGFX& g, State& s, float dt) {
  const uint32_t tNow = nowMs();
  const uint32_t tIn  = tNow - s.gaze.stateStartMs;

  // Gaze FSM
  if (s.gaze.state==GazeState::FIXATE){
    s.gaze.driftPhase += 2.0f * (float)M_PI * MICRO_DRIFT_HZ * dt;
    float drift = MICRO_DRIFT_AMP_PX * sinf(s.gaze.driftPhase);
    if ((float)random(1000)/1000.0f < MICRO_SACCADE_RATE*dt){
      const int hop = (random(2)? +MICRO_SACCADE_PX : -MICRO_SACCADE_PX);
      s.gaze.posX = clampf(s.gaze.posX + hop, -s.L.maxOffset, +s.L.maxOffset);
    }
    if (tIn >= (uint32_t)random(FIXATE_MS_MIN, FIXATE_MS_MAX+1)){
      (random(100) < PURSUIT_CHANCE_PCT) ? enterPursuit(s, s.L.maxOffset) : enterSaccade(s, s.L.maxOffset);
    } else {
      s.gaze.posX = clampf(s.gaze.posX + drift * dt * 60.0f, -s.L.maxOffset, +s.L.maxOffset);
    }
  } else if (s.gaze.state==GazeState::SACCADE){
    float u = easeInOutCubic((float)tIn / (float)s.gaze.stateDurMs);
    s.gaze.posX = s.gaze.startX + (s.gaze.targetX - s.gaze.startX)*u;
    s.gaze.posY = s.gaze.startY + (s.gaze.targetY - s.gaze.startY)*u;
    if (tIn >= s.gaze.stateDurMs){ s.gaze.posX=s.gaze.targetX; s.gaze.posY=s.gaze.targetY; s.gaze.driftPhase=0; enterFixate(s, s.L.maxOffset); }
  } else { // PURSUIT
    const float dx = s.gaze.targetX - s.gaze.posX, dy = s.gaze.targetY - s.gaze.posY;
    const float len = sqrtf(dx*dx + dy*dy) + 1e-6f, step = PURSUIT_SPEED_PX_S * dt;
    if (len <= step || tIn >= s.gaze.stateDurMs){ s.gaze.posX=s.gaze.targetX; s.gaze.posY=s.gaze.targetY; enterFixate(s, s.L.maxOffset); }
    else { s.gaze.posX += dx/len * step; s.gaze.posY += dy/len * step; }
  }

  // Blink schedule
  if (!s.blink.activeL && tNow >= s.blink.nextTriggerMsL){ s.blink.activeL=true; s.blink.startMsL=tNow; }
  if (!s.blink.activeR && tNow >= s.blink.nextTriggerMsR){ s.blink.activeR=true; s.blink.startMsR=tNow; }

  auto tri = [](uint32_t t0, uint32_t now)->float{
    float ph = (float)(now - t0) / (float)BLINK_DUR_MS; if (ph<0) ph=0; if (ph>1) ph=1;
    return (ph < 0.5f) ? (ph*2.f) : (1.f - (ph - 0.5f)*2.f);
  };

  float targetU_L = BASE_UPPER_LID, targetL_L = BASE_LOWER_LID;
  float targetU_R = BASE_UPPER_LID, targetL_R = BASE_LOWER_LID;

  if (s.blink.activeL){
    float u = tri(s.blink.startMsL, tNow);
    targetU_L = BASE_UPPER_LID + u;
    targetL_L = BASE_LOWER_LID + u * LOWER_LID_RATIO;
    if ((tNow - s.blink.startMsL) >= (uint32_t)BLINK_DUR_MS){ s.blink.activeL=false; scheduleNextBlink(s); }
  }
  if (s.blink.activeR){
    float u = tri(s.blink.startMsR, tNow);
    targetU_R = BASE_UPPER_LID + u;
    targetL_R = BASE_LOWER_LID + u * LOWER_LID_RATIO;
    if ((tNow - s.blink.startMsR) >= (uint32_t)BLINK_DUR_MS){ s.blink.activeR=false; }
  }

  const int newLx = clampi(s.L.cx + (int)lrintf(s.gaze.posX), s.L.cx - s.L.maxOffset, s.L.cx + s.L.maxOffset);
  const int newLy = clampi(s.L.cy + (int)lrintf(s.gaze.posY), s.L.cy - s.L.maxOffset, s.L.cy + s.L.maxOffset);
  const int newRx = clampi(s.R.cx + (int)lrintf(s.gaze.posX), s.R.cx - s.R.maxOffset, s.R.cx + s.R.maxOffset);
  const int newRy = clampi(s.R.cy + (int)lrintf(s.gaze.posY), s.R.cy - s.R.maxOffset, s.R.cy + s.R.maxOffset);

  g.startWrite();
  movePupil(g, s.L, newLx, newLy);
  movePupil(g, s.R, newRx, newRy);
  updateUpperLid(g, s.L, targetU_L); updateLowerLid(g, s.L, targetL_L);
  updateUpperLid(g, s.R, targetU_R); updateLowerLid(g, s.R, targetL_R);
  g.drawCircle(s.L.cx, s.L.cy, s.L.rWhite, TFT_DARKGREY);
  g.drawCircle(s.R.cx, s.R.cy, s.R.rWhite, TFT_DARKGREY);
  g.endWrite();

  return s.L.cy; // current eye center Y (useful for mouth placement)
}

} // namespace Eyes
