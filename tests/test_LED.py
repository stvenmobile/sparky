import spidev
import time
import math

# --- Configuration ---
NUM_LEDS = 12
SPI_BUS = 0
SPI_DEVICE = 0 # Might be 0 or 1 depending on which SPI you enabled

# Setup SPI
spi = spidev.SpiDev()
spi.open(SPI_BUS, SPI_DEVICE)
spi.max_speed_hz = 8000000  # 8MHz

def send_led_data(colors):
    """
    colors: List of (r, g, b, brightness) tuples.
    Brightness is 0-31. Colors are 0-255.
    """
    # 1. Start Frame (32 bits of 0)
    data = [0x00] * 4
    
    # 2. LED Frames
    for r, g, b, bright in colors:
        # APA102 Protocol:
        # First byte is 111 (header) + 5 bits of brightness
        # Note: Order is usually BGR or RGB depending on batch. Try BGR first.
        brightness_byte = 0xE0 | (bright & 0x1F)
        data += [brightness_byte, b, g, r]
        
    # 3. End Frame (32 bits of 1, or just 0xFF)
    data += [0xFF] * 4
    
    # Send it all at once
    spi.xfer2(data)

def arc_reactor_spin():
    """Makes a spinning blue pattern"""
    print("🔵 Arc Reactor Active (Ctrl+C to stop)")
    offset = 0
    try:
        while True:
            led_buffer = []
            for i in range(NUM_LEDS):
                # Calculate distance from the "spinner"
                dist = (i - offset) % NUM_LEDS
                
                # Make the "head" bright and the "tail" fade out
                if dist < 4:
                    intensity = 255 - (dist * 60)
                else:
                    intensity = 0
                
                # Add Blue Color (R=0, G=0, B=intensity) with partial brightness (15/31)
                led_buffer.append((0, 0, intensity, 15))
            
            send_led_data(led_buffer)
            offset = (offset + 1) % NUM_LEDS
            time.sleep(0.05) # Speed of spin
            
    except KeyboardInterrupt:
        # Turn off on exit
        off = [(0,0,0,0)] * NUM_LEDS
        send_led_data(off)
        print("\n⚫ Power Down.")

if __name__ == "__main__":
    arc_reactor_spin()