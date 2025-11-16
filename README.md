## Warehouse RTLS & Navigation System

It uses multiple ESP32 devices (as fixed anchors and mobile tags) to calculate a tag's position in real-time.
The system is built on an MQTT message bus with a Python backend (Flask/SocketIO) and a live-updating web dashboard. It supports tracking multiple mobile tags, uses a Kalman filter for location smoothing, and integrates RFID scanning for identifying racks or items.


## System Architecture
Mobile Tag (mobile.cpp): An ESP32 with an MFRC522 reader. It performs two jobs:
Broadcasts a BLE beacon (e.g., TAG_001) so anchors can "see" it.
Scans for RFID tags and publishes the UID via MQTT (e.g., to warehouse/scanner/rack_scan).

Fixed Anchors (anchor.cpp): 3+ ESP32s at known (X, Y) coordinates.
They scan for BLE beacons (e.g., TAG_...).
They publish the tag's ID, RSSI, and their own position to MQTT (e.g., to warehouse/anchors/ANCHOR_1/data).

Broker (Mosquitto): A central MQTT server that routes all messages.

Backend Server (server.py): The "brain" of the system.
Subscribes to all MQTT topics.
Calculates the (X, Y) position for each tag using trilateration.
Applies a Kalman Filter to each tag's position for smoothing.
Looks up scanned RFID UIDs in a database.
Serves the index.html dashboard and map.svg.
Pushes live position_update and rack_update events to the dashboard via SocketIO.

Database (db.py): An SQLite setup script that creates and populates tables for anchors and destinations.
Frontend (index.html & map.svg): The web dashboard.
Renders the map.svg floor plan.




## How It Works
Like "GPS for indoors." GPS doesn't work well inside buildings, so RTLS uses a different setup:
Tags (Mobile): A battery-powered device (a "tag") is attached to the person or object you want to track (like your mobile ESP32). This tag constantly sends out a signal.

Anchors (Fixed): These are like small "lighthouses" placed at known positions on the walls or ceiling. They "listen" for the tag's signal.

Software : When three or more anchors hear a tag's signal, they measure its strength (RSSI) or its time of arrival. They send this information to a central server , which uses a process called trilateration or multilateration to calculate the tag's precise (X, Y) coordinates on a map.
Common technologies used for the signals include BLE (Bluetooth Low Energy), UWB (Ultra-Wideband), WiFi, and Active RFID.

## What It's Used For
The main goal is to know "where is what" at all times.
Asset Tracking: Finding medical equipment in a hospital (like an IV pump) or a specific forklift in a warehouse.
Personnel Tracking: Ensuring worker safety in a mine or factory, or finding a doctor in a hospital.
Navigation: Guiding a person (or robot) through a complex building, just like in your project.

## Project Structure
Warehouse_Project/
├── server.py
├── db.py
├── warehouse.db    //created while runtime of db.py
├── templates/
│   └── index.html 
└── static/
    └── map.svg          // custom map file

