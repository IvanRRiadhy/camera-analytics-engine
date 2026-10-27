# Beginner's Guide: Setting Up Standalone CCTV AI Analytics (`standalone.json`)

Welcome! This guide is designed for **everyone**—even if you have zero background in programming or software engineering.

By following this tutorial, you will learn how to configure and run the **CCTV Analytics Engine** in **Standalone Mode** using a simple text file called `configs/standalone.json`.

---

## 💡 What is Standalone Mode?

Think of **Standalone Mode** as plugging an AI box directly into your security camera system:
- It runs 100% locally on your computer or edge device.
- It does **not** require any backend servers, web databases, or internet connections.
- All settings (cameras, detection areas, features, and logs) are controlled from **one file**: `configs/standalone.json`.

---

## 🛠️ How to Open and Edit the Settings File

1. Locate the file in your project folder:
   ```text
   CCTV Analytics/
   ├── configs/
   │   └── standalone.json  <-- THIS IS YOUR CONFIGURATION FILE
   ```
2. Right-click `standalone.json` and open it with **Notepad**, **Notepad++**, or **VS Code**.

> [!TIP]
> **JSON Formatting Rule**: JSON uses `{ }`, `[ ]`, and quotation marks `" "`. Always make sure every quote is closed, and separate items in a list with commas `,` (except the last item in a list).

---

## 📋 Complete Setting-by-Setting Explanation

Here is a sample configuration file followed by an easy explanation of every field:

```json
{
  "schema_version": "2.0.0",
  "config_version": "1.0.0",
  "engine": {
    "engine_id": "engine_standalone_01",
    "engine_name": "Standalone Edge CCTV Analytics",
    "mode": "standalone",
    "version": "1.5.0",
    "log_level": "INFO"
  },
  "runtime": {
    "device": "cuda:0",
    "worker_threads": 4,
    "max_fps": 30.0,
    "standalone": true,
    "display": true
  },
  "communication": {
    "publishers": [
      {
        "type": "console",
        "enabled": true,
        "publish_interval_seconds": 1.0,
        "ignore_change_detection": false
      },
      {
        "type": "log",
        "enabled": true,
        "publish_interval_seconds": 5.0,
        "ignore_change_detection": true,
        "log_dir": "logs",
        "human_filename": "analytics.log",
        "ndjson_filename": "analytics.ndjson",
        "max_bytes": 10485760,
        "max_backup_files": 5,
        "keep_last_days": 7
      }
    ]
  },
  "cameras": [
    {
      "camera_id": "cam_lobby_01",
      "name": "Lobby Entrance Camera",
      "rtsp_url": "rtsp://admin:Admin1234@192.168.1.64/Streaming/channels/1",
      "fps": 30.0,
      "device": "cuda:0",
      "viewer_enabled": true,
      "enabled_modules": ["people_counting", "queue_detection", "loitering"],
      "zones": [
        {
          "zone_id": "zone_lobby_entry",
          "name": "Main Entrance Lobby Zone",
          "type": "polygon",
          "color": [255, 0, 255],
          "points": [
            [100, 120],
            [600, 120],
            [650, 500],
            [80, 500]
          ]
        }
      ]
    }
  ]
}
```

---

### Section 1: Engine Information (`engine`)

This section gives your AI system an identity.

- `"engine_id"`: A unique name for your computer/device (e.g. `"engine_building_a"`).
- `"engine_name"`: Human-readable description (e.g. `"Building A Security Guard AI"`).
- `"mode"`: Always set to `"standalone"` for local operation.
- `"log_level"`: Controls how detailed system messages are (`"INFO"` is standard; `"DEBUG"` is for troubleshooting).

---

### Section 2: Hardware & Runtime Settings (`runtime`)

This section tells the AI how to use your computer's hardware.

- `"device"`: Controls whether to use a Graphics Card (GPU) or Processor (CPU).
  - `"cuda:0"`: Use your first NVIDIA Graphics Card (Recommended for fast AI).
  - `"cpu"`: Use your computer's regular processor (Slower, but works on any PC).
- `"display"`:
  - `true`: Opens a visual window showing live video feed with bounding boxes and drawn zones.
  - `false`: Runs quietly in the background without showing any video windows.

---

### Section 3: Output & Logging (`communication`)

This section controls where the AI sends results (on-screen text, log files, etc.).

#### Console Output (`type: "console"`)
Displays short status lines on your terminal screen (e.g. `[09:00:00] cam_lobby_01 | FPS 30 | People 3`).

