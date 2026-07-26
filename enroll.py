import base64
import json
import cv2
import face_recognition
import mysql.connector
import numpy as np

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5522,  # Uses the forwarded local port
    "user": "",  # Replace with your DB user
    "password": "",  # Replace with your DB password
    "database": "",
}




def capture_and_enroll(pupil_id):
    """Opens local webcam, captures face vector using dlib, and updates MySQL."""
    video_capture = cv2.VideoCapture(0)

    print("\nLook at the camera. Press 's' to capture and save, or 'q' to quit.")

    while True:
        ret, frame = video_capture.read()
        if not ret:
            print("Failed to access camera.")
            break

        # Show live feed with instructions
        cv2.putText(
            frame,
            "Press 'S' to Save Vector | 'Q' to Quit",
            (20, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2,
        )
        cv2.imshow("Enroll Pupil Face", frame)

        key = cv2.waitKey(1) & 0xFF

        if key == ord("s"):
            # Convert BGR to RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Detect faces and compute dlib 128-d encoding
            # boxes = face_recognition.face_locations(rgb_frame)
            # ✅ Upsample 2 or 3 times to detect faces under shadows / angles
            #boxes = face_recognition.face_locations(rgb_frame, number_of_times_to_upsample=2)
            # Uses dlib's Convolutional Neural Network detector instead of HOG
            boxes = face_recognition.face_locations(rgb_frame, model="cnn")
            encodings = face_recognition.face_encodings(rgb_frame, boxes)

            if len(encodings) == 1:
                # Convert numpy array vector to JSON string
                vector_json = json.dumps(encodings[0].tolist())

                # Save to MySQL
                try:
                    conn = mysql.connector.connect(**DB_CONFIG)
                    cursor = conn.cursor()

                    query = """
                        UPDATE Pupils 
                        SET face_vector = %s, has_vector = 1 
                        WHERE ID = %s
                    """
                    cursor.execute(query, (vector_json, pupil_id))
                    conn.commit()

                    cursor.close()
                    conn.close()

                    print(
                        f" Successfully saved face vector for Pupil ID {pupil_id}!"
                    )
                    break
                except mysql.connector.Error as err:
                    print(f"Database error: {err}")
            elif len(encodings) == 0:
                print("⚠️ No face detected! Please look directly at the camera.")
            else:
                print("⚠️ Multiple faces detected! Ensure only one person is in frame.")

        elif key == ord("q"):
            print("Enrollment canceled.")
            break

    video_capture.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    target_pupil_id = input("Enter Pupil ID to enroll: ").strip()
    if target_pupil_id.isdigit():
        capture_and_enroll(int(target_pupil_id))
    else:
        print("Invalid Pupil ID.")
