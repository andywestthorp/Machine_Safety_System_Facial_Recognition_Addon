#include "esp_camera.h"
#include <WiFi.h>
#include <HTTPClient.h>
#define LGFX_USE_V1
#include <LovyanGFX.hpp>
#include <ArduinoJson.h>
#include <Adafruit_NeoPixel.h> // <-- Add NeoPixel library!

// ============================================================================
// 0. WI-FI & FLASK SERVER CONFIGURATION
// ============================================================================

const char* WIFI_SSID     = "bobby";      
const char* WIFI_PASS     = "sparklebear";  
const char* SERVER_URL    = "http://192.168.1.230:5000/upload"; 

#define BUTTON_PIN 2

// 💡 NEOPIXEL RING LIGHT CONFIGURATION
#define LED_PIN     1     // GPIO 1 is free and suitable!
#define NUM_LEDS   24     // Your 24-LED ring

Adafruit_NeoPixel ring(NUM_LEDS, LED_PIN, NEO_GRB + NEO_KHZ800);

// Helper functions for light effects
void setRingColor(uint8_t r, uint8_t g, uint8_t b, uint8_t brightness = 50) {
  ring.setBrightness(brightness); // Keep brightness capped to prevent brownout
  for (int i = 0; i < NUM_LEDS; i++) {
    ring.setPixelColor(i, ring.Color(r, g, b));
  }
  ring.show();
}

void turnOffRing() {
  ring.clear();
  ring.show();
}

// ============================================================================
// 1. LOVYANGFX DISPLAY CONFIGURATION (GC9A01 Round Display)
// ============================================================================
class LGFX : public lgfx::LGFX_Device {
  lgfx::Panel_GC9A01 _panel_instance;
  lgfx::Bus_SPI _bus_instance;

public:
  LGFX() {
    {  // Configure SPI Bus
      auto cfg = _bus_instance.config();
      cfg.spi_host = SPI2_HOST;  // FSPI / SPI2
      cfg.spi_mode = 0;
      cfg.freq_write = 20000000;  // 20MHz SPI Clock speed
      cfg.pin_sclk = 48;          // SCLK / CLK (Display)
      cfg.pin_mosi = 47;          // MOSI / SDA / DIN (Display)
      cfg.pin_miso = -1;          // Unused
      cfg.pin_dc = 21;            // DC / RS (Display)
      _bus_instance.config(cfg);
      _panel_instance.setBus(&_bus_instance);
    }
    {  // Configure GC9A01 Panel Settings
      auto cfg = _panel_instance.config();
      cfg.pin_cs = 45;   // CS (Display)
      cfg.pin_rst = 19;  // RES / RST (Display)
      cfg.panel_width = 240;
      cfg.panel_height = 240;
      cfg.invert = true;  // GC9A01 panels require color inversion
      _panel_instance.config(cfg);
    }
    setPanel(&_panel_instance);
  }
};

LGFX lcd;

// ============================================================================
// 2. GOOUUU ESP32-S3-CAM PIN CONFIGURATION
// ============================================================================
#define PWDN_GPIO_NUM -1
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM 15
#define SIOD_GPIO_NUM 4
#define SIOC_GPIO_NUM 5

#define Y9_GPIO_NUM 16
#define Y8_GPIO_NUM 17
#define Y7_GPIO_NUM 18
#define Y6_GPIO_NUM 12
#define Y5_GPIO_NUM 10
#define Y4_GPIO_NUM 8
#define Y3_GPIO_NUM 9
#define Y2_GPIO_NUM 11
#define VSYNC_GPIO_NUM 6
#define HREF_GPIO_NUM 7
#define PCLK_GPIO_NUM 13

