import json
import math
import cv2
import face_recognition
import mysql.connector
import numpy as np

# ---------------------------------------------------------
# 1. Database Connection & Fetch Enrolled Vectors
# ---------------------------------------------------------
DB_CONFIG = {
    "host": "localhost",
    "user": "YOUR_DB_USER",  # Replace with your DB user
    "password": "YOUR_DB_PASSWORD",  # Replace with your DB password
    "database": "longtwla_Standard_Information",
}


def load_known_faces():
    """Fetches all pupils with enrolled face vectors from MySQL."""
    known_encodings = []
    known_names = []

    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # Select pupils who have face vectors
        query = """
            SELECT PupilID, Forename, Surname, Year_Group, House, face_vector 
            FROM Pupils 
            WHERE has_vector = 1 AND face_vector IS NOT NULL AND face_vector != ''
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        for row in rows:
            try:
                # Parse JSON array string back into Python list/numpy array
                vector_data = json.loads(row["face_vector"])
                encoding = np.array(vector_data, dtype=np.float64)

                if len(encoding) == 128:
                    known_encodings.append(encoding)
                    name_label = f"{row['Forename']} {row['Surname']} ({row['Year_Group']})"
                    known_names.append(name_label)
            except Exception as parse_err:
                print(
                    f"Skipping Pupil ID {row['PupilID']} due to invalid vector format: {parse_err}"
                )

        cursor.close()
        conn.close()
        print(f"Successfully loaded {len(known_encodings)} pupil face profiles.")

    except mysql.connector.Error as err:
        print(f"Database error: {err}")

    return known_encodings, known_names


# ---------------------------------------------------------
# 2. Main Video Recognition Loop
# ---------------------------------------------------------
def main():
    known_encodings, known_names = load_known_faces()

    if not known_encodings:
        print(
            "No valid face vectors found in database. Please enroll pupils first."
        )
        return

    # Open Webcam (0 is default camera)
    video_capture = cv2.VideoCapture(0)

    if not video_capture.isOpened():
        print("Error: Could not open camera.")
        return

    print("\nStarting camera recognition. Press 'q' to quit...\n")

    # Frame skipping toggle to optimize FPS
    process_this_frame = True

    face_locations = []
    face_encodings = []
    face_names = []

    while True:
        ret, frame = video_capture.read()
        if not ret:
            break

        # Scale down video frame to 1/4 size for faster face recognition processing
        small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)

        # Convert BGR (OpenCV) to RGB (face_recognition)
        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

        if process_this_frame:
            # Detect face locations and compute 128-d encodings for faces in frame
            face_locations = face_recognition.face_locations(rgb_small_frame)
            face_encodings = face_recognition.face_encodings(
                rgb_small_frame, face_locations
            )

            face_names = []
            for face_encoding in face_encodings:
                # Compare live face against all database encodings (Tolerance = 0.55 for strictness)
                matches = face_recognition.compare_faces(
                    known_encodings, face_encoding, tolerance=0.55
                )
                name = "Unknown"

                # Calculate Euclidean distances
                face_distances = face_recognition.face_distance(
                    known_encodings, face_encoding
                )
                if len(face_distances) > 0:
                    best_match_index = np.argmin(face_distances)
                    if matches[best_match_index]:
                        name = known_names[best_match_index]

                face_names.append(name)

        process_this_frame = not process_this_frame

        # Draw bounding boxes and labels on screen
        for (top, right, bottom, left), name in zip(
            face_locations, face_names
        ):
            # Scale face locations back up to original frame size (4x)
            top *= 4
            right *= 4
            bottom *= 4
            left *= 4

            # Set box color: Green for recognized, Red for unknown
            color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)

            # Draw box around face
            cv2.rectangle(frame, (left, top), (right, bottom), color, 2)

            # Draw label banner
            cv2.rectangle(
                frame,
                (left, bottom - 35),
                (right, bottom),
                color,
                cv2.FILLED,
            )
            cv2.putText(
                frame,
                name,
                (left + 6, bottom - 8),
                cv2.FONT_HERSHEY_DUPLEX,
                0.7,
                (255, 255, 255),
                1,
            )

        # Display output feed
        cv2.imshow("Pupil Face Verification", frame)

        # Press 'q' on keyboard to exit
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    video_capture.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
