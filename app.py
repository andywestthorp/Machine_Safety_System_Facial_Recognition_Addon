import json
import os
import time
import cv2
import face_recognition
import numpy as np
import requests
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

# -----------------------------------------------------------------------------
# CONFIGURATION & CONSTANTS
# -----------------------------------------------------------------------------
API_URL = "<the address of your server php file>"
DISTANCE_THRESHOLD = 0.55  # Match tolerance (lower = stricter)

SAVE_DEBUG_SNAPS = False   # Set to True to save snapshots in snaps/
SNAPS_DIR = "snaps"

if SAVE_DEBUG_SNAPS:
    os.makedirs(SNAPS_DIR, exist_ok=True)

# Memory Cache for Known Faces
known_encodings = []
known_names = []
known_rfids = []

# Active Enrollment Target (Set via Web Interface)
active_enrollment_target = None


def fetch_known_faces():
    """Fetch 128-D vectors, names, and RFIDs from PHP API into memory."""
    global known_encodings, known_names, known_rfids
    
    print("\n🔄 Fetching enrolled face vectors from server...")
    encodings_cache = []
    names_cache = []
    rfids_cache = []

    try:
        response = requests.get(API_URL, timeout=10)
        if response.status_code != 200:
            print(f"❌ Server returned HTTP {response.status_code}: {response.text}")
            return False

        data = response.json()

        for row in data:
            if "face_vector" in row and row["face_vector"]:
                try:
                    vector_data = json.loads(row["face_vector"])
                    encoding = np.array(vector_data, dtype=np.float64)
                    
                    if len(encoding) == 128:
                        encodings_cache.append(encoding)
                        names_cache.append(f"{row['Forename']} {row['Surname']}")
                        rfids_cache.append(row.get("RFID") or "UNKNOWN")
                except Exception:
                    continue

        known_encodings = encodings_cache
        known_names = names_cache
        known_rfids = rfids_cache

        print(f"✅ Successfully cached {len(known_encodings)} profile(s) in memory.")
        return True

    except Exception as e:
        print(f"❌ Error fetching vectors: {e}")
        return False


# Initialize cache on startup
fetch_known_faces()


def send_vector_to_api(person_id, person_type, vector_json):
    """Uploads the 128-D vector to the PHP API."""
    payload = {
        "person_id": person_id,
        "person_type": person_type,
        "face_vector": vector_json,
    }
    try:
        response = requests.post(API_URL, json=payload, timeout=10)
        result = response.json()
        if response.status_code == 200 and result.get("success"):
            return True, "Operation successful"
        else:
            return False, result.get("message", "API Error")
    except Exception as e:
        return False, str(e)


def delete_vector_from_api(person_id, person_type):
    """Deletes vector by sending delete parameters via both URL params and JSON body."""
    payload = {
        "action": "delete",
        "person_id": person_id,
        "person_type": person_type,
        "face_vector": "DELETE"
    }
    params = {
        "action": "delete",
        "person_id": person_id,
        "person_type": person_type
    }
    
    try:
        # Try JSON POST first
        response = requests.post(API_URL, json=payload, params=params, timeout=10)
        
        try:
            result = response.json()
            if response.status_code == 200 and result.get("success"):
                return True, "Vector deleted successfully"
            elif result.get("message"):
                return False, result.get("message")
        except Exception:
            pass

        # Fallback to standard form-data POST if PHP expects $_POST instead of JSON input
        response = requests.post(API_URL, data=payload, params=params, timeout=10)
        result = response.json()
        
        if response.status_code == 200 and result.get("success"):
            return True, "Vector deleted successfully"
        else:
            return False, result.get("message", f"HTTP {response.status_code}")

    except Exception as e:
        return False, str(e)


