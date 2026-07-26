import json
import time
import cv2
import face_recognition
import numpy as np
import requests

# Namecheap PHP API Endpoint
API_URL = "https:{The API}"


def fetch_known_faces():
    """Fetch vectors from Namecheap via HTTPS API."""
    print("Fetching enrolled face vectors from server...")
    known_encodings = []
    known_names = []

    try:
        response = requests.get(API_URL, timeout=10)
        data = response.json()

        for row in data:
            if "face_vector" in row and row["face_vector"]:
                vector_data = json.loads(row["face_vector"])
                encoding = np.array(vector_data, dtype=np.float64)
                if len(encoding) == 128:
                    known_encodings.append(encoding)
                    known_names.append(f"{row['Forename']} {row['Surname']}")

        print(
            f"Successfully cached {len(known_encodings)} profiles into local RAM."
        )
    except Exception as e:
        print(f"Error fetching vectors from API: {e}")

    return known_encodings, known_names


def main():
    known_encodings, known_names = fetch_known_faces()

    # Open USB Webcam or PiCam
    video_capture = cv2.VideoCapture(0)

    # Set lower resolution on Pi camera stream for max speed
    video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    process_this_frame = True

    while True:
        ret, frame = video_capture.read()
        if not ret:
            break

        if process_this_frame:
            # Downscale frame to 1/4 size for the Pi 4 CPU
            small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
            rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

            # Fast HOG detection
            face_locations = face_recognition.face_locations(
                rgb_small_frame, number_of_times_to_upsample=1, model="hog"
            )
            face_encodings = face_recognition.face_encodings(
                rgb_small_frame, face_locations
            )

            for face_encoding in face_encodings:
                face_distances = face_recognition.face_distance(
                    known_encodings, face_encoding
                )

                if len(face_distances) > 0:
                    best_match_index = np.argmin(face_distances)
                    distance = face_distances[best_match_index]

                    if distance < 0.55:
                        name = known_names[best_match_index]
                        print(
                            f" Match Found: {name} (Distance: {distance:.3f})"
                        )
                        # Optionally trigger GPIO pin, relay, buzzer, or log attendance here!

        process_this_frame = not process_this_frame

        # Display window (if running desktop GUI)
        cv2.imshow("Pi Scanner", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    video_capture.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
