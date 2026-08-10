/**************************************************************************
  Wiring:

  TFT-LCD      NodeMCU
  ====================
  VCC  ------  3.3v
  GND  ------` GND
  CS   ------  GPIO 15 (Pin D8)
  RST  ------  RST
  A0   ------  GPIO 2  (Pin D4)
  MOSI ------  GPIO 13 (Pin D7)
  SCK  ------  GPIO 14 (Pin D5)
  LED  ------  3.3v

  Screen size:  128 x 160 pixels

  RFID Scanner    NodeMCU
  =======================
  3.3v  ----------  3.3v
  RST ------------  RST
  GND ------------  GND
  IRQ
  MISO  ----------- GPIO 12 (Pin D6)
  MOSI  ----------- GPIO 13 (Pin D7)
  SCK   ----------- GPIO 14 (Pin D5)
  SDA   ----------- GPIO 16 (Pin D0)

 **************************************************************************/

#include <Arduino.h>
#include <LittleFS.h>
// Scanner number and machine name
String Scanner = "DT-3";
String machine_name = "Hi! I am the Rexon Bandsaw BS10SA.";

// The TFT Details
#include <Adafruit_GFX.h>     // Core graphics library
#include <Adafruit_ST7735.h>  // Hardware-specific library for ST7735
#include <Fonts/FreeMonoBoldOblique12pt7b.h>
#include <Fonts/FreeSerif9pt7b.h>
#include "images.h"
#include <SPI.h>

#define TFT_CS 15
#define TFT_RST 16  // May cause trouble?
#define TFT_DC 2

Adafruit_ST7735 tft = Adafruit_ST7735(TFT_CS, TFT_DC, TFT_RST);

#define BLACK 0x0000
#define NAVY 0x000F
#define DARKGREEN 0x03E0
#define DARKCYAN 0x03EF
#define MAROON 0x7800
#define PURPLE 0x780F
#define OLIVE 0x7BE0
#define LIGHTGREY 0xC618
#define DARKGREY 0x7BEF
#define BLUE 0x001F
#define GREEN 0x07E0
#define CYAN 0x07FF
#define RED 0xF800
#define MAGENTA 0xF81F
#define YELLOW 0xFFE0
#define WHITE 0xFFFF
#define ORANGE 0xFD20
#define GREENYELLOW 0xAFE5
#define PINK 0xF81F

// The RFID Scanner details
#include <MFRC522.h>
constexpr uint8_t RST_PIN = D3;
constexpr uint8_t SS_PIN = D0;
MFRC522 rfid(SS_PIN, RST_PIN);

MFRC522::MIFARE_Key key;
String tag;

int blockNum = 2;
byte blockData[16] = { "DTSafety-Master" };
byte bufferLen = 18;
byte readBlockData[18];

MFRC522::StatusCode status;

// The buzzer:
int frequency = 2000;  // Specified in Hz
int buzzPin = D1;
int timeOn = 100;   // Specified in milliseconds
int timeOff = 100;  // Specified in milliseconds

// The WiFi & Secure HTTP details
#include <ESP8266WiFi.h>
#include <ESP8266WiFiMulti.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClientSecure.h>
#include <WiFiUdp.h>

ESP8266WiFiMulti WiFiMulti;

#include <ESPAsyncTCP.h>
#include <ESPAsyncWebServer.h>

#define ELEGANTOTA_USE_ASYNC_WEBSERVER 1
#include <ElegantOTA.h>

AsyncWebServer server(80);

const char* ssid = "<SSID>";
const char* password = "<Password>";

// Main HTTPS Endpoint
const char* rfid_endpoint = "https://<address>/rfid.php";

String User_Key_Value = "";
String update_progress = "0%";
bool updating = false;

int WiFi_Connection_Attempts = 0;
boolean master_key_overide = false;

bool cycle_in_progress = false;

unsigned long previousMillis = 0;  // Stores last time WiFi check-in occurred
const long interval = 5 * 60000;   // Interval (5 minutes)

#define Cycle_Start_PIN 4        // Pulled LOW to activate relays
#define Cycle_in_progress_PIN 0  // HIGH at end of cycle
// Forward declaration of functions
void check_with_server(bool is_pi_source = false);

