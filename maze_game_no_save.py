# maze_game.py
from flask import Flask, render_template, request, jsonify
import json
import socket
import threading
import time
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

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
        {"x": 8, "y": 3, "active": True, "affects": "hazards"}
    ],
    "game_over": False,
    "players_finished": {"dog": False, "cat": False},
    "celebrating": False
}

# 0 = empty path
# 1 = black wall (impassable)
# 2 = orange wall (only cat can pass)
# 3 = white wall (only dog can pass)
# 4 = start
# 5 = finish
# 6 = switch
maze = [
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    [4, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1],
    [1, 1, 1, 0, 1, 0, 1, 1, 1, 1, 0, 1],
    [1, 0, 0, 0, 1, 0, 0, 0, 6, 1, 0, 1],
    [1, 0, 1, 1, 1, 1, 1, 1, 3, 1, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1],
    [1, 1, 1, 1, 1, 2, 2, 1, 1, 1, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    [1, 0, 0, 0, 0, 0, 0, 5, 1, 1, 1, 1]
]

hazard_positions = [
    {"x": 3, "y": 5},
    {"x": 4, "y": 5},
    {"x": 5, "y": 5},
    {"x": 6, "y": 5},
    {"x": 7, "y": 5}
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
    game_state["players"] = {
        "dog": {"x": 1, "y": 1},
        "cat": {"x": 2, "y": 1}
    }
    game_state["active_hazards"] = True
    for switch in game_state["switches"]:
        switch["active"] = True
    game_state["game_over"] = False
    game_state["players_finished"] = {"dog": False, "cat": False}
    game_state["celebrating"] = False
    
    return jsonify(game_state)

def find_available_port(start_port=5000, max_attempts=10):
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