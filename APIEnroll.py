import json
import os
import cv2
import face_recognition
import numpy as np
import requests

os.environ["QT_QPA_PLATFORM"] = "xcb"
os.environ["QT_LOGGING_RULES"] = "*=false"

API_URL = ""


def search_people(surname_prefix):
    """Fetches pupil and staff records matching the surname prefix."""
    try:
        response = requests.get(
            API_URL, params={"q": surname_prefix}, timeout=10
        )
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Server Error {response.status_code}: {response.text}")
            return []
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return []


def select_person():
    """Prompts user for surname search across Pupils & Staff."""
    while True:
        query = (
            input("\nEnter surname prefix (or 'q' to quit): ").strip().lower()
        )

        if query == "q":
            return None

        if len(query) < 2:
            print("⚠️ Enter at least 2 characters to search.")
            continue

        matches = search_people(query)

        if not matches:
            print(f"No records found starting with '{query}'.")
            continue

        print(f"\n--- Found {len(matches)} Match(es) ---")
        for idx, person in enumerate(matches, 1):
            status = (
                "✅ Enrolled" if person.get("has_vector") == 1 else "❌ No Vector"
            )

            ptype = f"[{person.get('PersonType', 'Pupil')}]"
            category = f"({person['Category']})" if person.get("Category") else ""
            print(
                f"  [{idx}] {ptype:<8} {person['Surname']}, {person['Forename']} {category} - {status} [ID: {person['PersonID']}]"
            )

        while True:
            choice = input(
                "\nSelect number to enroll (or 'b' to search again): "
            ).strip()

            if choice.lower() == "b":
                break
            if choice.isdigit():
                num = int(choice)
                if 1 <= num <= len(matches):
                    selected = matches[num - 1]
                    print(
                        f"\n🎯 Selected {selected['PersonType']}: {selected['Forename']} {selected['Surname']} (ID: {selected['PersonID']})"
                    )
                    return selected

            print("Invalid choice.")


def send_vector_to_api(person_id, person_type, vector_json):
    """Sends the generated vector to Namecheap."""
    print(f"Uploading vector for {person_type} ID {person_id} to server...")
    payload = {
        "person_id": person_id,
        "person_type": person_type,
        "face_vector": vector_json,
    }

    try:
        response = requests.post(API_URL, json=payload, timeout=10)
        result = response.json()
        if response.status_code == 200 and result.get("success"):
            print(
                f" Successful! Saved vector for {person_type} ID {person_id}."
            )
            return True
        else:
            print(
                f"❌ API Error ({response.status_code}): {result.get('message')}"
            )
    except Exception as e:
        print(f"❌ Connection error: {e}")

    return False


def capture_and_enroll(person):
    person_id = person["PersonID"]
    person_type = person["PersonType"]
    person_name = f"{person['Forename']} {person['Surname']}"

    video_capture = cv2.VideoCapture(0)
    print(f"\nEnrolling ({person_type}): {person_name}")

    while True:
        ret, frame = video_capture.read()
        if not ret:
            break

        cv2.putText(
            frame,
            f"Enrolling [{person_type}]: {person_name}",
            (20, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 0),
            2,
        )
        cv2.putText(
            frame,
            "Press 'S' to Save Vector | 'Q' to Quit",
            (20, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
        )
        cv2.imshow("Enroll Face", frame)

        key = cv2.waitKey(1) & 0xFF

        if key == ord("s"):
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            boxes = face_recognition.face_locations(
                rgb_frame, number_of_times_to_upsample=1, model="hog"
            )
            encodings = face_recognition.face_encodings(rgb_frame, boxes)

            if len(encodings) == 1:
                vector_json = json.dumps(encodings[0].tolist())
                if send_vector_to_api(person_id, person_type, vector_json):
                    break
            elif len(encodings) == 0:
                print("⚠️ No face detected!")
            else:
                print("⚠️ Multiple faces detected!")

        elif key == ord("q"):
            print("Enrollment canceled.")
            break

    video_capture.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    person = select_person()
    if person:
        capture_and_enroll(person)