void setup() {
  // Power-on beep sequence
  bleep(1000, 100);
  bleep(2000, 100);
  bleep(3000, 100);

  SPI.begin();
  rfid.PCD_Init();
  delay(1000);
  Serial.begin(115200);
  Serial.println(F("**************************"));
  Serial.println(F("DT Safety System August 2026"));
  Serial.println(F("(New Facial detection features)"));
  Serial.println(F("**************************\n"));

  // Load persistent parameters from flash
  loadConfig();
  Serial.println(machine_name);

  Serial.println("Setting up pins");
  pinMode(Cycle_Start_PIN, OUTPUT);
  pinMode(Cycle_in_progress_PIN, INPUT_PULLUP);
  digitalWrite(Cycle_Start_PIN, HIGH);

  Serial.println("Starting Screen");
  tft.initR(INITR_BLACKTAB);
  tft.setRotation(1);
  tft.setFont(&FreeSerif9pt7b);
  Serial.println(F("TFT Initialized"));

  tft.setTextColor(BLACK);
  tft.fillScreen(WHITE);
  tft.setCursor(20, 25);
  tft.println("Machine Safety");
  tft.setCursor(50, 45);
  tft.println("System");

  tft.fillRect(65, 60, 30, 38, BLUE);
  tft.drawBitmap(65, 60, logo, 30, 38, 0xffff);

  Serial.println("Setting up WiFi");
  WiFi.mode(WIFI_STA);
  WiFiMulti.addAP(ssid, password);  // Register credentials with WiFiMulti

  while (WiFiMulti.run() != WL_CONNECTED && WiFi_Connection_Attempts < 10) {
    Serial.print("Connecting to WiFi attempt ");
    Serial.println(WiFi_Connection_Attempts);
    delay(500);
    WiFi_Connection_Attempts++;
  }

  if (WiFiMulti.run() != WL_CONNECTED) {
    Serial.println("No Connection - Master Key Mode");
    master_key_overide = true;
  }

  // Network Details
  IPAddress ip = WiFi.localIP();
  String ipStr = ip.toString();

  Serial.println("");
  Serial.println("==================================");
  Serial.print("Connected to WiFi! IP address: ");
  Serial.println(ipStr);
  Serial.print("Web Console available at: http://");
  Serial.println(ipStr);
  Serial.println("==================================");

  // Print IP to TFT Screen
  tft.setCursor(25, 120);
  tft.println(ipStr);
  delay(2000);

  // ----------------------------------------------------------------
  // WEB SERVER ROUTE DEFINITIONS (Single Initialization Block)
  // ----------------------------------------------------------------

  // 1. Web Console Dashboard
  server.on("/", HTTP_GET, [](AsyncWebServerRequest* request) {
    String ipStr = WiFi.localIP().toString();
    int rssi = WiFi.RSSI();
    String macStr = WiFi.macAddress();

    String html = "<!DOCTYPE html><html><head><title>Machine Safety Console</title>";
    html += "<meta name='viewport' content='width=device-width, initial-scale=1'>";
    html += "<style>body{font-family:Arial;margin:20px;max-width:500px;} ";
    html += "input[type=text]{width:100%;padding:8px;margin:8px 0;box-sizing:border-box;} ";
    html += "input[type=submit]{background:#008CBA;color:white;padding:10px;border:none;width:100%;cursor:pointer;} ";
    html += ".card{background:#f2f2f2;padding:20px;border-radius:8px;margin-bottom:15px;}</style></head><body>";

    html += "<h2>Safety System Console</h2>";

    // Status Card
    html += "<div class='card'>";
    html += "<h3>Network Information</h3>";
    html += "<p><strong>IP Address:</strong> " + ipStr + "</p>";
    html += "<p><strong>Signal Strength (RSSI):</strong> " + String(rssi) + " dBm</p>";
    html += "<p><strong>MAC Address:</strong> " + macStr + "</p>";
    html += "</div>";

    // Form Card
    html += "<div class='card'>";
    html += "<h3>Machine Configuration</h3>";
    html += "<form action='/settings' method='POST'>";
    html += "<label>Scanner ID / Machine Number:</label>";
    html += "<input type='text' name='scanner' value='" + Scanner + "'>";
    html += "<label>Machine Display Name:</label>";
    html += "<input type='text' name='machine_name' value='" + machine_name + "'>";
    html += "<input type='submit' value='Save Settings'>";
    html += "</form></div>";

    html += "<p><a href='/update'>Go to Firmware Update (OTA)</a></p>";
    html += "</body></html>";

    request->send(200, "text/html", html);
  });

  // 2. Settings Save Handler
  server.on("/settings", HTTP_POST, [](AsyncWebServerRequest* request) {
    if (request->hasParam("scanner", true)) {
      Scanner = request->getParam("scanner", true)->value();
    }
    if (request->hasParam("machine_name", true)) {
      machine_name = request->getParam("machine_name", true)->value();
    }

    saveConfig();  // Persist changes to LittleFS

    request->send(200, "text/html", "<h3>Settings Saved Successfully!</h3><p><a href='/'>Back to Console</a></p>");
  });

  // Start Server & OTA
  ElegantOTA.begin(&server);
  server.begin();
  Serial.println("Web Console & OTA Server Started!");

  // ----------------------------------------------------------------

  for (byte i = 0; i < 6; i++) {
    key.keyByte[i] = 0xFF;
  }

  if (!master_key_overide) {
    check_in_to_keep_WiFi();
    display_scan_RFID();
  } else {
    display_communication_problem();
    delay(2000);
    display_scan_Master_Key();
  }

  Serial.println("Setup Complete\nPlease Scan Your Card");
  updating = false;
}

