import json
import os
import sys
import time

# -----------------------------------------------------------------
# 1. Environment & Logging Clean-up (Suppresses Qt/Font warnings)
# -----------------------------------------------------------------
os.environ["QT_LOGGING_RULES"] = "qt.qpa.fonts=false;*.warning=false"
os.environ["QT_QPA_PLATFORM"] = "xcb"

# Auto-create missing OpenCV Qt font directory if in virtualenv to stop Qt complaints
cv2_qt_fonts = os.path.join(
    sys.prefix,
    "lib",
    f"python{sys.version_info.major}.{sys.version_info.minor}",
    "site-packages",
    "cv2",
    "qt",
    "fonts",
)
os.makedirs(cv2_qt_fonts, exist_ok=True)

import cv2
import face_recognition
import numpy as np
import requests
import serial

# Configuration
API_URL = ""
SERIAL_PORT = "/dev/ttyUSB0"  # Change to /dev/ttyACM0 if needed
BAUD_RATE = 115200

# TFT Display Configuration
TFT_FB_DEVICE = "/dev/fb1"  # Default framebuffer for 3.5" SPI TFT screens
TFT_WIDTH = 480  # Common 3.5" TFT width
TFT_HEIGHT = 320  # Common 3.5" TFT height


def init_serial():
    """Attempt to open USB serial connection to ESP8266."""
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        time.sleep(2)  # Wait for ESP8266 to reset
        print(f" Connected to ESP8266 on {SERIAL_PORT}")
        return ser
    except Exception as e:
        print(f"⚠️ Warning: Could not open serial port {SERIAL_PORT}: {e}")
        print("Continuing without Serial output...")
        return None


def fetch_known_faces():
    """Fetch vectors, names, and RFIDs from server via HTTPS API."""
    print("Fetching enrolled face vectors from server...")
    known_encodings = []
    known_names = []
    known_rfids = []

    try:
        response = requests.get(API_URL, timeout=10)

        if response.status_code != 200:
            print(
                f"❌ Server returned HTTP status {response.status_code}: {response.text}"
            )
            return [], [], []

        data = response.json()

        for row in data:
            if "face_vector" in row and row["face_vector"]:
                vector_data = json.loads(row["face_vector"])
                encoding = np.array(vector_data, dtype=np.float64)
                if len(encoding) == 128:
                    known_encodings.append(encoding)
                    known_names.append(f"{row['Forename']} {row['Surname']}")
                    rfid_code = row.get("RFID") or "UNKNOWN"
                    known_rfids.append(rfid_code)

        print(
            f"Successfully cached {len(known_encodings)} profiles into local RAM."
        )
    except Exception as e:
        print(f"Error fetching vectors: {e}")

    return known_encodings, known_names, known_rfids


def render_to_tft(frame, fb_device=TFT_FB_DEVICE):
    """Resize image and write raw bytes directly to TFT framebuffer."""
    try:
        # Resize to fit 3.5" screen dimensions
        resized = cv2.resize(frame, (TFT_WIDTH, TFT_HEIGHT))

        # Convert OpenCV BGR format to BGR565 (16-bit color format used by Linux Framebuffers)
        bgr565_frame = cv2.cvtColor(resized, cv2.COLOR_BGR2BGR565)

        # Write to screen device file
        with open(fb_device, "wb") as fb:
            fb.write(bgr565_frame.tobytes())
    except Exception as e:
        pass  # Ignore framebuffer write errors if device is busy or unreadable


def main():
    known_encodings, known_names, known_rfids = fetch_known_faces()
    ser = init_serial()

    # Check if 3.5" TFT Framebuffer is present
    has_tft = os.path.exists(TFT_FB_DEVICE)
    if has_tft:
        print(f" 3.5 TFT Screen detected on {TFT_FB_DEVICE} (Headless Mode)")
    else:
        print(" No TFT framebuffer detected. Defaulting to Desktop GUI window.")

    video_capture = cv2.VideoCapture(0)
    video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    process_this_frame = True
    face_locations = []
    face_names = []

    last_sent_rfid = None
    last_sent_time = 0
    COOLDOWN_SECONDS = 3.0

    while True:
        ret, frame = video_capture.read()
        if not ret:
            break

        if process_this_frame:
            # Downscale frame to 1/4 size for fast processing on Raspberry Pi CPU
            small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
            rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

            face_locations = face_recognition.face_locations(
                rgb_small_frame, number_of_times_to_upsample=1, model="hog"
            )
            face_encodings = face_recognition.face_encodings(
                rgb_small_frame, face_locations
            )

            face_names = []
            for face_encoding in face_encodings:
                face_distances = face_recognition.face_distance(
                    known_encodings, face_encoding
                )

                name = "Unknown"
                rfid = "N/A"

                if len(face_distances) > 0:
                    best_match_index = np.argmin(face_distances)
                    distance = face_distances[best_match_index]

                    if distance < 0.55:
                        name = known_names[best_match_index]
                        rfid = known_rfids[best_match_index]
                        current_time = time.time()

                        print(
                            f" Match Found: {name} | RFID: {rfid} (Distance: {distance:.3f})"
                        )

                        # Trigger USB Serial transmit
                        if (
                            rfid != last_sent_rfid
                            or (current_time - last_sent_time) > COOLDOWN_SECONDS
                        ):
                            message = f"Face Recognised, RFID= {rfid}\n"
                            if ser and ser.is_open:
                                ser.write(message.encode("utf-8"))
                                print(f" Sent to ESP8266: {message.strip()}")

                            last_sent_rfid = rfid
                            last_sent_time = current_time

                face_names.append((name, rfid))

        process_this_frame = not process_this_frame

        # -----------------------------------------------------------------
        # Render Bounding Boxes and Labels onto Video Frame
        # -----------------------------------------------------------------
        for (top, right, bottom, left), (name, rfid) in zip(
            face_locations, face_names
        ):
            # Scale coordinates back up by 4x
            top *= 4
            right *= 4
            bottom *= 4
            left *= 4

            box_color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)

            # Draw face box
            cv2.rectangle(frame, (left, top), (right, bottom), box_color, 2)

            # Draw banner & text label
            label_text = f"{name} (RFID: {rfid})" if rfid != "N/A" else name
            cv2.rectangle(
                frame,
                (left, bottom - 35),
                (right, bottom),
                box_color,
                cv2.FILLED,
            )
            cv2.putText(
                frame,
                label_text,
                (left + 6, bottom - 10),
                cv2.FONT_HERSHEY_DUPLEX,
                0.5,
                (255, 255, 255),
                1,
            )

        # -----------------------------------------------------------------
        # Output Video Stream (TFT Framebuffer OR Desktop Window)
        # -----------------------------------------------------------------
        if has_tft:
            render_to_tft(frame)
        else:
            cv2.imshow("Pi Scanner", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    video_capture.release()
    cv2.destroyAllWindows()
    if ser and ser.is_open:
        ser.close()


if __name__ == "__main__":
    main()