// ============================================================================
// 3. SETUP FUNCTION
// ============================================================================
void setup() {
  Serial.begin(115200);

  // Initialize NeoPixel Ring Light
  ring.begin();
  turnOffRing(); // Ensure LEDs are off at boot

  unsigned long startWait = millis();
  while (!Serial && (millis() - startWait < 4000)) {
    delay(10);
  }

  delay(2000);
  Serial.println("\n\n=====================================");
  Serial.println("= ESP32-S3 Face Recogniser (Aug 26) =");
  Serial.println("=====================================\n");
  
  pinMode(BUTTON_PIN, INPUT_PULLUP);

  // A. Initialize Screen
  lcd.init();
  lcd.setRotation(1);
  lcd.fillScreen(TFT_BLACK);
  lcd.setTextColor(TFT_WHITE, TFT_BLACK);
  lcd.setTextDatum(textdatum_t::middle_center);

  // B. Connect to Wi-Fi
  lcd.drawString("Connecting Wi-Fi...", 120, 120, 2);
  Serial.print("Connecting to Wi-Fi");

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  unsigned long wifiStart = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - wifiStart < 8000) {
    delay(500);
    Serial.print(".");
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n✅ Wi-Fi Connected!");
    lcd.drawString(WiFi.localIP().toString().c_str(), 120, 120, 2);
    delay(1000);
  } else {
    Serial.println("\n⚠️ Wi-Fi Connection Timeout");
    lcd.drawString("No WiFi", 120, 120, 2);
    delay(1000);
  }

  // C. Camera Settings
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0       = Y2_GPIO_NUM;
  config.pin_d1       = Y3_GPIO_NUM;
  config.pin_d2       = Y4_GPIO_NUM;
  config.pin_d3       = Y5_GPIO_NUM;
  config.pin_d4       = Y6_GPIO_NUM;
  config.pin_d5       = Y7_GPIO_NUM;
  config.pin_d6       = Y8_GPIO_NUM;
  config.pin_d7       = Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk     = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;
  
  config.xclk_freq_hz = 16000000;         
  config.pixel_format = PIXFORMAT_JPEG;   
  config.frame_size   = FRAMESIZE_QVGA;   
  config.fb_location  = CAMERA_FB_IN_PSRAM;
  config.jpeg_quality = 12;
  config.fb_count     = 2;                

  // D. Initialize Camera
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("❌ Camera init failed: 0x%x\n", err);
    return;
  }

  sensor_t * s = esp_camera_sensor_get();
  if (s != NULL) {
    s->set_vflip(s, 1); 
    s->set_hmirror(s, 1); 
    s->set_brightness(s, 1);   
    s->set_contrast(s, 1);     
    s->set_aec2(s, 1);         
    s->set_ae_level(s, 1);     
  }
  lcd.fillScreen(TFT_BLACK);
}

// ============================================================================
// 4. BUTTON DEBOUNCE HELPER
// ============================================================================
bool isButtonPressed() {
  static unsigned long lastPressTime = 0;

  if (digitalRead(BUTTON_PIN) == LOW) {
    

    if (millis() - lastPressTime > 250) {
      lastPressTime = millis();
      return true;
    }
  }
  return false;
}

// ============================================================================
// 5. ANIMATION & HELPER FUNCTIONS
// ============================================================================
uint16_t dimColor(uint16_t color, float factor) {
  if (factor <= 0.0f) return TFT_BLACK;
  if (factor >= 1.0f) return color;

  uint8_t r = (color >> 11) & 0x1F;
  uint8_t g = (color >> 5) & 0x3F;
  uint8_t b = color & 0x1F;

  r = (uint8_t)(r * factor);
  g = (uint8_t)(g * factor);
  b = (uint8_t)(b * factor);

  return (r << 11) | (g << 5) | b;
}

void drawDotSpinner(uint16_t primaryColor) {
  static int step = 0;
  int centerX = 120, centerY = 120;
  int orbitRadius = 100;
  int maxRadius = 10;

  for (int i = 0; i < 8; i++) {
    int dotAngle = (i * 45) % 360;
    float rad = dotAngle * 0.0174533f;

    int x = centerX + sin(rad) * orbitRadius;
    int y = centerY - cos(rad) * orbitRadius;

    int distanceBehind = (step - i + 8) % 8;
    float brightness = 0.0f;
    int dotRadius = 0;

    if (distanceBehind == 0) {
      brightness = 1.0f;
      dotRadius = maxRadius;
    } else if (distanceBehind <= 4) {
      brightness = 1.0f - (distanceBehind * 0.22f);
      dotRadius = maxRadius - (distanceBehind * 2);
    } else {
      brightness = 0.0f;
      dotRadius = 0;
    }

    lcd.fillCircle(x, y, maxRadius + 1, TFT_BLACK);

    if (dotRadius > 0 && brightness > 0.0f) {
      uint16_t blendedColor = dimColor(primaryColor, brightness);
      lcd.fillCircle(x, y, dotRadius, blendedColor);
    }
  }

  step = (step + 1) % 8;
}

