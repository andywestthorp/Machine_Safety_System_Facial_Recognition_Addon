<?php
// Database configuration
$host     = 'localhost';
$db_name  = '';
$username = 'YOUR_DB_USER';                 // Replace with your DB username
$password = 'YOUR_DB_PASSWORD';             // Replace with your DB password

try {
    $pdo = new PDO("mysql:host=$host;dbname=$db_name;charset=utf8mb4", $username, $password);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
} catch (PDOException $e) {
    die("Database Connection Failed: " . $e->getMessage());
}

$message = '';

// Handle Form Submission (Update Vector)
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['update_vector'])) {
    $pupil_id    = !empty($_POST['pupil_id']) ? (int)$_POST['pupil_id'] : 0;
    $face_vector = trim($_POST['face_vector'] ?? '');

    if ($pupil_id <= 0 || empty($face_vector)) {
        $message = '<div class="alert alert-danger">Please select a pupil and capture a face vector first.</div>';
    } else {
        // Automatically determine Primary Key column name
        $id_col = 'PupilID'; // Change to 'ID' or 'id' if needed

        $sql = "UPDATE Pupils SET face_vector = :face_vector, has_vector = 1 WHERE {$id_col} = :pupil_id";
        $stmt = $pdo->prepare($sql);
        $executed = $stmt->execute([
            ':face_vector' => $face_vector,
            ':pupil_id'    => $pupil_id
        ]);

        if ($executed) {
            $message = '<div class="alert alert-success">Face vector updated successfully!</div>';
        } else {
            $message = '<div class="alert alert-danger">Failed to update pupil record.</div>';
        }
    }
}

// Fetch pupils
$pupils = [];
try {
    $stmt = $pdo->query("SELECT * FROM Pupils ORDER BY Surname, Forename");
    $pupils = $stmt->fetchAll(PDO::FETCH_ASSOC);
} catch (PDOException $e) {
    $message = '<div class="alert alert-danger">SQL Query Failed: ' . htmlspecialchars($e->getMessage()) . '</div>';
}
?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Enroll Face Vector</title>
    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <!-- Select2 CSS -->
    <link href="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css" rel="stylesheet" />
    <link href="https://cdn.jsdelivr.net/npm/select2-bootstrap-5-theme@1.3.0/dist/select2-bootstrap-5-theme.min.css" rel="stylesheet" />

    <!-- face-api.js Library -->
    <script defer src="https://cdn.jsdelivr.net/npm/@vladmandic/face-api/dist/face-api.js"></script>

    <style>
        #video-container {
            position: relative;
            width: 100%;
            max-width: 480px;
            margin: 0 auto;
            background: #000;
            border-radius: 8px;
            overflow: hidden;
        }
        video {
            width: 100%;
            height: auto;
            display: block;
        }
    </style>
</head>
<body class="bg-light">

