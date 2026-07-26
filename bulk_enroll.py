import json
import os
import sys
import face_recognition
import mysql.connector
import numpy as np

# Suppress Qt/Wayland display warnings in terminal
os.environ["QT_QPA_PLATFORM"] = "xcb"
os.environ["QT_LOGGING_RULES"] = "*=false"

# Match your active working database configuration
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5522,  # Uses your local SSH tunnel port
    "user": "YOUR_DB_USER",
    "password": "YOUR_DB_PASSWORD",
    "database": "YOUR_DB",
}


def enroll_pupil_from_image(pupil_id, image_path):
    """Loads an image, generates a 128-d dlib vector, and saves it to MySQL."""
    if not os.path.exists(image_path):
        print(f"❌ Error: Image file '{image_path}' not found.")
        return False

    print(f"\nProcessing Pupil ID {pupil_id} from '{image_path}'...")

    # 1. Load image using face_recognition
    image = face_recognition.load_image_file(image_path)

    # 2. Detect face locations using HOG + 1 upsample pass (Matches verify settings)
    face_locations = face_recognition.face_locations(
        image, number_of_times_to_upsample=1, model="hog"
    )

    if len(face_locations) == 0:
        print(
            f"⚠️ No face detected in '{image_path}'. Ensure good lighting and a clear view."
        )
        return False
    elif len(face_locations) > 1:
        print(
            f"⚠️ Multiple faces ({len(face_locations)}) detected in '{image_path}'. Image must contain only 1 person."
        )
        return False

    # 3. Generate 128-dimensional vector encoding
    encodings = face_recognition.face_encodings(image, face_locations)
    vector_json = json.dumps(encodings[0].tolist())

    # 4. Save/Update in MySQL Database
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        query = """
            UPDATE Pupils 
            SET face_vector = %s, has_vector = 1 
            WHERE PupilID = %s
        """
        cursor.execute(query, (vector_json, pupil_id))
        conn.commit()

        if cursor.rowcount > 0:
            print(
                f" Successful! Pupil ID {pupil_id} enrolled with vector size {len(encodings[0])}."
            )
            success = True
        else:
            print(
                f"⚠️ Database connected, but Pupil ID {pupil_id} was not found in the database table."
            )
            success = False

        cursor.close()
        conn.close()
        return success

    except mysql.connector.Error as err:
        print(f"❌ Database error: {err}")
        return False


def bulk_enroll_folder(folder_path):
    """Bulk process a folder where images are named by PupilID (e.g., '101.jpg', '102.png')."""
    if not os.path.exists(folder_path):
        print(f"❌ Folder '{folder_path}' does not exist.")
        return

    valid_extensions = (".jpg", ".jpeg", ".png", ".webp")
    files = [
        f
        for f in os.listdir(folder_path)
        if f.lower().endswith(valid_extensions)
    ]

    print(f"Found {len(files)} image(s) in '{folder_path}' to process.")

    success_count = 0
    for filename in files:
        # Extract PupilID from filename (e.g., '101.jpg' -> '101')
        pupil_id_str = os.path.splitext(filename)[0]

        if pupil_id_str.isdigit():
            image_path = os.path.join(folder_path, filename)
            if enroll_pupil_from_image(int(pupil_id_str), image_path):
                success_count += 1
        else:
            print(
                f"Skipping '{filename}': Filename must be numerical (e.g., '123.jpg')."
            )

    print(
        f"\n Bulk enrollment complete: {success_count}/{len(files)} pupils updated successfully."
    )


if __name__ == "__main__":
    # Check command-line arguments
    if len(sys.argv) == 3 and sys.argv[1] == "--single":
        # Usage: python bulk_enroll.py --single <PupilID> <path_to_image.jpg>
        pupil_id = sys.argv[2]
        img_path = sys.argv[3] if len(sys.argv) > 3 else ""
        if pupil_id.isdigit() and img_path:
            enroll_pupil_from_image(int(pupil_id), img_path)
        else:
            print("Usage: python bulk_enroll.py --single <PupilID> <image.jpg>")

    elif len(sys.argv) == 2:
        # Usage: python bulk_enroll.py <folder_path>
        folder = sys.argv[1]
        bulk_enroll_folder(folder)

    else:
        print("--- DTFace Bulk Enrollment Tool ---")
        print("Option 1 (Bulk Folder): python bulk_enroll.py ./pupil_photos")
        print(
            "Option 2 (Single File): python bulk_enroll.py --single 101 ./pupil_photos/101.jpg"
        )