# -----------------------------------------------------------------------------
# HTML DASHBOARD TEMPLATE (Rendered at http://192.168.1.230:5000/)
# -----------------------------------------------------------------------------
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Face Recognition & Enrollment Portal</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 20px; display: flex; justify-content: center; }
        .container { max-width: 650px; width: 100%; background: #1e293b; padding: 25px; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
        h1 { font-size: 1.5rem; text-align: center; color: #38bdf8; margin-top: 0; }
        .search-box { width: 100%; padding: 12px; font-size: 1rem; border-radius: 8px; border: 1px solid #475569; background: #0f172a; color: white; box-sizing: border-box; margin-bottom: 15px; }
        .status-banner { background: #334155; border-left: 5px solid #38bdf8; padding: 15px; border-radius: 6px; margin-bottom: 20px; text-align: center; font-size: 1.1rem; }
        .status-banner.active { border-left-color: #f59e0b; background: #451a03; }
        .results-list { list-style: none; padding: 0; margin: 0; max-height: 350px; overflow-y: auto; }
        .person-card { background: #334155; padding: 12px; margin-bottom: 8px; border-radius: 6px; display: flex; justify-content: space-between; align-items: center; }
        .person-info { font-size: 0.95rem; }
        .tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; margin-right: 5px; }
        .tag-pupil { background: #0284c7; color: white; }
        .tag-staff { background: #7c3aed; color: white; }
        .tag-enrolled { background: #16a34a; color: white; }
        .tag-missing { background: #dc2626; color: white; }
        .action-btns { display: flex; gap: 6px; }
        .enroll-btn { background: #38bdf8; color: #0f172a; border: none; padding: 8px 12px; font-weight: bold; border-radius: 6px; cursor: pointer; transition: 0.2s; }
        .enroll-btn:hover { background: #7dd3fc; }
        .delete-btn { background: #ef4444; color: white; border: none; padding: 8px 12px; font-weight: bold; border-radius: 6px; cursor: pointer; transition: 0.2s; }
        .delete-btn:hover { background: #f87171; }
        .cancel-btn { background: #ef4444; color: white; border: none; padding: 8px 14px; font-weight: bold; border-radius: 6px; cursor: pointer; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📸 Face Enrollment Portal</h1>
        
        <div id="statusBanner" class="status-banner">
            🔍 <b>Verification Mode Active</b><br><small>Press ESP32 button to verify faces.</small>
        </div>

        <input type="text" id="searchInput" class="search-box" placeholder="Type surname to search (e.g. Westthorp)..." onkeyup="searchPeople()">

        <ul id="resultsList" class="results-list"></ul>
    </div>

    <script>
        let checkStatusInterval = null;

        function searchPeople() {
            let query = document.getElementById('searchInput').value.trim();
            if (query.length < 2) {
                document.getElementById('resultsList').innerHTML = '';
                return;
            }

            fetch('/search_people?q=' + encodeURIComponent(query))
                .then(res => res.json())
                .then(data => {
                    let list = document.getElementById('resultsList');
                    list.innerHTML = '';

                    if (!data.results || data.results.length === 0) {
                        list.innerHTML = '<li style="text-align:center; padding:10px; color:#94a3b8;">No records found</li>';
                        return;
                    }

                    data.results.forEach(person => {
                        let li = document.createElement('li');
                        li.className = 'person-card';

                        let isEnrolled = person.has_vector == 1;
                        let typeTag = `<span class="tag ${person.PersonType === 'Staff' ? 'tag-staff' : 'tag-pupil'}">${person.PersonType}</span>`;
                        let statusTag = `<span class="tag ${isEnrolled ? 'tag-enrolled' : 'tag-missing'}">${isEnrolled ? 'Enrolled' : 'No Vector'}</span>`;

                        let deleteBtnHTML = isEnrolled ? 
                            `<button class="delete-btn" onclick="deleteVector('${person.PersonID}', '${person.PersonType}', '${person.Forename} ${person.Surname}')">Delete</button>` : '';

                        li.innerHTML = `
                            <div class="person-info">
                                ${typeTag} ${statusTag} <b>${person.Forename} ${person.Surname}</b>
                            </div>
                            <div class="action-btns">
                                <button class="enroll-btn" onclick="startEnrollment('${person.PersonID}', '${person.PersonType}', '${person.Forename} ${person.Surname}')">
                                    ${isEnrolled ? 'Re-enroll' : 'Enroll'}
                                </button>
                                ${deleteBtnHTML}
                            </div>
                        `;
                        list.appendChild(li);
                    });
                });
        }

        function startEnrollment(id, type, name) {
            fetch('/set_enrollment_target', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ person_id: id, person_type: type, name: name })
            }).then(() => updateStatus());
        }

        function deleteVector(id, type, name) {
            if (confirm(`Are you sure you want to delete the facial vector for ${name}?`)) {
                fetch('/delete_vector', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ person_id: id, person_type: type })
                })
                .then(res => res.json())
                .then(data => {
                    alert(data.message);
                    searchPeople();
                });
            }
        }

        function cancelEnrollment() {
            fetch('/cancel_enrollment', { method: 'POST' }).then(() => updateStatus());
        }

        function updateStatus() {
            fetch('/get_enrollment_target')
                .then(res => res.json())
                .then(data => {
                    let banner = document.getElementById('statusBanner');
                    if (data.target) {
                        banner.className = 'status-banner active';
                        banner.innerHTML = `
                            ⏳ <b>ENROLLMENT MODE ACTIVE</b><br>
                            Target: <b>${data.target.name}</b> (${data.target.person_type})<br>
                            <small style="color:#fcd34d;">👉 Point camera at ${data.target.name} & PRESS SNAP BUTTON on ESP32 now!</small><br>
                            <button class="cancel-btn" onclick="cancelEnrollment()">Cancel Enrollment</button>
                        `;
                        if (!checkStatusInterval) {
                            checkStatusInterval = setInterval(updateStatus, 2000);
                        }
                    } else {
                        banner.className = 'status-banner';
                        banner.innerHTML = `🔍 <b>Verification Mode Active</b><br><small>Press ESP32 button to verify faces.</small>`;
                        if (checkStatusInterval) {
                            clearInterval(checkStatusInterval);
                            checkStatusInterval = null;
                            searchPeople(); 
                        }
                    }
                });
        }

        updateStatus();
    </script>
</body>
</html>
"""

# -----------------------------------------------------------------------------
# FLASK ROUTES
# -----------------------------------------------------------------------------
@app.route('/')
def home():
    return render_template_string(HTML_PAGE)


@app.route('/set_enrollment_target', methods=['POST'])
def set_target():
    global active_enrollment_target
    data = request.json
    active_enrollment_target = {
        "person_id": data["person_id"],
        "person_type": data["person_type"],
        "name": data["name"]
    }
    print(f"\n🎯 Enrollment Target Set: {data['name']} (ID: {data['person_id']})")
    return jsonify({"status": "success"}), 200


@app.route('/cancel_enrollment', methods=['POST'])
def cancel_target():
    global active_enrollment_target
    active_enrollment_target = None
    print("\n🛑 Enrollment canceled. Back to verification mode.")
    return jsonify({"status": "success"}), 200


@app.route('/get_enrollment_target', methods=['GET'])
def get_target():
    return jsonify({"target": active_enrollment_target}), 200


@app.route('/delete_vector', methods=['POST'])
def delete_vector_route():
    data = request.json
    person_id = data.get("person_id")
    person_type = data.get("person_type", "Pupil")

    if not person_id:
        return jsonify({"status": "error", "message": "Missing person_id"}), 400

    print(f"\n🗑️ Deleting vector for {person_type} ID: {person_id}...")
    
    success, msg = delete_vector_from_api(person_id, person_type)

    if success:
        fetch_known_faces()  # Reload local cache immediately
        return jsonify({"status": "success", "message": f"Successfully deleted vector for ID {person_id}"}), 200
    else:
        return jsonify({"status": "error", "message": f"Failed to delete vector: {msg}"}), 500


@app.route('/search_people', methods=['GET'])
def search_people_route():
    query = request.args.get('q', '').strip().lower()
    if len(query) < 2:
        return jsonify({"status": "error", "message": "Query must be at least 2 characters"}), 400

    try:
        response = requests.get(API_URL, params={"q": query}, timeout=10)
        if response.status_code == 200:
            return jsonify({"status": "success", "results": response.json()}), 200
        return jsonify({"status": "error", "message": response.text}), response.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/upload', methods=['POST'])
def handle_esp32_upload():
    global active_enrollment_target

    image_bytes = request.data
    if not image_bytes:
        return jsonify({"status": "error", "message": "No image data"}), 400

    np_arr = np.frombuffer(image_bytes, np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if frame is None:
        return jsonify({"status": "error", "message": "Failed to decode JPEG"}), 400

    # Horizontal flip (mirror)
    frame = cv2.flip(frame, 1)

    if SAVE_DEBUG_SNAPS:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        cv2.imwrite(os.path.join(SNAPS_DIR, f"snap_{timestamp}.jpg"), frame)

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    face_locations = face_recognition.face_locations(rgb_frame, number_of_times_to_upsample=1, model="hog")
    face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

    if not face_encodings:
        print("📸 ESP32 Snap Processed: No face detected.")
        return jsonify({"status": "success", "recognized": False, "message": "No face found"}), 200

    # =========================================================================
    # MODE A: ENROLLMENT MODE
    # =========================================================================
    if active_enrollment_target:
        target = active_enrollment_target
        if len(face_encodings) > 1:
            return jsonify({"status": "error", "message": "Multiple faces detected! Single person required."}), 400

        print(f"⚡ Enrolling face for {target['name']}...")
        vector_json = json.dumps(face_encodings[0].tolist())
        
        success, msg = send_vector_to_api(target["person_id"], target["person_type"], vector_json)

        if success:
            fetch_known_faces()  # Refresh memory cache
            enrolled_person = target['name']
            active_enrollment_target = None  # Reset back to verification mode
            
            return jsonify({
                "status": "success",
                "recognized": True,
                "results": [{"name": f"ENROLLED: {enrolled_person}", "rfid": "NEW VECTOR", "distance": 0.0}]
            }), 200
        else:
            active_enrollment_target = None
            return jsonify({"status": "error", "message": msg}), 500

    # =========================================================================
    # MODE B: VERIFICATION / MATCHING MODE
    # =========================================================================
    matches_summary = []

    for face_encoding in face_encodings:
        name = "Unknown"
        rfid = "N/A"
        distance = 1.0

        if len(known_encodings) > 0:
            face_distances = face_recognition.face_distance(known_encodings, face_encoding)
            best_match_index = np.argmin(face_distances)
            distance = float(face_distances[best_match_index])

            if distance < DISTANCE_THRESHOLD:
                name = known_names[best_match_index]
                rfid = known_rfids[best_match_index]
                print(f"🎯 Match Found: {name} | RFID: {rfid} | Distance: {distance:.3f}")
            else:
                print(f"❓ Face Detected but Unknown (Distance: {distance:.3f})")

        matches_summary.append({
            "name": name,
            "rfid": rfid,
            "distance": round(distance, 4)
        })

    return jsonify({
        "status": "success",
        "recognized": any(m["name"] != "Unknown" for m in matches_summary),
        "results": matches_summary
    }), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
