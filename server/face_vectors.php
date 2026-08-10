<?php
error_reporting(0);
ini_set('display_errors', 0);

header('Content-Type: application/json; charset=utf-8');

$host = 'localhost';
$db   = '<Standard_Information>'; 
$user = '';     // Replace with your MySQL user
$pass = ''; // Replace with your MySQL password

try {
    $pdo = new PDO("mysql:host=$host;dbname=$db;charset=utf8mb4", $user, $pass, [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC
    ]);

    // -------------------------------------------------------------
    // 1. GET REQUEST
    // -------------------------------------------------------------
    if ($_SERVER['REQUEST_METHOD'] === 'GET') {
        $search = isset($_GET['q']) ? trim($_GET['q']) : '';

        // MODE A: Search Mode (for APIEnroll.py)
        if (strlen($search) >= 2) {
            $sql = "
                SELECT 
                    p.ID AS PersonID, 
                    p.Forename, 
                    p.Surname, 
                    CONCAT('Year ', p.Year_Group) AS Category, 
                    p.has_vector, 
                    'Pupil' AS PersonType,
                    r.RFID_Code AS RFID
                FROM Pupils p
                LEFT JOIN RFID_Pupil r ON p.ID = r.Pupil_ID
                WHERE p.Surname LIKE :search 

                UNION ALL

                SELECT 
                    s.TeacherID AS PersonID, 
                    s.Forename, 
                    s.Surname, 
                    s.Department AS Category, 
                    s.has_vector, 
                    'Staff' AS PersonType,
                    s.RFID AS RFID
                FROM Staff s
                WHERE s.Surname LIKE :search 

                ORDER BY Surname, Forename 
                LIMIT 20
            ";

            $stmt = $pdo->prepare($sql);
            $stmt->execute([':search' => $search . '%']);
            echo json_encode($stmt->fetchAll());
            exit();
        } 
        
        // MODE B: Fetch All Enrolled Profiles Mode (for APIVerify.py)
        else {
            $sql = "
                SELECT 
                    p.ID AS PersonID, 
                    p.Forename, 
                    p.Surname, 
                    CONCAT('Year ', p.Year_Group) AS Category, 
                    p.has_vector, 
                    p.face_vector,
                    'Pupil' AS PersonType,
                    r.RFID_Code AS RFID
                FROM Pupils p
                LEFT JOIN RFID_Pupil r ON p.ID = r.Pupil_ID
                WHERE p.has_vector = 1

                UNION ALL

                SELECT 
                    s.TeacherID AS PersonID, 
                    s.Forename, 
                    s.Surname, 
                    s.Department AS Category, 
                    s.has_vector, 
                    s.face_vector,
                    'Staff' AS PersonType,
                    s.RFID AS RFID
                FROM Staff s
                WHERE s.has_vector = 1

                ORDER BY Surname, Forename
            ";

            $stmt = $pdo->prepare($sql);
            $stmt->execute();
            echo json_encode($stmt->fetchAll());
            exit();
        }
    }

    // -------------------------------------------------------------
    // 2. POST REQUEST: Save Vector to designated table
    // -------------------------------------------------------------
    if ($_SERVER['REQUEST_METHOD'] === 'POST') {
        $input = json_decode(file_get_contents('php://input'), true);

        $person_id   = isset($input['person_id']) ? intval($input['person_id']) : 0;
        $person_type = isset($input['person_type']) ? $input['person_type'] : 'Pupil';
        $face_vector = isset($input['face_vector']) ? $input['face_vector'] : '';

        if ($person_id <= 0 || empty($face_vector)) {
            http_response_code(400);
            echo json_encode(["success" => false, "message" => "Missing parameters"]);
            exit();
        }

        if ($person_type === 'Staff') {
            $sql = "UPDATE Staff SET face_vector = :face_vector, has_vector = 1 WHERE TeacherID = :person_id";
        } else {
            $sql = "UPDATE Pupils SET face_vector = :face_vector, has_vector = 1 WHERE ID = :person_id";
        }

        $stmt = $pdo->prepare($sql);
        $stmt->execute([
            ':face_vector' => $face_vector,
            ':person_id'   => $person_id
        ]);

        if ($stmt->rowCount() > 0) {
            echo json_encode(["success" => true, "message" => "Vector saved successfully"]);
        } else {
            echo json_encode(["success" => false, "message" => "Record ID $person_id not found or vector unchanged"]);
        }
        exit();
    }

} catch (PDOException $e) {
    http_response_code(500);
    echo json_encode(["success" => false, "message" => "Database error: " . $e->getMessage()]);
}
?>
 
 