boolean RFID_Initialised = false;

void loop() {
  ElegantOTA.loop();

  if (!RFID_Initialised) {
    rfid.PCD_Init();
    RFID_Initialised = true;
  }

  // Check for incoming Serial RFID commands from Raspberry Pi
  check_serial_input();

  unsigned long currentMillis = millis();

  if (currentMillis - previousMillis >= interval) {
    previousMillis = currentMillis;
    check_in_to_keep_WiFi();
  }

  if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) {
    return;
  }

  Serial.println("\n UID tag :");
  String content = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    Serial.print(rfid.uid.uidByte[i] < 0x10 ? " 0" : " ");
    Serial.print(rfid.uid.uidByte[i], HEX);
    content.concat(String(rfid.uid.uidByte[i] < 0x10 ? " 0" : " "));
    content.concat(String(rfid.uid.uidByte[i], HEX));
  }
  content.toUpperCase();
  Serial.println();
  User_Key_Value = content;
  User_Key_Value.replace(" ", "");

  Serial.println(User_Key_Value);

  previousMillis = currentMillis;

  if (!master_key_overide) {
    check_with_server();
  } else {
    check_master_key();
    Serial.println("Returned from master key fun");
  }
  digitalWrite(Cycle_Start_PIN, HIGH);

  if (!master_key_overide) {
    display_scan_RFID();
  } else {
    display_scan_Master_Key();
  }
}

void bleep(int freq, int length) {
  tone(buzzPin, freq);
  delay(length);
  noTone(buzzPin);
}

void display_scan_RFID() {
  tft.fillScreen(BLUE);
  tft.setTextColor(WHITE);
  tft.setCursor(10, 26);
  tft.println("Please, tap your tag");
  tft.drawBitmap(40, 49, Scan, 120, 82, 0xffff);
  bleep(2000, 100);
}

void display_ppe() {
  tft.fillScreen(WHITE);
  tft.fillRect(30, 20, 100, 100, BLUE);
  tft.drawBitmap(30, 20, eyeprot, 100, 100, 0xffff);
  tft.setTextColor(BLACK);
  tft.setCursor(20, 15);
  tft.println("Please, take care");

  bleep(3000, 100);
  bleep(4000, 100);
  bleep(2000, 100);
}

void display_tidy_up() {
  Serial.println(F("Tidy up"));
  tft.fillScreen(BLUE);
  tft.setTextColor(WHITE);
  tft.setCursor(20, 20);
  tft.println("Please, tidy up!");
  tft.drawBitmap(40, 30, vacuum, 100, 101, 0xffff);
}

void display_no_entry() {
  tft.fillScreen(RED);
  tft.fillCircle(80, 64, 50, WHITE);
  tft.fillCircle(80, 64, 48, RED);
  tft.fillRoundRect(40, 55, 81, 20, 2, WHITE);
  bleep(100, 200);
}

void display_communication_problem() {
  tft.fillScreen(WHITE);
  tft.fillRect(30, 20, 100, 102, RED);
  tft.drawBitmap(30, 20, wifi_fault, 100, 102, 0xffff);
  tft.setTextColor(BLACK);
  tft.setCursor(24, 16);
  tft.println("Master Overide");
  bleep(100, 200);
}

