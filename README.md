# DTFace — Facial Recognition & Enrollment System

A dual-mode Raspberry Pi & Flask facial recognition system designed for real-time verification and web-based enrollment. It uses 128-dimensional face embedding vectors cached locally for high-speed matching, integrates with a backend MySQL/PHP database, and communicates via USB Serial with external hardware (ESP8266/ESP32).

To help explain things, please take a look at the following Youtube videos:

* **New feature**: (https://www.youtube.com/watch?v=8xTHW9tI40U) — Proof of concept
* **Existing system in workshop**: (https://www.youtube.com/watch?v=OMUBlsAB1YI) — The current RFID system.
* **Management console**: (https://www.youtube.com/watch?v=gfuSRVSx0mU) — The simple management console.



## 🏗️ Architecture Overview

```text
 [ ESP32-S3-CAM ]  --(HTTP POST JPEG)-->  [ Flask Server (Port 5000) ]  --(JSON Vector)-->  [ PHP / MySQL Database ]
 (Display + Ring)                        (face_recognition / dlib)                         (face_vectors.php)

```

1. **ESP32-S3-CAM:** Captures frame via camera feed, displays live UI on GC9A01 screen, and triggers light ring flash on snapshot button press.
2. **Flask Processing Engine:** Handles face detection, extracts 128-D face encodings, and matches faces against an in-memory memory cache.
3. **Web Dashboard:** Served directly by Flask. Allows admins to search members, activate target **Enrollment Mode**, or delete facial vectors.
4. **PHP API / Database:** Acts as the persistent backend store for member profiles and 128-D vector arrays.

---

## 🛠️ Hardware Requirements

* **Board:** GOOUUU ESP32-S3-CAM
* **Display:** GC9A01 240x240 Round LCD (SPI interface)
* **Lighting:** 24-LED WS2812B NeoPixel Ring Light
* **Trigger:** Momentary Push Button

### Pin Mapping

| Component | Function | ESP32-S3 GPIO |
| --- | --- | --- |
| **Snap Button** | Input (Pull-Up) | `GPIO 2` |
| **NeoPixel Ring** | D-In | `GPIO 1` |
| **GC9A01 Display** | SCLK | `GPIO 48` |
|  | MOSI (SDA) | `GPIO 47` |
|  | DC | `GPIO 21` |
|  | CS | `GPIO 45` |
|  | RST | `GPIO 19` |
| **Serial Comms** | TX | Connect to RX of ESP8266 |
|  | RX | Connect to TX of ESP8266 |
|  | GND | Connect to GND of ESP8266 |


> ⚠️ **Note:** Ensure the button is wired between `GPIO 2` and `GND`. Also make sure that you can disconnect the two ESP devices (I used an RJ11 cable and two RJ11 sockets).

---

## 💻 Software Prerequisites

### 1. Python Server Environment

* Python 3.8+
* `face_recognition` (`dlib`)
* `OpenCV` (`opencv-python`)
* `Flask`
* `requests`
* `numpy`

### 2. ESP32 Arduino Dependencies

* **Libraries:** `LovyanGFX`, `Adafruit_NeoPixel`, `ArduinoJson`, `HTTPClient`, `WiFi`
* **Board Package:** ESP32 by Espressif Systems (v2.x or v3.x)

---

## 🚀 Getting Started

### 1. Configure and Run the Flask Server

1. Install required dependencies:
```bash
pip install flask opencv-python face_recognition numpy requests

```


2. Update `API_URL` inside `app.py` to point to your PHP backend endpoint.
3. Start the Flask application:
```bash
python app.py

```


4. Access the web dashboard by navigating to `http://<YOUR_SERVER_IP>:5000/`.

### 2. Flash the ESP32-S3

1. Open `ESP32-S3-Cam-Screen.ino` in Arduino IDE.
2. Update Wi-Fi and Server credentials:
```cpp
const char* WIFI_SSID  = "YOUR_WIFI_NAME";      
const char* WIFI_PASS  = "YOUR_WIFI_PASSWORD";  
const char* SERVER_URL = "http://<YOUR_SERVER_IP>:5000/upload";

```


3. Set tools configuration in Arduino IDE:
* **Board:** `ESP32S3 Dev Module`
* **PSRAM:** `OPI PSRAM`
* **Partition Scheme:** `Huge APP (3MB No OTA/1MB SPIFFS)`


4. Upload the code to your ESP32-S3.

---

## 📖 User Workflow

### A. Verification Mode (Default)

1. Point the camera at a person.
2. Press the **Snap Button**.
3. The NeoPixel ring flashes warm white for exposure.
4. The server runs facial recognition against cached encodings:
* 🟢 **Match:** Display shows green screen with Name & RFID + Green LED Ring.
* 🔴 **No Match:** Display shows red screen + Red LED Ring.



### B. Enrolling a Person

1. Open `http://<SERVER_IP>:5000/` on a web browser.
2. Search for a name/surname in the filtered search bar.
3. Click **Enroll**. The web banner switches to active **Enrollment Mode**.
4. Direct the target person to face the ESP32-S3 camera and press the **Snap Button**.
5. The face vector is generated, submitted to the PHP API, and added instantly to the active server cache.

### C. Deleting a Profile Vector

1. Search for an enrolled user on the web dashboard.
2. Click **Delete**.
3. Confirm prompt to clear the vector from the database and invalidate local server cache.

---

## 🔒 Security & Performance Notes

* **Vector Match Tolerance:** `DISTANCE_THRESHOLD` is set to `0.55` in `app.py` for optimal balance between accuracy and false positives.
* **Camera Optimization:** Mirroring (`hmirror`) and vertical flipping (`vflip`) are active to present a natural mirror-like UI experience on the GC9A01 display.