// ============================================================================
// 6. UPLOAD FUNCTION (POST TO FLASK)
// ============================================================================
void uploadImageToFlask(camera_fb_t * fb) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("❌ Wi-Fi Disconnected!");
    turnOffRing();
    return;
  }

  HTTPClient http;
  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "image/jpeg");

  unsigned long startTime = millis();

  // Send binary image frame via HTTP POST
  int httpResponseCode = http.POST(fb->buf, fb->len);

  // Keep rendering dot spinner while HTTP upload progresses
  while (millis() - startTime < 1500) {
    drawDotSpinner(TFT_GREEN);
    delay(30);
  }

  if (httpResponseCode > 0) {
    Serial.printf("✅ Image Uploaded! Server Response Code: %d\n", httpResponseCode);
    
    String responseText = http.getString();
    //Serial.println("📩 Raw Server Response: " + responseText);
// message = f"Face Recognised, RFID= {rfid}\n"
    StaticJsonDocument<512> doc;
    DeserializationError error = deserializeJson(doc, responseText);

    if (!error) {
      bool recognized = doc["recognized"] | false;

      if (recognized) {
        const char* name = doc["results"][0]["name"];
        const char* rfid = doc["results"][0]["rfid"];
        Serial.printf("Face Recognised, RFID=%s\n", rfid);
        
        // 💡 LIGHT RING: Solid Green on match!
        setRingColor(0, 255, 0, 80);

        // 📺 Draw Match Badge on Screen
        lcd.fillScreen(TFT_GREEN);
        lcd.setTextColor(TFT_BLACK, TFT_GREEN);
        lcd.setTextDatum(textdatum_t::middle_center); 
        
        lcd.drawString("MATCH FOUND!", 120, 70, 4);
        lcd.drawString(name, 120, 120, 4);
        lcd.drawString(rfid, 120, 160, 2);

      } else {
        // 💡 LIGHT RING: Solid Red on no match
        setRingColor(255, 0, 0, 80);

        // 📺 Draw Unknown Badge on Screen
        lcd.fillScreen(TFT_RED);
        lcd.setTextColor(TFT_WHITE, TFT_RED);
        lcd.setTextDatum(textdatum_t::middle_center);
        
        lcd.drawString("NO MATCH", 120, 100, 4);
        lcd.drawString("Unknown Person", 120, 140, 2);
      }

    } else {
      setRingColor(255, 255, 0, 50); // Yellow on bad JSON
      lcd.fillCircle(120, 120, 35, TFT_YELLOW);
      lcd.setTextColor(TFT_BLACK, TFT_YELLOW);
      lcd.drawString("BAD JSON", 120, 120, 2);
    }

  } else {
    setRingColor(255, 0, 0, 80);
    lcd.fillCircle(120, 120, 35, TFT_RED);
    lcd.setTextColor(TFT_WHITE, TFT_RED);
    lcd.drawString("ERROR", 120, 120, 4);
  }

  http.end();
  delay(2500); // Hold result on screen & ring light
  turnOffRing(); // Turn light back off before resuming stream
}

// ============================================================================
// 7. MAIN STREAMING & CAPTURE LOOP
// ============================================================================
void loop() {
  // 1. Capture live camera feed
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) return;

  // Render JPEG frame to LovyanGFX display
  lcd.drawJpg(fb->buf, fb->len, 0, 0);

  // 2. Check for button snap
  if (isButtonPressed()) {
    Serial.println("📸 SNAP! Button pressed - Sending image...");

    // 💡 FLASH LIGHT: Turn on Natural Warm White (255, 190, 110) at ~20% brightness
    setRingColor(255, 190, 110, 50); 
    delay(100); // Brief pause to let camera exposure adapt

    // Free live stream frame and grab a fresh, well-lit snapshot
    esp_camera_fb_return(fb);
    fb = esp_camera_fb_get();

    // Overlay status text
    lcd.setTextColor(TFT_CYAN, TFT_BLACK);
    lcd.drawString("CHECKING...", 120, 120, 2);

    // Perform HTTP POST to Flask
    uploadImageToFlask(fb);
  }

  esp_camera_fb_return(fb);
}