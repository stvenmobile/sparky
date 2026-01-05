#pragma once
#include <stdint.h>

// ====== Global mouth geometry ======
static constexpr int   MOUTH_SEGMENTS   = 21; // smoother contours
static constexpr int   MOUTH_MAX_DY     = 12; // abs max px offset per lip
static constexpr int   MOUTH_CLEAR_PAD  = 5;  // vertical clear band around mouth
static constexpr int   ANCHOR_PX        = 2;  // fixed pixels at each end that never move

// Signed offsets per lip, relative to baseline (0)
// +N = above baseline; -N = below baseline
struct MouthFrame {
  int8_t upper[MOUTH_SEGMENTS];
  int8_t lower[MOUTH_SEGMENTS];
};

// ====== Moods (static shapes) ======
enum class MouthMood : uint8_t { Neutral=0, Smile, Frown, Puzzled, Oooh };

#define MF_UP(...)  { __VA_ARGS__ }
#define MF_LO(...)  { __VA_ARGS__ }

// Helper comment: 21 points are indexed 0..20 (center at 10).

// Neutral: single slightly-open line (lower just a hair below baseline)
static const MouthFrame MOOD_NEUTRAL = {
  MF_UP( 0,0,0,0,0,0,0,0,1,1, 1, 1,1,0,0,0,0,0,0,0,0 ),
  MF_LO( -1,-1,-1,-1,-1,-1,-2,-2,-2,-2, -2, -2,-2,-2,-2,-1,-1,-1,-1,-1,-1 )
};

// Smile: upper = subtle ∩, lower = deeper ∪
static const MouthFrame MOOD_SMILE = {
  MF_UP( 6,4,0,-4,-4,-6,-6,-9,-9,-10, -12, -10,-9,-9,-6,-6,-4,-4,0,4,6 ),
  MF_LO( 5,2,-2,-5,-5,-6,-9,-9,-9,-10, -12, -10,-9,-9,-9,-6,-5,-5,-2,2,5 )
};

// Frown: upper = deeper ∩, lower = subtle ∪ (inverted smile)
static const MouthFrame MOOD_FROWN = {
  MF_UP( -4,-2,2,4,5,6,9,9,11,12, 12, 12,11,9,9,6,5,4,2,-2,-4 ),
  MF_LO( -6,-3,0,3,4,7,7,8,8,9, 10, 9,8,8,7,7,4,3,0,-3,-6 )
};

// Puzzled: mild asymmetry, wavy
static const MouthFrame MOOOD_PUZZLED_FALLBACK = { // in case of typo use this name
  MF_UP( 0,0,1,2,2,  1,3,1,  2,0, 1, 1,0, 2,1,3, 1,2,1,0,0 ),
  MF_LO( 0,0,-1,0,-2, -1,-2,-1, -1,0, -1, -1,0, -2,-1,-2, -1,0,-1,0,0 )
};
static const MouthFrame MOOD_PUZZLED = {
  MF_UP( 0,0,1,2,2,  1,3,1,  2,0, 1, 1,0, 2,1,3, 1,2,1,0,0 ),
  MF_LO( 0,0,-1,0,-2, -1,-2,-1, -1,0, -1, -1,0, -2,-1,-2, -1,0,-1,0,0 )
};

// “Oooh”: rounded O—symmetric upper(+)/lower(-)
static const MouthFrame MOOD_OOOH = {
  MF_UP( 2,4,4,7,7, 7,8,10,10,12, 12, 12,10,10,8,7,7,7,4,4,2 ),
  MF_LO( -2,-3,-5,-7,-7, -8,-8,-10,-10,-11, -12, -11,-10,-10,-8,-8,-7,-7,-5,-3,-2 )
};

static inline const MouthFrame& moodToFrame(MouthMood m) {
  switch (m) {
    case MouthMood::Smile:   return MOOD_SMILE;
    case MouthMood::Frown:   return MOOD_FROWN;
    case MouthMood::Puzzled: return MOOD_PUZZLED;
    case MouthMood::Oooh:    return MOOD_OOOH;
    case MouthMood::Neutral:
    default:                 return MOOD_NEUTRAL;
  }
}