// Perform POST check-in via HTTPS
void check_in_to_keep_WiFi() {
  Serial.println("Checking in with server...");

  if (WiFiMulti.run() == WL_CONNECTED) {
    WiFiClientSecure client;
    client.setInsecure();  // Skip standard SSL certificate verification

    HTTPClient http;
    if (http.begin(client, rfid_endpoint)) {
      http.addHeader("Content-Type", "application/x-www-form-urlencoded");

      String postData = "action=checkin&Scanner=" + Scanner + "&IP=" + WiFi.localIP().toString() + "&RSSI=" + String(WiFi.RSSI());

      int httpCode = http.POST(postData);

      if (httpCode > 0) {
        Serial.printf("[HTTPS] POST... code: %d\n", httpCode);
        if (httpCode == HTTP_CODE_OK || httpCode == HTTP_CODE_MOVED_PERMANENTLY) {
          Serial.println("Server communication OK");
        }
      } else {
        Serial.printf("[HTTPS] POST... failed, error: %s\n", http.errorToString(httpCode).c_str());
        master_key_overide = true;
        display_communication_problem();
      }
      http.end();
    } else {
      Serial.println("[HTTPS] Unable to connect");
      master_key_overide = true;
      display_communication_problem();
    }
  }
}


// Perform authorization check via POST over HTTPS
void check_with_server(bool is_pi_source) {
  String payload = "";

  if (WiFiMulti.run() == WL_CONNECTED) {
    WiFiClientSecure client;
    client.setInsecure();

    HTTPClient http;
    if (http.begin(client, rfid_endpoint)) {
      http.addHeader("Content-Type", "application/x-www-form-urlencoded");

      // Include a flag telling rfid.php whether to swap bytes or not
      String postData = "UID=" + User_Key_Value + 
                        "&Scanner=" + Scanner + 
                        "&raw=" + String(is_pi_source ? "1" : "0");
                        
      int httpCode = http.POST(postData);

      if (httpCode > 0) {
        Serial.printf("[HTTPS] POST... code: %d\n", httpCode);
        if (httpCode == HTTP_CODE_OK || httpCode == HTTP_CODE_MOVED_PERMANENTLY) {
          payload = http.getString();
          Serial.println(payload);
        }
      } else {
        Serial.printf("[HTTPS] POST... failed, error: %s\n", http.errorToString(httpCode).c_str());
        display_communication_problem();
      }
      http.end(); // Cleanly close connection
    } else {
      Serial.println("[HTTPS] Unable to connect");
      display_communication_problem();
    }
  }

  // Process payload
  if (payload.length() > 0) {
    What_shall_we_do_with_the(payload);
  }
}


void What_shall_we_do_with_the(String payload) {
  if (payload == "Not permitted") {
    display_no_entry();
    delay(1000);
    return;
  }

  if (payload.indexOf("Authorised") != -1) {
    int start_of_token = payload.indexOf("[") + 1;
    int end_of_token = payload.indexOf("]");

    String token = payload.substring(start_of_token, end_of_token);
    Serial.println("\nThe token is: " + token);

    display_ppe();
    start_machinery();

    if (server_acknowledged("Complete", token)) {
      Serial.println("Server Ack");
    }
  } else if (payload == "MakeMaster") {
    Serial.println("Make this a master key");
    make_master_key();
    RFID_Initialised = false;
  } else {
    display_no_entry();
    delay(1000);
  }
}

// Send operation status updates back to backend using POST
boolean server_acknowledged(String message, String data) {
  if (WiFiMulti.run() == WL_CONNECTED) {
    WiFiClientSecure client;
    client.setInsecure();     // Skip standard SSL certificate verification
    client.setTimeout(5000);  // Set a generous connection timeout (5 seconds)

    HTTPClient http;
    // Explicitly configure HTTPClient to manage connection state cleanly
    http.setTimeout(5000);

    if (http.begin(client, rfid_endpoint)) {
      http.addHeader("Content-Type", "application/x-www-form-urlencoded");
      http.addHeader("Connection", "close");  // Force server to close socket after response

      String postData = "action=acknowledge&Scanner=" + Scanner + "&UID=" + User_Key_Value + "&Message=" + message + "&Data=" + data;

      int httpCode = http.POST(postData);

      if (httpCode > 0) {
        Serial.printf("[HTTPS] POST... code: %d\n", httpCode);
        if (httpCode == HTTP_CODE_OK || httpCode == HTTP_CODE_MOVED_PERMANENTLY) {
          String payload = http.getString();
          Serial.println(payload);
          http.end();
          return true;
        } else {
          http.end();
          return false;
        }
      } else {
        Serial.printf("[HTTPS] POST... failed, error: %s\n", http.errorToString(httpCode).c_str());
        http.end();
        return false;
      }
    } else {
      Serial.println("[HTTPS] Unable to connect");
      return false;
    }
  }

  Serial.println("[HTTPS] WiFi not connected");
  return false;
}

