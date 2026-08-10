<?php
// Force error reporting
ini_set('display_errors', 1);
ini_set('display_startup_errors', 1);
error_reporting(E_ALL);

try {

  // Disable error display in production to prevent system info leakage
error_reporting(E_ALL);
ini_set('display_errors', 0);

$t = time();
$time = date("H:i:s", $t);
$date = date("Y-m-d", $t);

require_once 'config.php';

// ------------------------------------------------------------------
// Parameter Extraction (Prefers POST, falls back to GET for transition)
// ------------------------------------------------------------------
$MacID        = $_POST['MAC'] ?? $_GET['MAC'] ?? '';
$Scanner_ID   = test_input($_POST['Scanner'] ?? $_GET['Scanner'] ?? '');
$raw_user_uid = test_input($_POST['UID'] ?? $_GET['UID'] ?? '');
$is_raw = isset($_POST['raw']) && $_POST['raw'] === '1';

if (!$is_raw) {
    // Perform standard byte swapping logic for MFRC522 raw reads
    $User_RFID_Key  = reverse_bytes($raw_user_uid);
    // Convert numbers to decimal
    $User_RFID_Key_Dec = hexdec($User_RFID_Key);
    // Add leading zeros if needed
    $User_RFID_Key_Formatted = pad_rfid($User_RFID_Key_Dec);
    
 
}
else
{
    // If this has comefrom theface scanner box, then it should be correct!
    $User_RFID_Key_Formatted = $raw_user_uid;
}


$Staff_or_pupil = "Not set";

// ==================================================================
// DT Safety System (Scanner IDs starting with "DT-")
// ==================================================================
if (substr($Scanner_ID, 0, 2) == "DT") {
    wh_log("********* DT-Scanner - Processing ***********");
    
    
    

    $Machine_ID = ltrim($Scanner_ID, "DT-");
    wh_log("DT-Scanner - User RFID = " . $User_RFID_Key_Formatted . " Machine = " . $Scanner_ID);

    $User_ID = DT_System_find_user_ID($link, $User_RFID_Key_Formatted, $Staff_or_pupil);
    
    if (DT_System_are_they_authorised($link, $machinery_db, $Machine_ID, $User_ID, $Staff_or_pupil)) {
        DT_System_store_use($machinery_db, $Machine_ID, $User_ID, $Staff_or_pupil);
        echo "Authorised";
        $result = "Authorised";
    } else {
        echo "Not permitted";
        $result = "Not permitted";
    }

    $log = "RFID:" . $User_RFID_Key_Formatted . " User:" . $User_ID . "-Machine:" . $Machine_ID . " Authorisation: " . $result;
    wh_log($log);

    $stmt = $link->prepare("INSERT INTO ScannerLog (Scanner, RFID, Result) VALUES (?, ?, ?)");
    $stmt->bind_param("sss", $Scanner_ID, $User_RFID_Key_Formatted, $result);
    $stmt->execute();
    $stmt->close();

    wh_log("-----------------------------------------------------------");
    exit(0);
}
} catch (Throwable $e) {
    // Override status code to 200 so LiteSpeed won't swallow the error output
    http_response_code(200);
    header("Content-Type: text/plain");
    echo "CRASH DETECTED:\n";
    echo "Message: " . $e->getMessage() . "\n";
    echo "File: "    . $e->getFile() . "\n";
    echo "Line: "    . $e->getLine() . "\n";
}
// ==================================================================
// HELPER FUNCTIONS
// ==================================================================

function wh_log($log_msg) {
    $log_dir = __DIR__ . '/log';
    if (!file_exists($log_dir)) {
        mkdir($log_dir, 0750, true);
    }
    $log_file_data = $log_dir . '/log_' . date('d-M-Y') . '.log';
    file_put_contents($log_file_data, $log_msg . "\n", FILE_APPEND);
}

function pad_rfid($rfid) {
    return str_pad($rfid, 10, "0", STR_PAD_LEFT);
}

function DT_System_find_user_ID($link, $User_RFID_Key, &$Staff_or_pupil) {
    $User_ID = "";

    // 1. Check Staff table
    if ($stmt = $link->prepare("SELECT TeacherID FROM Staff WHERE RFID = ?")) {
        $stmt->bind_param("s", $User_RFID_Key);
        $stmt->execute();
        $stmt->bind_result($teacher_id);
        
        if ($stmt->fetch()) {
            $Staff_or_pupil = "Staff";
            $stmt->close();
            return $teacher_id;
        }
        $stmt->close();
    }

    // 2. Check Pupils table
    if ($stmt = $link->prepare("SELECT Pupil_ID FROM RFID_Pupil WHERE RFID_Code = ?")) {
        $stmt->bind_param("s", $User_RFID_Key);
        $stmt->execute();
        $stmt->bind_result($pupil_id);
        
        if ($stmt->fetch()) {
            $Staff_or_pupil = "Pupil";
            $stmt->close();
            return $pupil_id;
        }
        $stmt->close();
    }

    return $User_ID;
}
function DT_System_are_they_authorised($link, $machinery_db, $Machine_ID, $User_ID, $Staff_or_pupil) {
    if ($Staff_or_pupil == "Staff") {
        wh_log("Staff OVERRIDE - using machine: " . $Machine_ID);
        return true;
    }

    if (!empty($User_ID)) {
        $stmt = $machinery_db->prepare("SELECT 1 FROM `Authorisation` WHERE Machine_ID = ? AND Machine_User = ?");
        $stmt->bind_param("ss", $Machine_ID, $User_ID);
        $stmt->execute();
        $res = $stmt->get_result();
        $authorised = ($res->num_rows >= 1);
        $stmt->close();
        return $authorised;
    }

    return false;
}

function DT_System_store_use($machinery_db, $Machine_ID, $User_ID, $Staff_or_pupil) {
    $start_time = date("Y-m-d H:i:s");
    
    // 1. Insert the new usage record
    $stmt = $machinery_db->prepare("INSERT INTO Machine_Usage (Machine_ID, User_ID, Staff_or_Pupil, Start_Time) VALUES (?, ?, ?, ?)");
    $stmt->bind_param("ssss", $Machine_ID, $User_ID, $Staff_or_pupil, $start_time);
    $stmt->execute();
    $stmt->close();

    // 2. Get the auto-increment keyfield directly from the insertion
    $inserted_id = $machinery_db->insert_id;

    // Fallback: If keyfield isn't an auto-increment column, retrieve it safely via bind_result()
    if (!$inserted_id) {
        $stmt = $machinery_db->prepare("SELECT keyfield FROM Machine_Usage WHERE Start_Time = ? AND Machine_ID = ? AND User_ID = ?");
        $stmt->bind_param("sss", $start_time, $Machine_ID, $User_ID);
        $stmt->execute();
        $stmt->bind_result($keyfield);
        
        if ($stmt->fetch()) {
            $inserted_id = $keyfield;
        }
        $stmt->close();
    }

    // 3. Output the token in the format expected by the ESP8266
    if ($inserted_id) {
        echo "[" . $inserted_id . "]";
    }
}


function reverse_bytes($rfid) {
    $output = "";
    $index = strlen($rfid);
    while ($index >= 0) {
        $character = substr($rfid, $index, 2);
        $output .= $character;
        $index -= 2;
    }
    return $output;
}

function test_input($data) {
    return htmlspecialchars(stripslashes(trim($data)));
}
?>
