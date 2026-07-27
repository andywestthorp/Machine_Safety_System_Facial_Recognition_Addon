import json
import os
import time
import cv2
import face_recognition
import numpy as np
import requests
import serial
import sys

# 1. Suppress Qt/Wayland logging noise
os.environ["QT_LOGGING_RULES"] = "qt.qpa.fonts=false;*.warning=false"
os.environ["QT_QPA_PLATFORM"] = "xcb"

# 2. Auto-create missing OpenCV Qt font directory if running in venv
cv2_qt_fonts = os.path.join(
    sys.prefix, "lib", f"python{sys.version_info.major}.{sys.version_info.minor}", "site-packages", "cv2", "qt", "fonts"
)
os.makedirs(cv2_qt_fonts, exist_ok=True)

# Namecheap PHP API Endpoint
API_URL = "https://enrichment.longridgetowers.com/dt/face_vectors.php"

# Serial Port Configuration
SERIAL_PORT = "/dev/ttyUSB0"  # Change to /dev/ttyACM0 if needed
BAUD_RATE = 115200


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


def main():
    known_encodings, known_names, known_rfids = fetch_known_faces()
    ser = init_serial()

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
            # Downscale frame to 1/4 size
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
        # Render Results directly onto the Video Frame
        # -----------------------------------------------------------------
        for (top, right, bottom, left), (name, rfid) in zip(
            face_locations, face_names
        ):
            # Scale face locations back up by 4 since the frame was processed at 1/4 size
            top *= 4
            right *= 4
            bottom *= 4
            left *= 4

            # Set color: Green for known profiles, Red for Unknown
            box_color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)

            # Draw bounding box around the face
            cv2.rectangle(frame, (left, top), (right, bottom), box_color, 2)

            # Draw label banner at the bottom of the box
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

        # Show frame in GUI Window
        cv2.imshow("Pi Scanner", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    video_capture.release()
    cv2.destroyAllWindows()
    if ser and ser.is_open:
        ser.close()


if __name__ == "__main__":
    main()