// ====== Talking frames (animated bank, signed) ======
// Keep within [-MOUTH_MAX_DY, +MOUTH_MAX_DY]. 21-point versions.
static const MouthFrame TALK_FRAMES[] = {
  // Gentle vowel-ish
  { MF_UP( 0,0,0,0,0, 1,1,2,2,2, 3, 2,2,2,1,1,0,0,0,0,0 ),
    MF_LO( 0,0,0,0,0, -1,-1,-2,-2,-2, -3, -2,-2,-2,-1,-1,0,0,0,0,0 ) },

  // Medium open, centered
  { MF_UP( 0,0,1,2,2, 3,4,4,5,5, 6, 5,5,4,4,3,2,2,1,0,0 ),
    MF_LO( 0,0,-1,-2,-2, -3,-4,-4,-5,-5, -6, -5,-5,-4,-4,-3,-2,-2,-1,0,0 ) },

  // Wide open "O"
  { MF_UP( 0,1,2,3,4, 5,6,7,8,9, 10, 9,8,7,6,5,4,3,2,1,0 ),
    MF_LO( 0,-1,-2,-3,-4, -5,-6,-7,-8,-9, -10, -9,-8,-7,-6,-5,-4,-3,-2,-1,0 ) },

  // Single-line lower chatter
  { MF_UP( 0,0,0,0,0, 0,0,0,0,0, 0, 0,0,0,0,0,0,0,0,0,0 ),
    MF_LO( 0,0,-1,-2,-3, -2,-1,0,-1,-2, -3, -2,-1,0,-1,-2,-3,-2,-1,0,0 ) },

  // Single-line upper chatter
  { MF_UP( 0,0,1,2,3, 2,1,0,1,2, 3, 2,1,0,1,2,3,2,1,0,0 ),
    MF_LO( 0,0,0,0,0, 0,0,0,0,0, 0, 0,0,0,0,0,0,0,0,0,0 ) },

  // Consonant-ish snaps
  { MF_UP( 0,4,0,5,0, 6,0,5,0,4, 0, 4,0,5,0,6,0,5,0,4,0 ),
    MF_LO( 0,-2,0,-3,0, -4,0,-5,0,-4, 0, -4,0,-5,0,-6,0,-5,0,-4,0 ) },

  // Asymmetric sweep L→R
  { MF_UP( 0,0,1,2,3, 4,5,6,6,5, 4, 3,2,1,1,0,0,0,0,0,0 ),
    MF_LO( 0,0,-1,-2,-3, -4,-5,-6,-6,-5, -4, -3,-2,-1,-1,0,0,0,0,0,0 ) },

  // Asymmetric sweep R→L
  { MF_UP( 0,0,0,0,0, 0,0,1,1,2, 3, 4,5,6,6,5,4,3,2,1,0 ),
    MF_LO( 0,0,0,0,0, 0,0,-1,-1,-2, -3, -4,-5,-6,-6,-5,-4,-3,-2,-1,0 ) },

  // Quiet breathy
  { MF_UP( 0,0,0,0,1, 0,0,0,0,1, 0, 0,0,0,0,1,0,0,0,0,0 ),
    MF_LO( 0,0,0,0,-1, 0,0,0,0,-1, 0, 0,0,0,0,-1,0,0,0,0,0 ) },

  // Small jaw “m-m-m”
  { MF_UP( 0,0,0,0,0, 1,0,0,0,0, 2, 0,0,0,0,1,0,0,0,0,0 ),
    MF_LO( 0,0,0,0,0, -2,0,0,0,0, -3, 0,0,0,0,-2,0,0,0,0,0 ) },
};
static constexpr int NUM_TALK_FRAMES = sizeof(TALK_FRAMES)/sizeof(TALK_FRAMES[0]);

#undef MF_UP
#undef MF_LO
