from flask import Flask, render_template, request, jsonify
import json
import socket
import threading
import time
import os
import uuid
import datetime

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Ensure saves directory exists
SAVES_DIR = "game_saves"
if not os.path.exists(SAVES_DIR):
    os.makedirs(SAVES_DIR)

# Game state
'''gives the starting position of the animals and the hazard state'''
game_state = {
    "players": {
        "dog": {"x": 1, "y": 1},
        "cat": {"x": 2, "y": 1}
    },
    "hazards": [],
    "active_hazards": True,
    "switches": [
        {"x": 10, "y": 5, "active": True, "affects": "hazards"}
    ],
    "game_over": False,
    "players_finished": {"dog": False, "cat": False},
    "celebrating": False,
    "save_id": None,  # Added for save functionality
    "save_name": None,  # Added for save functionality
    "save_time": None   # Added for save functionality
}

# 0 = empty path
# 1 = black wall (impassable)
# 2 = orange wall (only cat can pass)
# 3 = white wall (only dog can pass)
# 4 = start
# 5 = finish
# 6 = switch
maze = [
    [1, 1, 1, 1, 1, 2, 1, 1, 2, 1, 1, 1],
    [4, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1],
    [1, 1, 1, 0, 1, 0, 2, 1, 1, 1, 0, 2],
    [1, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 1],
    [1, 0, 1, 1, 1, 1, 3, 1, 2, 1, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 6, 1],
    [1, 1, 1, 1, 1, 2, 2, 1, 1, 1, 0, 1],
    [1, 0, 0, 0, 0, 0, 3, 0, 0, 0, 0, 1],
    [1, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 1],
    [1, 0, 0, 0, 0, 0, 3, 0, 0, 0, 0, 1],
    [1, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    [1, 0, 0, 0, 0, 0, 0, 5, 1, 1, 1, 1]
]

hazard_positions = [
    {"x": 3, "y": 5},
    {"x": 4, "y": 5},
    {"x": 5, "y": 5},
    {"x": 6, "y": 5},
    {"x": 7, "y": 5},
    {"x": 8, "y": 5},
    {"x": 8, "y": 3},
    {"x": 7, "y": 3},
    {"x": 6, "y": 3},
    {"x": 5, "y": 3},
    {"x": 5, "y": 2},
    {"x": 5, "y": 1},
    {"x": 6, "y": 1},
    {"x": 7, "y": 1},
    {"x": 8, "y": 1},
    {"x": 9, "y": 1},
    {"x": 10, "y": 1},
    {"x": 10, "y": 2},
    {"x": 10, "y": 3},
    {"x": 10, "y": 4},
]

# Check if a move is valid
def is_valid_move(player, x, y):
    # Check if out of bounds
    if x < 0 or y < 0 or x >= len(maze[0]) or y >= len(maze):
        return False
    
    cell = maze[y][x]
    
    # Empty path or switch
    if cell == 0 or cell == 6:
        return True
    
    # Start or finish
    if cell == 4 or cell == 5:
        return True
    
    # Check special walls
    if cell == 2 and player == "cat":  # Orange wall - only cat can pass
        return True
    if cell == 3 and player == "dog":  # White wall - only dog can pass
        return True
    
    # Black wall is impassable
    if cell == 1:
        return False
    
    return False

# Check if player is on a hazard
def check_hazards():
    if not game_state["active_hazards"]:
        return
        
    dog_pos = game_state["players"]["dog"]
    cat_pos = game_state["players"]["cat"]
    
    for hazard in game_state["hazards"]:
        # If player is on an active hazard, reset to start
        if (dog_pos["x"] == hazard["x"] and dog_pos["y"] == hazard["y"]):
            game_state["players"]["dog"] = {"x": 1, "y": 1}
        if (cat_pos["x"] == hazard["x"] and cat_pos["y"] == hazard["y"]):
            game_state["players"]["cat"] = {"x": 2, "y": 1}

# Check if player is on a switch
def check_switches():
    dog_pos = game_state["players"]["dog"]
    cat_pos = game_state["players"]["cat"]
    
    for switch in game_state["switches"]:
        if switch["active"] and (
            (dog_pos["x"] == switch["x"] and dog_pos["y"] == switch["y"]) or
            (cat_pos["x"] == switch["x"] and cat_pos["y"] == switch["y"])
        ):
            switch["active"] = False
            if switch["affects"] == "hazards":
                game_state["active_hazards"] = False

# Check if both players reached the finish
def check_finish():
    for y in range(len(maze)):
        for x in range(len(maze[0])):
            if maze[y][x] == 5:
                dog_pos = game_state["players"]["dog"]
                cat_pos = game_state["players"]["cat"]
                
                if dog_pos["x"] == x and dog_pos["y"] == y:
                    game_state["players_finished"]["dog"] = True
                if cat_pos["x"] == x and cat_pos["y"] == y:
                    game_state["players_finished"]["cat"] = True
                    
                if game_state["players_finished"]["dog"] and game_state["players_finished"]["cat"]:
                    game_state["celebrating"] = True

# Save game state to file
@app.route('/save-game', methods=['POST'])
def save_game():
    data = request.get_json()
    filename = data['filename']
    maze = data['maze']
    game_state = data['gameState']
    
    save_path = os.path.join('saves', f"{filename}.json")
    
    try:
        with open(save_path, 'w') as f:
            json.dump({'maze': maze, 'gameState': game_state}, f)
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error saving game: {e}")
        return jsonify({'success': False, 'message': str(e)})


# Load game state from file
def load_game(save_id):
    save_file = os.path.join(SAVES_DIR, f"{save_id}.txt")
    
    if not os.path.exists(save_file):
        return None
    
    with open(save_file, 'r') as f:
        loaded_state = json.load(f)
    
    # Update current game state
    global game_state
    game_state = loaded_state
    
    return game_state

# Get list of saved games
def get_saved_games():
    saves = []
    
    for filename in os.listdir(SAVES_DIR):
        if filename.endswith(".txt"):
            save_path = os.path.join(SAVES_DIR, filename)
            with open(save_path, 'r') as f:
                save_data = json.load(f)
                saves.append({
                    "save_id": save_data.get("save_id"),
                    "save_name": save_data.get("save_name"),
                    "save_time": save_data.get("save_time")
                })
    
    # Sort by save time (most recent first)
    saves.sort(key=lambda x: x.get("save_time", ""), reverse=True)
    return saves

# Hazard generation thread
def hazard_generator():
    while True:
        if game_state["active_hazards"]:
            game_state["hazards"] = hazard_positions.copy()
        else:
            game_state["hazards"] = []
        time.sleep(1)
        game_state["hazards"] = []
        time.sleep(1)

# Start hazard thread
hazard_thread = threading.Thread(target=hazard_generator, daemon=True)
hazard_thread.start()

@app.route('/')
def index():
    return render_template('maze_game.html')

@app.route('/move', methods=['POST'])
def move():
    data = request.get_json()
    player = data.get('player')
    direction = data.get('direction')
    
    current_pos = game_state["players"][player].copy()
    new_pos = current_pos.copy()
    
    if direction == 'up':
        new_pos["y"] -= 1
    elif direction == 'down':
        new_pos["y"] += 1
    elif direction == 'left':
        new_pos["x"] -= 1
    elif direction == 'right':
        new_pos["x"] += 1
    
    if is_valid_move(player, new_pos["x"], new_pos["y"]):
        game_state["players"][player] = new_pos
        
    check_hazards()
    check_switches()
    check_finish()
    
    return jsonify(game_state)

@app.route('/state', methods=['GET'])
def state():
    return jsonify({
        "game_state": game_state,
        "maze": maze
    })

@app.route('/reset', methods=['POST'])
def reset():
    global game_state
    game_state = {
        "players": {
            "dog": {"x": 1, "y": 1},
            "cat": {"x": 2, "y": 1}
        },
        "hazards": [],
        "active_hazards": True,
        "switches": [
            {"x": 8, "y": 3, "active": True, "affects": "hazards"}
        ],
        "game_over": False,
        "players_finished": {"dog": False, "cat": False},
        "celebrating": False,
        "save_id": None,
        "save_name": None,
        "save_time": None
    }
    
    return jsonify(game_state)

@app.route('/save', methods=['POST'])
def save():
    data = request.get_json()
    save_name = data.get('save_name')
    
    save_data = save_game(save_name)
    
    return jsonify({
        "success": True,
        "message": "Game saved successfully",
        "save_data": save_data
    })

@app.route('/load', methods=['POST'])
def load():
    data = request.get_json()
    save_id = data.get('save_id')
    
    loaded_state = load_game(save_id)
    
    if loaded_state:
        return jsonify({
            "success": True,
            "message": "Game loaded successfully",
            "game_state": loaded_state
        })
    else:
        return jsonify({
            "success": False,
            "message": "Save file not found"
        }), 404

@app.route('/saves', methods=['GET'])
def saves():
    saved_games = get_saved_games()
    
    return jsonify({
        "saves": saved_games
    })

@app.route('/autosave', methods=['POST'])
def autosave():
    # Auto-save without custom name
    save_data = save_game()
    
    return jsonify({
        "success": True,
        "message": "Game auto-saved",
        "save_data": save_data
    })

def find_available_port(start_port=5000, max_attempts=20):
    port = start_port
    for _ in range(max_attempts):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('localhost', port))
            sock.close()
            return port
        except OSError:
            port += 1
    # If we get here, we couldn't find an open port
    raise RuntimeError(f"Could not find an available port after {max_attempts} attempts")

if __name__ == '__main__':
    port = find_available_port()
    print(f"Starting server on port {port}")
    app.run(debug=True, port=port)