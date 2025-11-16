import paho.mqtt.client as mqtt
import json
import time
import sqlite3
from flask import Flask, render_template, request, jsonify, g
from flask_socketio import SocketIO, emit
import numpy as np
from scipy.optimize import least_squares
import networkx as nx
from threading import Lock
from filterpy.kalman import KalmanFilter
from filterpy.common import Q_discrete_white_noise
from datetime import datetime

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

DATABASE = 'warehouse.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

global_lock = Lock()
anchor_positions = {} 
anchor_data_cache = {}  
tag_positions = {} 
kalman_filters = {} 
warehouse_graph = None

#Kalman Filter 
def create_kalman_filter():
    dt = 1.0 # Time step
    kf = KalmanFilter(dim_x=4, dim_z=2) 
    kf.x = np.array([25., 25., 0., 0.])
    kf.F = np.array([[1, 0, dt, 0], [0, 1, 0, dt], [0, 0, 1, 0], [0, 0, 0, 1]])
    kf.H = np.array([[1, 0, 0, 0], [0, 1, 0, 0]]) 
    kf.R = np.eye(2) * 5
    kf.Q = Q_discrete_white_noise(dim=4, dt=dt, var=0.5)
    kf.P = np.eye(4) * 50
    return kf

#Trilateration(gps_model)
def trilaterate(anchor_list):
    if len(anchor_list) < 3:
        return None

    anchors_with_pos = []
    for anchor_data in anchor_list:
        if anchor_data['id'] in anchor_positions:
            anchors_with_pos.append({
                **anchor_data,
                'x': anchor_positions[anchor_data['id']][0],
                'y': anchor_positions[anchor_data['id']][1]
            })

    if len(anchors_with_pos) < 3:
        return None 
        
    sorted_anchors = sorted(anchors_with_pos, key=lambda a: a['rssi'], reverse=True)[:3]
    points = np.array([[a['x'], a['y']] for a in sorted_anchors])
    distances = np.array([a['dist'] for a in sorted_anchors])
    
    def residuals(pos):
        return np.linalg.norm(points - pos, axis=1) - distances
    
    try:
        result = least_squares(residuals, np.mean(points, axis=0))
        return tuple(result.x)
    except:
        return None

def create_warehouse_graph():
    global warehouse_graph
    G = nx.grid_2d_graph(51, 51)
    blocked = [(i,j) for i in range(10,21) for j in range(10,21)] # Example Rack
    for node in blocked:
        if G.has_node(node):
            G.remove_node(node)
    warehouse_graph = G
    print("Warehouse graph created.")

def shortest_path(start, goal):
    start_node = (int(round(start[0])), int(round(start[1])))
    goal_node = (int(round(goal[0])), int(round(goal[1])))
    
    if not warehouse_graph.has_node(start_node):
        print(f"Start node {start_node} not in graph.")
        return []
    if not warehouse_graph.has_node(goal_node):
        print(f"Goal node {goal_node} not in graph.")
        return []
    try:
        path = nx.astar_path(warehouse_graph, start_node, goal_node, 
                             heuristic=lambda a,b: np.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2), 
                             weight='weight')
        return list(path)
    except nx.NetworkXNoPath:
        return []

#MQTT block
def on_connect(client, userdata, flags, rc):
    print("MQTT Connected")
    client.subscribe("warehouse/anchors/+/data")
    client.subscribe("warehouse/scanner/rack_scan")
def on_message(client, userdata, msg):
    """Sorts messages to the correct handler."""
    try:
        if msg.topic.startswith("warehouse/anchors/"):
            handle_location_message(msg)
        elif msg.topic == "warehouse/scanner/rack_scan":
            handle_rack_scan(msg)
    except Exception as e:
        print(f"Error in on_message: {e}")

def handle_rack_scan(msg):
    print(f"Received rack scan: {msg.payload.decode()}")

