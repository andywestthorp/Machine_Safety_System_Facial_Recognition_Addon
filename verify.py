import json
import os

# Suppress OpenCV/Qt window warnings
os.environ["QT_QPA_PLATFORM"] = "xcb"
os.environ["QT_LOGGING_RULES"] = "*=false"

import cv2
import face_recognition
import mysql.connector
import numpy as np

# Database Config (adjust host/port as needed for SSH/MySQL)
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5522,  # Uses the forwarded local port
    "user": "",  # Replace with your DB user
    "password": "",  # Replace with your DB password
    "database": "",
}


def load_known_faces():
    known_encodings = []
    known_names = []
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        query = "SELECT ID, Forename, Surname, Year_Group, face_vector FROM Pupils WHERE has_vector = 1 AND face_vector IS NOT NULL"
        cursor.execute(query)
        for row in cursor.fetchall():
            try:
                vector_data = json.loads(row["face_vector"])
                encoding = np.array(vector_data, dtype=np.float64)
                if len(encoding) == 128:
                    known_encodings.append(encoding)
                    known_names.append(
                        f"{row['Forename']} {row['Surname']}"
                    )
            except Exception as e:
                pass
        cursor.close()
        conn.close()
    except Exception as err:
        print(f"Database error: {err}")
    return known_encodings, known_names


def main():
    known_encodings, known_names = load_known_faces()
    print(f"Loaded {len(known_encodings)} face vector profiles.")

    video_capture = cv2.VideoCapture(0)
    process_this_frame = True

    face_locations = []
    face_encodings = []
    face_names = []

    while True:
        ret, frame = video_capture.read()
        if not ret:
            break

        # Fast 1/4 size frame scaling
        small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

        if process_this_frame:
            # Use fast HOG model with 1 upsample pass
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

                if len(face_distances) > 0:
                    best_match_index = np.argmin(face_distances)
                    distance = face_distances[best_match_index]

                    # Print real-time Euclidean distance to console
                    print(f"Live Distance: {distance:.3f}")

                    # Lenient threshold (0.50) to compensate for shadow/lighting variations
                    if distance < 0.50:
                        
                        name = known_names[best_match_index]
                        print(name)
                    else:
                        name = "Unknown"

                face_names.append(name)

        process_this_frame = not process_this_frame

        # Render Bounding Boxes (Scale x4 back to original size)
        for (top, right, bottom, left), name in zip(
            face_locations, face_names
        ):
            top *= 4
            right *= 4
            bottom *= 4
            left *= 4
            color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)

            cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
            cv2.rectangle(
                frame,
                (left, bottom - 30),
                (right, bottom),
                color,
                cv2.FILLED,
            )
            cv2.putText(
                frame,
                name,
                (left + 6, bottom - 6),
                cv2.FONT_HERSHEY_DUPLEX,
                0.6,
                (255, 255, 255),
                1,
            )

        cv2.imshow("Pupil Verification", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    video_capture.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