void start_machinery() {
  Serial.println("Pulling Cycle Start Pin LOW");
  digitalWrite(Cycle_Start_PIN, LOW);
  delay(5000);

  Serial.println("Pulling Cycle Start Pin HIGH");
  digitalWrite(Cycle_Start_PIN, HIGH);

  cycle_in_progress = true;

  while (cycle_in_progress) {
    int val = digitalRead(Cycle_in_progress_PIN);
    if (val == 1) {
      Serial.println("Cycle complete line = " + String(val));
      cycle_in_progress = false;
    }
    yield();
  }

  display_tidy_up();
  delay(5000);
}

void display_card_writing() {
  tft.fillScreen(CYAN);
  tft.fillCircle(80, 64, 50, WHITE);
  tft.fillCircle(80, 64, 48, RED);
  tft.fillRoundRect(40, 55, 81, 20, 2, WHITE);
  bleep(200, 50);
}

// Load settings from flash memory on startup safely
void loadConfig() {
  if (!LittleFS.begin()) {
    Serial.println("Formatting LittleFS filesystem...");
    LittleFS.format();
    LittleFS.begin();
  }

  if (LittleFS.exists("/config.txt")) {
    File file = LittleFS.open("/config.txt", "r");
    if (file) {
      Scanner = file.readStringUntil('\n');
      Scanner.trim();
      machine_name = file.readStringUntil('\n');
      machine_name.trim();
      file.close();
      Serial.println("Config loaded from flash!");
    }
  } else {
    Serial.println("No config file found. Using default values.");
    saveConfig();  // Save default values on first boot
  }
}

// Save settings back to flash memory
void saveConfig() {
  File file = LittleFS.open("/config.txt", "w");
  if (file) {
    file.println(Scanner);
    file.println(machine_name);
    file.close();
    Serial.println("Config saved to flash!");
  }
}

// Adjustable Cooldown in milliseconds (e.g., 3000ms = 3 seconds pause between reads)
const unsigned long SERIAL_COOLDOWN_MS = 3000; 
unsigned long lastPiReadTime = 0;

void check_serial_input() {
  if (Serial.available() > 0) {
    String serialMsg = Serial.readStringUntil('\n');
    serialMsg.trim(); // Clean up trailing \r or spaces

    // 1. Check if we are still in the cooldown window
    if (millis() - lastPiReadTime < SERIAL_COOLDOWN_MS) {
      // Ignore this message because it arrived too quickly after the last one
      return; 
    }

    // Look for the "RFID=" substring
    int rfidIndex = serialMsg.indexOf("RFID=");
    
    if (rfidIndex != -1) {
      // Extract everything after "RFID="
      String pi_uid = serialMsg.substring(rfidIndex + 5); 
      pi_uid.trim();
      pi_uid.toUpperCase();

      if (pi_uid.length() > 0) {
        Serial.println("\n[Serial API] Parsed RFID from Pi: " + pi_uid);
        User_Key_Value = pi_uid;

        previousMillis = millis(); // Refresh activity timer
        lastPiReadTime = millis(); // Update cooldown timer!

        if (!master_key_overide) {
          check_with_server(true); // Takes ~1 second to complete
        } else {
          check_master_key();
        }

        digitalWrite(Cycle_Start_PIN, HIGH);

        // Reset UI display
        if (!master_key_overide) {
          display_scan_RFID();
        } else {
          display_scan_Master_Key();
        }

        // 2. CLEAR THE BACKLOG: Flush any messages that queued up during HTTP request
        while (Serial.available() > 0) {
          Serial.read(); // Read and discard stale data
        }
      }
    }
  }
}
