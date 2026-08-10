# DTFace — Facial Recognition & Enrollment System

A dual-mode Raspberry Pi & Flask facial recognition system designed for real-time verification and web-based enrollment. It uses 128-dimensional face embedding vectors cached locally for high-speed matching, integrates with a backend MySQL/PHP database, and communicates via USB Serial with external hardware (ESP8266/ESP32).

To help explain things, please take a look at the following Youtube videos:

* **New feature**: (https://www.youtube.com/watch?v=8xTHW9tI40U) — Proof of concept
* **Existing system in workshop**: (https://www.youtube.com/watch?v=OMUBlsAB1YI) — The current RFID system.
* **Trigger Switch**: (https://www.youtube.com/watch?v=gfuSRVSx0mU) — The simple management console.

---

## Key Features

* **High-Speed Hardware Processing**: Captures frames natively via `picamera2` and renders them directly to a 3.5" SPI TFT framebuffer (`/dev/fb0` / `/dev/fb1`) without requiring a desktop GUI.
* **Dual-Mode Flask Application**: Supports both live verification matching and interactive face enrollment using an embedded web dashboard.
* **Offline RAM Caching**: Downloads 128-D vectors from a central API on startup and caches them locally in RAM for ultra-fast local matching.
* **Serial Hardware Integration**: Sends recognized RFID payload data over USB Serial (`/dev/ttyUSB0`) to an ESP8266/ESP32 to trigger the machinery relays.
* **Read-Only System Safeguard**: Configured to run on a Raspberry Pi Read-Only (RO) overlay filesystem to protect the SD card from power-cut corruption.

---

## Tech Stack & Dependencies

### Python Environment
* **Python**: 3.x (Virtual Environment)
* **Core Libraries**:
  * `face_recognition` (1.3.0) — Dlib-based 128-D facial vector generation
  * `opencv-python` (5.0.0.93) — Video frame manipulation and framebuffer rendering
  * `Flask` (3.1.3) — Enrollment web portal & upload handler
  * `picamera2` — Native Raspberry Pi camera module capture
  * `pyserial` (3.5) — Serial communication with ESP8266
  * `numpy` (2.5.2) — Vector operations
  * `requests` (2.34.2) — Remote API communication

### Backend Stack
* **Web Server**: Apache/Nginx with PHP (PDO extension)
* **Database**: MySQL / MariaDB (Tables for `Pupils`, `Staff`, and `RFID_Pupil`)

---

## System Architecture & Workflow

1. **Startup**: The Python application fetches all active face vectors from the remote endpoint (`https://enrichment.longridgetowers.com/dt/face_vectors.php`) and caches them into RAM[cite: 5, 6].
2. **Verification Mode**: Camera frames are captured, downscaled to 1/4 size for CPU optimization, and checked against cached vectors.
3. **Hardware Trigger**: Upon a match (distance $< 0.55$), the user's details are displayed on the local 3.5" screen, and an RFID payload (`Face Recognised, RFID= XXXXX\n`) is transmitted over Serial[cite: 4, 5].
4. **Enrollment Mode**: Administrators access the web dashboard (`http://<PI_IP>:5000/`) to search for an individual and trigger enrollment mode[cite: 5]. The next face captured is vectorized and saved to the database via a POST request[cite: 5, 6].

---

## Installation & Setup

### 1. Clone & Set Up Python Environment
```bash
git clone [https://github.com/your-username/DTFace.git](https://github.com/your-username/DTFace.git)
cd DTFace

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```
## Hardware

This project utilizes the **Goouuu-ESP32-S3-CAM** as its core controller, integrated with a camera, screen, status lighting, and custom 3D/CNC enclosure:

* **Microcontroller & Camera**: [Goouuu-ESP32-S3-CAM](https://github.com/zhuhai-esp/ESP32-S3-Goouuu-Cam/blob/main/Documents/ESP32-S3CAM%E5%8E%9F%E7%90%86%E5%9B%BE.pdf) — Core module driving image capture and system logic.
* **Display**: [Waveshare 1.28" Round LCD Module](https://www.waveshare.com/wiki/1.28inch_LCD_Module) — Displays a live preview so users can position themselves for recognition.
* **Trigger Switch**: [RUNCCI-YUN Waterproof Momentary Push Button](https://www.amazon.co.uk/RUNCCI-YUN-Waterproof-Momentary-momentary-Pre-soldered/dp/B0825RCZJS) — Physical trigger pressed to capture a photo and initiate the recognition process.
* **Lighting**: [24-LED WS2812B 5050 RGB Ring Light](https://www.amazon.co.uk/dp/B07DKJ6SFR/) — Surrounds the display to evenly illuminate subject faces for accurate detection.
* **Enclosure**: [OnShape CAD Model](https://cad.onshape.com/documents/e8091fb71c589a1951f0c958/w/28693c77fca783187902ff98/e/2a3cb1dce8734d894cc1e33f?renderMode=0&uiState=6a79f3552ffbc9994ff3b5aa) — Custom housing consisting of 3D-printed main body parts and a solid front disc CNC-routed from acrylic.

| Component | Component Pin / Function | ESP32-S3 GPIO | Notes / Protocol |
| :--- | :--- | :--- | :--- |
| **GC9A01 LCD Display** | SCLK / CLK | **GPIO 48** | SPI Clock |
| | MOSI / SDA / DIN | **GPIO 47** | SPI Data |
| | DC / RS | **GPIO 21** | Data / Command Selection |
| | CS | **GPIO 45** | Chip Select |
| | RES / RST | **GPIO 19** | Hardware Reset |
| **WS2812 Ring Light** | Data In (DI) | **GPIO 1** | 24-LED Neopixel Data Pin |
| **Trigger Switch** | Button Signal | **GPIO 2** | Active Low / Internal Pull-Up (`INPUT_PULLUP`) |
| **Serial Communications** | TX | **TX** | To **RX** on existing device |
| Note: Disconnect when uploading| RX | **RX** | To **TX** on existing device |




