// src/lgfx_cyd28.hpp
#pragma once
#define LGFX_USE_V1
#include <LovyanGFX.hpp>

// --- Adjust these if needed for your ESP32_2432S028 variant ---
static const int PIN_TFT_CS   = 15;
static const int PIN_TFT_DC   = 2;
static const int PIN_TFT_RST  = -1;
static const int PIN_TFT_BL   = 21;   // backlight (PWM-capable)
static const int PIN_SCLK     = 14;
static const int PIN_MOSI     = 13;
static const int PIN_MISO     = 12;   // not used on many CYD boards

// Many ESP32_2432S028 units ship with ST7789 240x320 SPI panels.
// If yours is ILI9341, change Panel_ST7789 to Panel_ILI9341 and set memory size.
class LGFX : public lgfx::LGFX_Device {
public:
  LGFX() {
    // SPI bus
    auto cfg_bus = _bus.config();
    cfg_bus.spi_host   = SPI3_HOST;   // VSPI
    cfg_bus.spi_mode   = 0;
    cfg_bus.freq_write = 40000000;    // 40 MHz is fine to start
    cfg_bus.freq_read  = 16000000;
    cfg_bus.pin_sclk   = PIN_SCLK;
    cfg_bus.pin_mosi   = PIN_MOSI;
    cfg_bus.pin_miso   = PIN_MISO;
    cfg_bus.pin_dc     = PIN_TFT_DC;
    _bus.config(cfg_bus);
    _panel.setBus(&_bus);

    // Panel
    auto cfg = _panel.config();
    cfg.pin_cs        = PIN_TFT_CS;
    cfg.pin_rst       = PIN_TFT_RST;
    cfg.pin_busy      = -1;
    cfg.panel_width   = 240;
    cfg.panel_height  = 320;
    cfg.offset_x      = 0;
    cfg.offset_y      = 0;
    cfg.offset_rotation = 0;
    cfg.readable      = (PIN_MISO >= 0);
    cfg.invert        = false;
    cfg.rgb_order     = false;
    cfg.dlen_16bit    = false;
    cfg.bus_shared    = true;
    _panel.config(cfg);

    // Backlight
    auto bl = _light.config();
    bl.pin_bl = PIN_TFT_BL;
    bl.freq   = 12000;
    bl.pwm_channel = 7;
    _light.config(bl);
    _panel.setLight(&_light);

    setPanel(&_panel);
  }

private:
  lgfx::Bus_SPI       _bus;
  lgfx::Panel_ILI9341 _panel;   // ST7789, ILI9341;
  lgfx::Light_PWM     _light;
};
