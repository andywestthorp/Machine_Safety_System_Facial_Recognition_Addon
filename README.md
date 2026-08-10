# DTFace — Facial Recognition & Enrollment System

A dual-mode Raspberry Pi & Flask facial recognition system designed for real-time verification and web-based enrollment. It uses 128-dimensional face embedding vectors cached locally for high-speed matching, integrates with a backend MySQL/PHP database, and communicates via USB Serial with external hardware (ESP8266/ESP32).

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