#### File Log (`type: "log"`)
Saves counts and events into text files inside the `logs/` folder.
- `"publish_interval_seconds"`: How often to save logs (e.g. `5.0` = every 5 seconds).
- `"ignore_change_detection"`:
  - `true`: Keeps saving logs every 5 seconds continuously (even if 0 people are found).
  - `false`: Saves logs only when person counts or zone activity changes.
- `"max_bytes"`: Maximum size of a log file before starting a new one (e.g. `10485760` = 10 Megabytes).
- `"keep_last_days"`: Deletes log files older than this number of days (e.g. `7` = keep 1 week).

---

### Section 4: Camera Setup (`cameras`)

You can add one or multiple IP cameras to this list!

- `"camera_id"`: Unique ID for this camera (e.g. `"cam_parking_01"`). Must not contain spaces.
- `"name"`: Friendly name shown on top of the video window (e.g. `"West Gate Parking"`).
- `"rtsp_url"`: The video stream address provided by your IP camera or NVR.
  - Example RTSP URL: `"rtsp://admin:Password123@192.168.1.100:554/live"`
  - For testing with a video file: `"video_test.mp4"`
  - For testing with your webcam: `"0"`
- `"enabled_modules"`: List of AI features enabled for this camera (see Feature List below).

---

## 🎯 Available AI Feature Modules (`enabled_modules`)

Choose which AI features to activate on each camera by placing their names in the list:

```json
"enabled_modules": ["people_counting", "queue_detection", "loitering"]
```

| Module Name | What It Does | Best Used For |
| :--- | :--- | :--- |
| `"people_counting"` | Counts total people currently visible, total people who entered, and total who exited. | Entrances, lobbies, walkways. |
| `"queue_detection"` | Measures how many people are standing in line within a defined zone. | Cashier lines, reception desks, ticket booths. |
| `"loitering"` | Detects people staying stationary inside a zone longer than allowed. | Restricted areas, security gates, ATMs. |

---

## 📐 How to Draw Detection Zones (`zones`)

Zones allow you to draw specific shapes (Polygons) on the camera image to restrict AI rules.

```text
(0,0) Top-Left corner of video
  +-----------------------------------+ (1920, 0)
  |                                   |
  |      [100, 120]--------[600, 120] |
  |          |                  |     |
  |      [80, 500]---------[650, 500] |
  |                                   |
  +-----------------------------------+ (1920, 1080) Bottom-Right corner
```

- `"zone_id"`: Unique ID for this zone (e.g. `"zone_lobby_door"`).
- `"type"`: Shape type. Set to `"polygon"`.
- `"color"`: RGB Color of the shape `[Red, Green, Blue]`.
  - `[0, 255, 0]` = Bright Green
  - `[255, 0, 0]` = Bright Red
  - `[255, 0, 255]` = Magenta/Purple
- `"points"`: A list of `[x, y]` pixel coordinates connecting the corners of your shape.
  - A `"polygon"` requires at least **3 corner points**.

---

## 🎯 Interactive Cursor Coordinate Tooltip (Easy Zone Drawing)

To make drawing zone polygons effortless, the video viewer window includes an **Interactive Cursor Tooltip**:

1. Open the video viewer window (`"display": true`).
2. Move your mouse over any point in the video feed.
3. A bright yellow **`(x, y)` coordinate badge** will hover at the top-right of your cursor, along with a small crosshair dot.
4. Simply hover over each corner point of your desired zone, write down the numbers shown (e.g. `(600, 120)`), and paste them directly into your `standalone.json` points list!

---

## 🚀 How to Run Standalone Mode

Once you have edited and saved `configs/standalone.json`, open your terminal and run:

```bash
python -m camera_analytics.main --standalone
```

---

## ❓ Common Beginner Questions & Error Troubleshooting

### 1. "The engine stopped immediately with a `[CRITICAL]` message!"
- **Cause**: The engine uses a **Fail-Fast** safety policy. If your RTSP URL is incorrect, your camera password is wrong, or YOLO AI model weights are missing, it will abort immediately rather than showing fake results.
- **Fix**: Double-check your camera RTSP address and password in `standalone.json`.

### 2. "The zone polygon shape isn't drawing!"
- **Cause**: Polygons require at least 3 corner points `[[x1, y1], [x2, y2], [x3, y3]]`.
- **Fix**: Check that your coordinates are within your camera resolution (e.g. between 0 and 1920 for X, and 0 and 1080 for Y).

### 3. "Can I add more than one camera?"
- **Yes!** Simply duplicate the camera block inside `"cameras": [ ... ]` separated by a comma `,`. Give each camera a unique `"camera_id"`.
