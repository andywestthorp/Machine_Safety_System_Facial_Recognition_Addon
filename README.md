# Machine Safety System

A lightweight hybrid web and desktop application designed to enroll, store, and verify pupil facial recognition vectors. The system uses a **PHP/JS** interface for vector enrollment via a web browser and a **Python** script for real-time video verification.

This is an addon to an existing RFID based system which I built a few years ago and have trialled with my pupils- but found taht tehy often forgot to bring their RFID tags. Hopefully, they won't forget to bring their faces?

---

## 🌟 Features

* **Web-Based Enrollment (`enroll.php`):**
  * Searchable pupil selection dropdown powered by **Select2**.
  * Real-time browser webcam capture using **face-api.js**.
  * Extracts 128-dimensional face embeddings and saves them directly to MySQL.
  * Auto-updates the pupil database flags (`has_vector = 1`).

* **Real-Time Verification (`verify.py`):**
  * Connects to MySQL and loads enrolled face vector profiles into memory.
  * Live camera stream processing using **OpenCV** and **dlib (`face_recognition`)**.
  * Frame scaling and downsampling for high-FPS detection.
  * Real-time bounding box rendering (Green = Recognized, Red = Unknown).

---

## 🗄️ Database Prerequisites

Ensure your MySQL database (`longtwla_Standard_Information`) contains a `Pupils` table with the following minimal structure:

```sql
ALTER TABLE Pupils 
ADD COLUMN face_vector TEXT DEFAULT NULL,
ADD COLUMN has_vector TINYINT(1) DEFAULT 0;

```

---

## 🚀 Quick Start & Installation

### 1. Web Enrollment Setup (`enroll.php`)

1. Host `enroll.php` on a web server running PHP 7.4+ and MySQL.
2. Update the database credentials at the top of `enroll.php`:
```php
$host     = 'localhost';
$db_name  = 'longtwla_Standard_Information';
$username = 'YOUR_DB_USER';
$password = 'YOUR_DB_PASSWORD';

```


3. Open `enroll.php` in your web browser, grant camera permissions, select a pupil, and click **Capture Face** then **Save Vector**.

---

### 2. Python Verification Setup (`verify.py`)

#### Prerequisites

* Python 3.8+
* A working webcam

#### Step 1: Clone the Repository

```bash
git clone [https://github.com/your-username/your-repo-name.git](https://github.com/your-username/your-repo-name.git)
cd your-repo-name

```

#### Step 2: Create & Activate a Virtual Environment

* **Windows (Command Prompt):**
```cmd
python -m venv venv
venv\Scripts\activate

```


* **Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1

```


* **macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate

```



#### Step 3: Install Dependencies

```bash
pip install opencv-python face_recognition mysql-connector-python numpy

```

> **Note for Windows Users:** Installing `face_recognition` requires `dlib`. If you hit building errors, install CMake first:
> `pip install cmake`

#### Step 4: Configure Database Settings

Edit the `DB_CONFIG` dictionary inside `verify.py`:

```python
DB_CONFIG = {
    "host": "localhost",
    "user": "YOUR_DB_USER",
    "password": "YOUR_DB_PASSWORD",
    "database": "longtwla_Standard_Information"
}

```

#### Step 5: Run Verification

```bash
python verify.py

```

* Press **`q`** at any time to exit the camera feed.

---

## 🛠️ Configuration & Tuning

In `verify.py`, you can fine-tune recognition sensitivity by altering the tolerance threshold on line 91:

```python
matches = face_recognition.compare_faces(known_encodings, face_encoding, tolerance=0.55)

```

* **Lower tolerance (e.g., `0.45`):** Stricter matching. Reduces false positives but may require better lighting.
* **Higher tolerance (e.g., `0.65`):** More forgiving matching. Useful for low-light environments.

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.

```

```