<div class="container mt-4 mb-5">
    <div class="row justify-content-center">
        <div class="col-md-8">
            <div class="card shadow-sm">
                <div class="card-header bg-primary text-white">
                    <h4 class="card-title mb-0">Enroll Pupil Face Vector</h4>
                </div>
                <div class="card-body">
                    <?= $message; ?>

                    <form method="POST" action="enroll.php">
                        <input type="hidden" name="update_vector" value="1">

                        <!-- Select Pupil -->
                        <div class="mb-4">
                            <label for="pupil_id" class="form-label fw-bold">1. Select Pupil *</label>
                            <select class="form-select select2" id="pupil_id" name="pupil_id" required>
                                <option value="" disabled selected>Search by name, year, or house...</option>
                                <?php foreach ($pupils as $pupil): 
                                    $id = $pupil['PupilID'] ?? $pupil['ID'] ?? $pupil['id'] ?? 0;
                                    $hasVector = !empty($pupil['has_vector']);
                                ?>
                                    <option value="<?= htmlspecialchars($id); ?>">
                                        <?= htmlspecialchars(($pupil['Surname'] ?? '') . ', ' . ($pupil['Forename'] ?? '')); ?> 
                                        (Year: <?= htmlspecialchars($pupil['Year_Group'] ?? 'N/A'); ?>, House: <?= htmlspecialchars($pupil['House'] ?? 'N/A'); ?>)
                                        <?= $hasVector ? ' [Vector Enrolled]' : ' [No Vector]'; ?>
                                    </option>
                                <?php endforeach; ?>
                            </select>
                        </div>

                        <!-- Webcam Section -->
                        <div class="mb-4 text-center">
                            <label class="form-label fw-bold d-block">2. Capture Face Vector</label>
                            
                            <div id="video-container" class="mb-3">
                                <video id="webcam" autoplay muted playsinline></video>
                            </div>

                            <div id="status-badge" class="badge bg-secondary mb-3">Loading face detection models...</div>

                            <div>
                                <button type="button" id="btn-capture" class="btn btn-success" disabled>
                                    📸 Capture Face & Generate Vector
                                </button>
                            </div>
                        </div>

                        <!-- Hidden / Readonly Vector Data Container -->
                        <div class="mb-4">
                            <label for="face_vector" class="form-label fw-bold">Generated Vector Output</label>
                            <textarea class="form-control font-monospace" id="face_vector" name="face_vector" rows="3" readonly placeholder="Vector coordinates will appear here after clicking capture..." required></textarea>
                        </div>

                        <div class="d-grid">
                            <button type="submit" id="btn-submit" class="btn btn-primary btn-lg" disabled>Save Vector to Database</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Scripts -->
<script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js"></script>

<script>
$(document).ready(function() {
    $('.select2').select2({ theme: 'bootstrap-5' });
});

const video = document.getElementById('webcam');
const statusBadge = document.getElementById('status-badge');
const btnCapture = document.getElementById('btn-capture');
const btnSubmit = document.getElementById('btn-submit');
const vectorInput = document.getElementById('face_vector');

// Load Face-API models from CDN
async function loadModels() {
    const MODEL_URL = 'https://cdn.jsdelivr.net/npm/@vladmandic/face-api/model/';
    
    try {
        await faceapi.nets.ssdMobilenetv1.loadFromUri(MODEL_URL);
        await faceapi.nets.faceLandmark68Net.loadFromUri(MODEL_URL);
        await faceapi.nets.faceRecognitionNet.loadFromUri(MODEL_URL);
        
        statusBadge.className = 'badge bg-info';
        statusBadge.innerText = 'Models loaded. Starting webcam...';
        startWebcam();
    } catch (err) {
        statusBadge.className = 'badge bg-danger';
        statusBadge.innerText = 'Error loading models: ' + err.message;
    }
}

// Start Video Stream
function startWebcam() {
    navigator.mediaDevices.getUserMedia({ video: {} })
        .then(stream => {
            video.srcObject = stream;
            statusBadge.className = 'badge bg-success';
            statusBadge.innerText = 'Ready to capture';
            btnCapture.disabled = false;
        })
        .catch(err => {
            statusBadge.className = 'badge bg-danger';
            statusBadge.innerText = 'Webcam access denied or unavailable';
        });
}

// Capture and Generate Vector
btnCapture.addEventListener('click', async () => {
    statusBadge.className = 'badge bg-warning text-dark';
    statusBadge.innerText = 'Detecting face & calculating descriptors...';

    const detection = await faceapi.detectSingleFace(video)
                                   .withFaceLandmarks()
                                   .withFaceDescriptor();

    if (detection) {
        // Convert Float32Array vector descriptor to JSON array string
        const vectorArray = Array.from(detection.descriptor);
        vectorInput.value = JSON.stringify(vectorArray);

        statusBadge.className = 'badge bg-success';
        statusBadge.innerText = 'Face captured successfully!';
        btnSubmit.disabled = false;
    } else {
        statusBadge.className = 'badge bg-danger';
        statusBadge.innerText = 'No face detected! Ensure good lighting and look directly at the camera.';
    }
});

// Initialize on page load
window.addEventListener('DOMContentLoaded', loadModels);
</script>

</body>
</html>