def handle_location_message(msg):
    global tag_positions, anchor_data_cache, kalman_filters
    
    try:
        parts = msg.payload.decode().split(',')
        if len(parts) != 6:
             return 
             
        anchor_id, x_str, y_str, dist_str, rssi_str, tag_id = parts
        
        with global_lock:
            if tag_id not in anchor_data_cache:
                anchor_data_cache[tag_id] = {}
            if tag_id not in kalman_filters:
                print(f"New tag {tag_id} detected, creating Kalman filter.")
                kalman_filters[tag_id] = create_kalman_filter()
                with app.app_context():
                    db = get_db()
                    cur = db.cursor()
                    cur.execute("INSERT OR IGNORE INTO tags (id) VALUES (?)", (tag_id,))
                    db.commit()
            anchor_data_cache[tag_id][anchor_id] = {
                'id': anchor_id,
                'dist': float(dist_str),
                'rssi': int(rssi_str)
            }
            current_anchors = list(anchor_data_cache[tag_id].values())
            if len(current_anchors) >= 3:
                pos_raw = trilaterate(current_anchors)
                if pos_raw:
                    kf = kalman_filters[tag_id]
                    kf.predict()
                    kf.update(pos_raw)
                    pos_smooth = kf.x[0:2]
                    tag_positions[tag_id] = (pos_smooth[0], pos_smooth[1])
                    socketio.emit('position_update', {
                        'id': tag_id, 
                        'x': pos_smooth[0], 
                        'y': pos_smooth[1]
                    })
                    with app.app_context():
                        db = get_db()
                        db.execute("UPDATE tags SET last_x = ?, last_y = ?, last_seen = ? WHERE id = ?",
                                   (pos_smooth[0], pos_smooth[1], datetime.now(), tag_id))
                        db.commit()
    except Exception as e:
        print(f"Error in handle_location_message: {e}")
@app.route('/')
def index():
    """Serves the main dashboard page."""
    return render_template('index.html')

@app.route('/path', methods=['POST'])
def get_path_route():
    data = request.json
    tag_id = data.get("tag_id")
    dest_name = data.get("dest_name")

    if not tag_id or not dest_name:
        return jsonify({"error": "tag_id and dest_name are required"}), 400

    with global_lock:
        start_pos = tag_positions.get(tag_id, (25, 25))
    
    db = get_db()
    dest = db.execute("SELECT x, y FROM destinations WHERE name = ?", (dest_name,)).fetchone()
    
    if not dest:
        return jsonify({"error": "Destination not found"}), 404
        
    goal_pos = (dest['x'], dest['y'])
    path = shortest_path(start_pos, goal_pos)
    
    return jsonify({'path': path, 'tag_id': tag_id})

@app.route('/destinations')
def get_destinations():
    """API endpoint to get all destinations from DB."""
    db = get_db()
    cur = db.execute("SELECT name, x, y FROM destinations ORDER BY name")
    dests = cur.fetchall()
    return jsonify([dict(row) for row in dests])


def load_data_from_db():
    """Load anchors and tags from DB into memory on startup."""
    with app.app_context():
        db = get_db()
        for row in db.execute("SELECT id, x, y FROM anchors"):
            anchor_positions[row['id']] = (row['x'], row['y'])
        print(f"Loaded {len(anchor_positions)} anchors from DB.")
        for row in db.execute("SELECT id, last_x, last_y FROM tags"):
            tag_id = row['id']
            tag_positions[tag_id] = (row['last_x'], row['last_y'])
            kf = create_kalman_filter()
            kf.x[0:2] = [row['last_x'], row['last_y']] # Initialize filter
            kalman_filters[tag_id] = kf
        print(f"Loaded {len(kalman_filters)} existing tags from DB.")

if __name__ == '__main__':
    load_data_from_db()
    create_warehouse_graph()
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect("localhost", 1883, 60)
    client.loop_start()
    print("Starting Flask-SocketIO server at http://0.0.0.0:5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)