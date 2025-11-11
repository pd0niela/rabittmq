from flask import Flask, request, jsonify
import pika
import json
import random
import threading
import time

app = Flask(__name__)

# CONFIGURARE

RABBITMQ_HOST = 'localhost'

# 5 Cozi RabbitMQ - Fiecare pentru un tip de mesaj
QUEUE_STATISTICS = 'game_statistics'  # Statistici joc
QUEUE_STATE = 'game_state'            # Starea jocului
QUEUE_MOVES = 'game_moves'            # Mișcări jucători
QUEUE_CHAT = 'game_chat'              # Mesaje chat
QUEUE_ACTIONS = 'game_actions'        # Acțiuni generale

GRID_SIZE = 15
MAX_BOMBS = 5
PLAYER_EMOJIS = ['❤️', '⭐', '🌙', '🔥', '💎', '🌸', '🎵', '🦋']

# STAREA JOCULUI
game = {
    'phase': 'setup',
    'players': {},
    'bombs': [],
    'items': [],
    'chat': [],
    'current_turn': None,
    'player_order': [],
    'available_emojis': PLAYER_EMOJIS.copy(),
    'found_items': [],
    'winner': None
}


# RABBITMQ - PRODUCER
def send_to_queue(queue_name, data):
    """Trimite mesaj în coada specificată"""
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBITMQ_HOST, heartbeat=600, blocked_connection_timeout=300)
        )
        channel = connection.channel()
        channel.queue_declare(queue=queue_name, durable=True)
        channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=json.dumps(data),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        connection.close()
        print(f'📤 [{queue_name}] Mesaj trimis: {data.get("action", data.get("type", "update"))}')
    except Exception as e:
        print(f'❌ Eroare RabbitMQ [{queue_name}]: {e}')

# RABBITMQ - CONSUMERS

def statistics_consumer():
    """Consumer pentru statistici"""
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBITMQ_HOST, heartbeat=600, blocked_connection_timeout=300)
        )
        channel = connection.channel()
        channel.queue_declare(queue=QUEUE_STATISTICS, durable=True)
        channel.basic_qos(prefetch_count=1)

        def callback(ch, method, properties, body):
            try:
                data = json.loads(body)
                print(f'📊 [STATISTICS] {data}')
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as e:
                print(f'❌ Statistics Error: {e}')
                ch.basic_ack(delivery_tag=method.delivery_tag)

        channel.basic_consume(queue=QUEUE_STATISTICS, on_message_callback=callback)
        print('📊 [STATISTICS CONSUMER] Pornit!')
        channel.start_consuming()
    except Exception as e:
        print(f'❌ Statistics Consumer Error: {e}')

def state_consumer():
    """Consumer pentru starea jocului"""
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBITMQ_HOST, heartbeat=600, blocked_connection_timeout=300)
        )
        channel = connection.channel()
        channel.queue_declare(queue=QUEUE_STATE, durable=True)
        channel.basic_qos(prefetch_count=1)

        def callback(ch, method, properties, body):
            try:
                data = json.loads(body)
                print(f'🎮 [STATE] {data}')
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as e:
                print(f'❌ State Error: {e}')
                ch.basic_ack(delivery_tag=method.delivery_tag)

        channel.basic_consume(queue=QUEUE_STATE, on_message_callback=callback)
        print('🎮 [STATE CONSUMER] Pornit!')
        channel.start_consuming()
    except Exception as e:
        print(f'❌ State Consumer Error: {e}')

def moves_consumer():
    """Consumer pentru mișcări"""
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBITMQ_HOST, heartbeat=600, blocked_connection_timeout=300)
        )
        channel = connection.channel()
        channel.queue_declare(queue=QUEUE_MOVES, durable=True)
        channel.basic_qos(prefetch_count=1)

        def callback(ch, method, properties, body):
            try:
                data = json.loads(body)
                action = data.get('action')
                player = data.get('player')

                if action == 'move':
                    direction = data.get('direction')
                    move_player(player, direction)
                    print(f'🎯 [MOVES] {player} s-a mișcat: {direction}')
                elif action == 'place_bomb':
                    x, y = data.get('x'), data.get('y')
                    place_bomb_setup(player, x, y)
                    print(f'💣 [MOVES] {player} a plasat bombă: ({x}, {y})')

                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as e:
                print(f'❌ Moves Error: {e}')
                ch.basic_ack(delivery_tag=method.delivery_tag)

        channel.basic_consume(queue=QUEUE_MOVES, on_message_callback=callback)
        print('🎯 [MOVES CONSUMER] Pornit!')
        channel.start_consuming()
    except Exception as e:
        print(f'❌ Moves Consumer Error: {e}')

def chat_consumer():
    """Consumer pentru chat"""
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBITMQ_HOST, heartbeat=600, blocked_connection_timeout=300)
        )
        channel = connection.channel()
        channel.queue_declare(queue=QUEUE_CHAT, durable=True)
        channel.basic_qos(prefetch_count=1)

        def callback(ch, method, properties, body):
            try:
                data = json.loads(body)
                player = data.get('player')
                message = data.get('message', '')
                add_chat(player, message)
                print(f'💬 [CHAT] {player}: {message}')
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as e:
                print(f'❌ Chat Error: {e}')
                ch.basic_ack(delivery_tag=method.delivery_tag)

        channel.basic_consume(queue=QUEUE_CHAT, on_message_callback=callback)
        print('💬 [CHAT CONSUMER] Pornit!')
        channel.start_consuming()
    except Exception as e:
        print(f'❌ Chat Consumer Error: {e}')

def actions_consumer():
    """Consumer pentru acțiuni generale"""
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBITMQ_HOST, heartbeat=600, blocked_connection_timeout=300)
        )
        channel = connection.channel()
        channel.queue_declare(queue=QUEUE_ACTIONS, durable=True)
        channel.basic_qos(prefetch_count=1)

        def callback(ch, method, properties, body):
            try:
                data = json.loads(body)
                action = data.get('action')
                player = data.get('player')

                if action == 'join':
                    add_player(player)
                    print(f'✅ [ACTIONS] {player} a intrat în joc!')

                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as e:
                print(f'❌ Actions Error: {e}')
                ch.basic_ack(delivery_tag=method.delivery_tag)

        channel.basic_consume(queue=QUEUE_ACTIONS, on_message_callback=callback)
        print('⚡ [ACTIONS CONSUMER] Pornit!')
        channel.start_consuming()
    except Exception as e:
        print(f'❌ Actions Consumer Error: {e}')


# LOGICA JOCULUI

def add_player(name):
    if name in game['players']:
        return

    emoji = game['available_emojis'].pop(0) if game['available_emojis'] else '🎮'

    # Găsește poziție liberă
    for _ in range(100):
        x = random.randint(0, GRID_SIZE-1)
        y = random.randint(0, GRID_SIZE-1)

        occupied = any(p['x'] == x and p['y'] == y for p in game['players'].values())
        if not occupied:
            break

    game['players'][name] = {
        'x': x,
        'y': y,
        'score': 0,
        'emoji': emoji,
        'hp': 3,
        'bombs_placed': 0,
        'last_seen': time.time()
    }

    game['player_order'].append(name)

    if len(game['player_order']) == 1:
        game['current_turn'] = name

    add_chat('SISTEM', f'{emoji} {name} intră în joc!')

    # RabbitMQ: Notificare stare
    send_to_queue(QUEUE_STATE, {
        'type': 'player_join',
        'player': name,
        'emoji': emoji,
        'total_players': len(game['players'])
    })

def place_bomb_setup(player_name, x, y):
    if player_name not in game['players']:
        return

    player = game['players'][player_name]

    if player['bombs_placed'] >= MAX_BOMBS:
        return

    if not (0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE):
        return

    if any(bomb['x'] == x and bomb['y'] == y for bomb in game['bombs']):
        return

    game['bombs'].append({'x': x, 'y': y, 'owner': player_name})
    player['bombs_placed'] += 1

    add_chat('SISTEM', f'💣 {player_name} plasează bomba {player["bombs_placed"]}/{MAX_BOMBS}')

    if all(p['bombs_placed'] >= MAX_BOMBS for p in game['players'].values()):
        start_game()

def start_game():
    game['phase'] = 'playing'
    generate_hidden_items()

    num_players = len(game['players'])
    total_bombs = len(game['bombs'])
    total_items = len(game['items'])

    add_chat('SISTEM', '🎮 JOCUL ÎNCEPE! Items-urile sunt ascunse!')
    add_chat('SISTEM', f'📊 {num_players} jucători | {total_bombs} bombe | {total_items} items')
    add_chat('SISTEM', f'▶️ Turul lui {game["current_turn"]}')

    # RabbitMQ: Notificare start
    send_to_queue(QUEUE_STATE, {
        'type': 'phase_change',
        'phase': 'playing',
        'num_players': num_players,
        'total_bombs': total_bombs,
        'total_items': total_items
    })

def generate_hidden_items():
    game['items'] = []
    num_players = len(game['players'])
    num_items = num_players * 10

    occupied = set()
    for p in game['players'].values():
        occupied.add((p['x'], p['y']))
    for b in game['bombs']:
        occupied.add((b['x'], b['y']))

    item_distribution = (
        ['apple'] * (num_items // 2) +
        ['star'] * (num_items // 4) +
        ['heart'] * (num_items // 5) +
        ['bomb_extra'] * (num_items // 10) +
        ['diamond'] * (num_items // 20)
    )

    while len(item_distribution) < num_items:
        item_distribution.append(random.choice(['apple', 'star', 'heart']))

    random.shuffle(item_distribution)

    while len(game['items']) < num_items and item_distribution:
        x = random.randint(0, GRID_SIZE-1)
        y = random.randint(0, GRID_SIZE-1)

        if (x, y) not in occupied:
            item_type = item_distribution.pop()
            game['items'].append({'x': x, 'y': y, 'type': item_type})
            occupied.add((x, y))

def move_player(player_name, direction):
    if game['phase'] != 'playing':
        return

    if player_name not in game['players']:
        return

    if game['current_turn'] != player_name:
        return

    player = game['players'][player_name]
    old_x, old_y = player['x'], player['y']
    new_x, new_y = old_x, old_y

    if direction == 'UP':
        new_y = max(0, old_y - 1)
    elif direction == 'DOWN':
        new_y = min(GRID_SIZE-1, old_y + 1)
    elif direction == 'LEFT':
        new_x = max(0, old_x - 1)
    elif direction == 'RIGHT':
        new_x = min(GRID_SIZE-1, old_x + 1)

    if old_x == new_x and old_y == new_y:
        return

    player['x'] = new_x
    player['y'] = new_y

    # Verifică bombă
    for bomb in game['bombs'][:]:
        if bomb['x'] == new_x and bomb['y'] == new_y:
            if bomb['owner'] != player_name:
                player['hp'] -= 1
                player['score'] = max(0, player['score'] - 1)
                add_chat('SISTEM', f'💣 {player_name} lovește o bombă! HP: {player["hp"]}')

                if player['hp'] <= 0:
                    add_chat('SISTEM', f'💀 {player_name} ELIMINAT!')
                    eliminate_player(player_name)
                    next_turn()
                    return

            game['bombs'].remove(bomb)
            break

    # Verifică items
    for item in game['items'][:]:
        if item['x'] == new_x and item['y'] == new_y:
            handle_item(player_name, player, item)
            game['items'].remove(item)
            break

    if player_name in game['players']:
        next_turn()

def handle_item(player_name, player, item):
    game['found_items'].append({
        'x': item['x'],
        'y': item['y'],
        'type': item['type'],
        'time': time.time()
    })

    if item['type'] == 'apple':
        player['score'] += 1
        add_chat('SISTEM', f'🍎 {player_name} a găsit un măr! +1 | Total: {player["score"]}')
    elif item['type'] == 'star':
        player['score'] += 3
        add_chat('SISTEM', f'⭐ {player_name} a găsit o stea! +3 | Total: {player["score"]}')
    elif item['type'] == 'diamond':
        player['score'] += 5
        add_chat('SISTEM', f'💎 {player_name} a găsit un diamant! +5 | Total: {player["score"]}')
    elif item['type'] == 'heart':
        player['hp'] = min(5, player['hp'] + 1)
        add_chat('SISTEM', f'❤️ {player_name} a găsit o inimă! +1 HP | HP: {player["hp"]}')
    elif item['type'] == 'bomb_extra':
        player['hp'] -= 1
        player['score'] = max(0, player['score'] - 1)
        add_chat('SISTEM', f'💥 {player_name} a găsit o bombă! -1 HP')

        if player['hp'] <= 0:
            add_chat('SISTEM', f'💀 {player_name} ELIMINAT!')
            eliminate_player(player_name)
            return

    # RabbitMQ: Statistici
    send_to_queue(QUEUE_STATISTICS, {
        'type': 'item_found',
        'player': player_name,
        'item_type': item['type'],
        'score': player['score'],
        'hp': player['hp']
    })

    check_game_over()

def eliminate_player(player_name):
    if player_name not in game['players']:
        return

    emoji = game['players'][player_name]['emoji']

    if emoji in PLAYER_EMOJIS:
        game['available_emojis'].append(emoji)

    if player_name in game['player_order']:
        game['player_order'].remove(player_name)

    del game['players'][player_name]

    if game['current_turn'] == player_name:
        if game['player_order']:
            game['current_turn'] = game['player_order'][0]
        else:
            game['current_turn'] = None

    check_game_over()

def next_turn():
    if not game['player_order']:
        game['current_turn'] = None
        check_game_over()
        return

    if game['current_turn'] not in game['player_order']:
        game['current_turn'] = game['player_order'][0]
        add_chat('SISTEM', f'▶️ Turul lui {game["current_turn"]}')
        return

    try:
        current_index = game['player_order'].index(game['current_turn'])
        next_index = (current_index + 1) % len(game['player_order'])
        game['current_turn'] = game['player_order'][next_index]
        add_chat('SISTEM', f'▶️ Turul lui {game["current_turn"]}')
    except ValueError:
        if game['player_order']:
            game['current_turn'] = game['player_order'][0]

def check_game_over():
    if game['phase'] != 'playing':
        return

    all_items_found = len(game['items']) == 0
    one_player = len(game['players']) == 1
    no_players = len(game['players']) == 0

    if all_items_found or one_player or no_players:
        game['phase'] = 'finished'

        if no_players:
            add_chat('SISTEM', '🎮 Joc terminat! Toți eliminați!')
            return

        if game['players']:
            max_score = max(p['score'] for p in game['players'].values())
            winners = [name for name, p in game['players'].items() if p['score'] == max_score]

            if len(winners) == 1:
                game['winner'] = winners[0]
                winner_emoji = game['players'][winners[0]]['emoji']
                add_chat('SISTEM', f'🎉 {winner_emoji} {winners[0]} A CÂȘTIGAT cu {max_score} puncte!')
            else:
                winner_names = ', '.join(winners)
                add_chat('SISTEM', f'🎉 EGALITATE! {winner_names} cu {max_score} puncte!')
                game['winner'] = winner_names

def add_chat(sender, message):
    game['chat'].append({
        'sender': sender,
        'message': message,
        'time': time.strftime('%H:%M:%S')
    })
    if len(game['chat']) > 40:
        game['chat'] = game['chat'][-40:]

def remove_player(player_name):
    if player_name not in game['players']:
        return

    emoji = game['players'][player_name]['emoji']

    if emoji in PLAYER_EMOJIS:
        game['available_emojis'].append(emoji)

    if player_name in game['player_order']:
        game['player_order'].remove(player_name)

    if game['phase'] == 'setup':
        game['bombs'] = [b for b in game['bombs'] if b['owner'] != player_name]

    del game['players'][player_name]

    if game['current_turn'] == player_name:
        if game['player_order']:
            game['current_turn'] = game['player_order'][0]
        else:
            game['current_turn'] = None

    add_chat('SISTEM', f'{emoji} {player_name} a părăsit jocul!')
    check_game_over()

def cleanup_inactive_players():
    while True:
        time.sleep(5)
        current_time = time.time()
        inactive = [
            name for name, player in game['players'].items()
            if current_time - player.get('last_seen', current_time) > 10
        ]

        for player_name in inactive:
            remove_player(player_name)

        game['found_items'] = [
            item for item in game['found_items']
            if current_time - item['time'] < 3
        ]

# FLASK ROUTES

@app.route('/')
def index():
    return HTML

@app.route('/api/join', methods=['POST'])
def api_join():
    name = request.json.get('name', 'Anonim')
    send_to_queue(QUEUE_ACTIONS, {'action': 'join', 'player': name})
    return jsonify({'ok': True})

@app.route('/api/place_bomb', methods=['POST'])
def api_place_bomb():
    data = request.json
    send_to_queue(QUEUE_MOVES, {
        'action': 'place_bomb',
        'player': data.get('player'),
        'x': data.get('x'),
        'y': data.get('y')
    })
    return jsonify({'ok': True})

@app.route('/api/move', methods=['POST'])
def api_move():
    data = request.json
    send_to_queue(QUEUE_MOVES, {
        'action': 'move',
        'player': data.get('player'),
        'direction': data.get('direction')
    })
    return jsonify({'ok': True})

@app.route('/api/chat', methods=['POST'])
def api_chat():
    data = request.json
    send_to_queue(QUEUE_CHAT, {
        'action': 'chat',
        'player': data.get('player'),
        'message': data.get('message')
    })
    return jsonify({'ok': True})

@app.route('/api/state', methods=['GET'])
def api_state():
    player_name = request.args.get('player', '')
    state = dict(game)

    if game['phase'] == 'setup' and player_name:
        state['bombs'] = [b for b in game['bombs'] if b['owner'] == player_name]

    return jsonify(state)

@app.route('/api/heartbeat', methods=['POST'])
def api_heartbeat():
    player_name = request.json.get('player', '')
    if player_name in game['players']:
        game['players'][player_name]['last_seen'] = time.time()
    return jsonify({'ok': True})

@app.route('/api/leave', methods=['POST'])
def api_leave():
    player_name = request.json.get('player', '')
    remove_player(player_name)
    return jsonify({'ok': True})

@app.route('/api/reset', methods=['POST'])
def api_reset():
    """Resetează jocul complet"""
    global game
    game['phase'] = 'setup'
    game['players'] = {}
    game['bombs'] = []
    game['items'] = []
    game['chat'] = []
    game['current_turn'] = None
    game['player_order'] = []
    game['available_emojis'] = PLAYER_EMOJIS.copy()
    game['found_items'] = []
    game['winner'] = None

    add_chat('SISTEM', '🔄 Joc resetat! Toți jucătorii pot reintra!')
    return jsonify({'ok': True})

HTML = '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>🎮 Joc RabbitMQ</title>
    <style>
        body { margin: 0; padding: 20px; background: #e8eaf6; color: #333; font-family: Arial; }
        .container { max-width: 900px; margin: 0 auto; background: white; padding: 25px; border-radius: 15px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
        h1 { text-align: center; color: #3f51b5; margin-bottom: 10px; font-size: 42px; }
        .player-info { text-align: center; font-size: 28px; padding: 15px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 10px; margin: 15px 0; font-weight: bold; }
        .phase { text-align: center; font-size: 24px; font-weight: bold; padding: 15px; background: #ffeb3b; color: #333; border-radius: 10px; margin: 20px 0; }
        .grid { display: grid; grid-template-columns: repeat(15, 45px); gap: 2px; margin: 20px auto; width: fit-content; }
        .cell { width: 45px; height: 45px; background: #f5f5f5; border: 2px solid #ddd; display: flex; align-items: center; justify-content: center; font-size: 24px; border-radius: 5px; cursor: pointer; transition: all 0.2s; position: relative; }
        .cell:hover { background: #e0e0e0; transform: scale(1.1); }
        .cell.explored { background: #e8f5e9; border: 2px solid #a5d6a7; }
        .cell.found-item { background: #c8e6c9 !important; animation: foundItemPulse 1s ease-out; }
        @keyframes foundItemPulse {
            0% { transform: scale(1); background: #4caf50; box-shadow: 0 0 0 0 rgba(76, 175, 80, 0.7); }
            50% { transform: scale(1.2); background: #81c784; box-shadow: 0 0 20px 10px rgba(76, 175, 80, 0.3); }
            100% { transform: scale(1); background: #c8e6c9; box-shadow: 0 0 0 0 rgba(76, 175, 80, 0); }
        }
        .found-icon { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 32px; animation: iconPop 0.5s ease-out; }
        @keyframes iconPop {
            0% { transform: translate(-50%, -50%) scale(0); opacity: 0; }
            50% { transform: translate(-50%, -50%) scale(1.5); }
            100% { transform: translate(-50%, -50%) scale(1); opacity: 1; }
        }
        .controls { display: grid; grid-template-columns: repeat(3, 100px); gap: 10px; margin: 20px auto; width: fit-content; }
        .btn { padding: 15px; border: none; border-radius: 10px; font-size: 18px; cursor: pointer; font-weight: bold; background: #2196f3; color: white; transition: transform 0.1s; }
        .btn:hover { transform: scale(1.05); background: #1976d2; }
        .btn:active { transform: scale(0.95); }
        .info { background: #f5f5f5; padding: 15px; border-radius: 10px; margin: 10px 0; }
        .chat { height: 150px; overflow-y: auto; background: #fafafa; padding: 10px; border-radius: 5px; margin: 10px 0; font-size: 14px; }
        .login { text-align: center; margin: 20px 0; }
        .login input { padding: 12px; font-size: 18px; border-radius: 8px; border: 2px solid #ddd; margin-right: 10px; }
        .login button { padding: 12px 25px; font-size: 18px; border-radius: 8px; border: none; background: #4caf50; color: white; cursor: pointer; font-weight: bold; }
        .login button:hover { background: #45a049; }
        .hidden { display: none !important; }
        .player-item { padding: 10px; margin: 5px 0; background: #f5f5f5; border-radius: 5px; }
        .current-turn { background: #fff9c4; border: 2px solid #fbc02d; }
        .notification { position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); background: rgba(0,0,0,0.95); color: white; padding: 40px 60px; border-radius: 20px; font-size: 36px; font-weight: bold; z-index: 1000; animation: fadeIn 0.3s; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        .winner-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 2000; align-items: center; justify-content: center; animation: fadeIn 0.5s; }
        .winner-message { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 60px 80px; border-radius: 30px; text-align: center; color: white; }
        .winner-message h1 { font-size: 72px; margin: 0 0 20px 0; }
        .winner-message p { font-size: 36px; margin: 20px 0; }
        .winner-emoji { font-size: 120px; margin: 20px 0; animation: bounce 1s infinite; }
        @keyframes bounce { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-20px); } }
        .winner-btn { padding: 15px 40px; font-size: 20px; margin: 0 10px; border: none; border-radius: 10px; cursor: pointer; font-weight: bold; transition: transform 0.2s, box-shadow 0.2s; }
        .winner-btn:hover { transform: scale(1.1); box-shadow: 0 8px 16px rgba(0,0,0,0.3); }
        .winner-btn:active { transform: scale(0.95); }
        .btn-yes { background: #4caf50; color: white; }
        .btn-no { background: #f44336; color: white; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎮 JOC MULTIPLAYER RABBITMQ 🐰</h1>

        <div id="playerInfo" class="player-info hidden"></div>

        <div id="login" class="login">
            <input type="text" id="nameInput" placeholder="Numele tău" maxlength="15">
            <button onclick="join()">INTRĂ ÎN JOC</button>
        </div>

        <div id="game" class="hidden">
            <div id="phaseInfo" class="phase"></div>
            <div id="grid" class="grid"></div>

            <div id="setupControls">
                <p style="text-align: center; font-size: 18px;">👆 Click pe grilă pentru a plasa bombe!</p>
            </div>

            <div id="playControls" class="hidden">
                <div class="controls">
                    <div></div>
                    <button class="btn" onclick="move('UP')">⬆️</button>
                    <div></div>
                    <button class="btn" onclick="move('LEFT')">⬅️</button>
                    <button class="btn" onclick="move('DOWN')">⬇️</button>
                    <button class="btn" onclick="move('RIGHT')">➡️</button>
                </div>
            </div>

            <div id="itemsCounter" class="info hidden">
                <h3>🎯 Items rămase:</h3>
                <div id="itemsList" style="font-size: 18px; font-weight: bold;"></div>
            </div>

            <div class="info">
                <h3>👥 Jucători:</h3>
                <div id="players"></div>
            </div>

            <div class="info">
                <h3>💬 Chat:</h3>
                <div id="chat" class="chat"></div>
                <input type="text" id="chatInput" placeholder="Mesaj..." style="width: 80%; padding: 8px; border-radius: 5px;">
                <button onclick="sendChat()" style="padding: 8px 15px; border: none; background: #3498db; color: white; border-radius: 5px; cursor: pointer;">📤</button>
            </div>

            <div class="info">
                <h3>📖 Reguli:</h3>
                <p><strong>FAZA 1:</strong> Plasează 5 bombe strategice (bombele TALE nu îți fac rău!)</p>
                <p><strong>FAZA 2:</strong> Joc pe rând! Găsește items ascunse!</p>
                <p><strong>Items:</strong></p>
                <p>🍎 Măr +1 punct | ⭐ Stea +3 puncte | 💎 Diamant +5 puncte | ❤️ Inimă +1 HP</p>
                <p><strong>Pericole:</strong></p>
                <p>💣 Bomba ALTUI jucător -1 HP | 💥 Item bombă (capcană) -1 HP</p>
            </div>
        </div>
    </div>

    <div id="winnerOverlay" class="winner-overlay hidden"></div>

    <script>
        let myName = '';
        let gridData = [];
        let lastChatLength = 0;
        let exploredCells = new Set(); // Păstrează celulele explorate

        function join() {
            myName = document.getElementById('nameInput').value.trim();
            if (!myName) { alert('Introdu un nume!'); return; }

            fetch('/api/join', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({name: myName})
            });

            document.getElementById('login').classList.add('hidden');
            document.getElementById('game').classList.remove('hidden');
            updateGame();
            startHeartbeat();
        }

        function startHeartbeat() {
            setInterval(() => {
                if (myName) {
                    fetch('/api/heartbeat', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({player: myName})
                    });
                }
            }, 3000);
        }

        window.addEventListener('beforeunload', () => {
            if (myName) {
                const blob = new Blob([JSON.stringify({player: myName})], {type: 'application/json'});
                navigator.sendBeacon('/api/leave', blob);
            }
        });

        function showNotification(message) {
            const notif = document.createElement('div');
            notif.className = 'notification';
            notif.textContent = message;
            document.body.appendChild(notif);
            setTimeout(() => { notif.remove(); }, 2000);
        }

        function placeBomb(x, y) {
            if (!myName) return;
            fetch('/api/place_bomb', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({player: myName, x: x, y: y})
            });
        }

        function move(direction) {
            if (!myName) return;
            fetch('/api/move', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({player: myName, direction: direction})
            });
        }

        function sendChat() {
            const input = document.getElementById('chatInput');
            const msg = input.value.trim();
            if (!msg) return;
            fetch('/api/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({player: myName, message: msg})
            });
            input.value = '';
        }

        document.getElementById('chatInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendChat();
        });

        document.addEventListener('keydown', (e) => {
            if (!myName || gridData.phase !== 'playing') return;
            if (e.key === 'ArrowUp') move('UP');
            else if (e.key === 'ArrowDown') move('DOWN');
            else if (e.key === 'ArrowLeft') move('LEFT');
            else if (e.key === 'ArrowRight') move('RIGHT');
        });

        function updateGame() {
            fetch(`/api/state?player=${encodeURIComponent(myName)}`)
                .then(r => r.json())
                .then(state => {
                    gridData = state;
                    renderGame(state);
                });
            setTimeout(updateGame, 500);
        }

        function renderGame(state) {
            renderPlayerInfo(state);
            renderPhase(state);
            renderGrid(state);
            renderItemsCounter(state);
            renderPlayers(state);
            renderChat(state);
        }

        function renderPlayerInfo(state) {
            const playerInfoDiv = document.getElementById('playerInfo');

            if (!myName || !state.players[myName]) {
                playerInfoDiv.classList.add('hidden');
                return;
            }

            const myPlayer = state.players[myName];
            playerInfoDiv.classList.remove('hidden');
            playerInfoDiv.innerHTML = `${myPlayer.emoji} TU EȘTI: <span style="font-size: 32px;">${myName}</span> ${myPlayer.emoji}`;
        }

        function renderPhase(state) {
            const phaseDiv = document.getElementById('phaseInfo');

            if (state.phase === 'setup') {
                phaseDiv.textContent = '📍 FAZA 1: PLASARE BOMBE';
                document.getElementById('setupControls').classList.remove('hidden');
                document.getElementById('playControls').classList.add('hidden');
                document.getElementById('itemsCounter').classList.add('hidden');
            } else if (state.phase === 'playing') {
                phaseDiv.textContent = '🎮 FAZA 2: JOC PE RÂND';
                document.getElementById('setupControls').classList.add('hidden');
                document.getElementById('playControls').classList.remove('hidden');
                document.getElementById('itemsCounter').classList.remove('hidden');
            } else if (state.phase === 'finished') {
                phaseDiv.textContent = '🏆 JOC TERMINAT!';
                document.getElementById('setupControls').classList.add('hidden');
                document.getElementById('playControls').classList.add('hidden');
                showWinner(state);
            }
        }

        function showWinner(state) {
            if (!state.winner) return;

            const overlay = document.getElementById('winnerOverlay');
            let winnerEmoji = '🎉';
            if (state.players[state.winner]) {
                winnerEmoji = state.players[state.winner].emoji;
            }

            overlay.innerHTML = `
                <div class="winner-message">
                    <h1>🎉 FELICITĂRI! 🎉</h1>
                    <div class="winner-emoji">${winnerEmoji}</div>
                    <p>${state.winner} A CÂȘTIGAT!</p>
                    <div style="margin-top: 40px;">
                        <p style="font-size: 24px; margin-bottom: 20px;">Vrei să joci din nou?</p>
                        <button onclick="resetGame()" class="winner-btn btn-yes">✅ DA</button>
                        <button onclick="closeWinner()" class="winner-btn btn-no">❌ NU</button>
                    </div>
                </div>
            `;
            overlay.style.display = 'flex';
            overlay.classList.remove('hidden');
        }

        function resetGame() {
            fetch('/api/reset', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'}
            }).then(() => {
                // Resetează tot pe client
                document.getElementById('winnerOverlay').classList.add('hidden');
                document.getElementById('game').classList.add('hidden');
                document.getElementById('login').classList.remove('hidden');
                myName = '';
                lastChatLength = 0;
                exploredCells.clear(); // Resetează celulele explorate
            });
        }

        function closeWinner() {
            // Nu face nimic, doar închide overlay-ul
            document.getElementById('winnerOverlay').classList.add('hidden');
        }

        function renderItemsCounter(state) {
            if (state.phase !== 'playing' && state.phase !== 'finished') return;

            const itemsDiv = document.getElementById('itemsList');
            const total = state.items.length;

            itemsDiv.innerHTML = `📦 <strong>${total} items</strong> rămase`;
        }

        function renderGrid(state) {
            const grid = document.getElementById('grid');
            grid.innerHTML = '';

            const cells = Array(15).fill().map(() => Array(15).fill('⬜'));
            const foundItemsMap = {};

            if (state.found_items) {
                state.found_items.forEach(item => {
                    const key = `${item.x},${item.y}`;
                    foundItemsMap[key] = item.type;
                    exploredCells.add(key); // Marchează ca explorată
                });
            }

            if (state.phase === 'setup') {
                state.bombs.forEach(bomb => {
                    cells[bomb.y][bomb.x] = '💣';
                });
            }

            // Mai întâi adaugă jucătorii
            Object.values(state.players).forEach(p => {
                cells[p.y][p.x] = p.emoji;
            });

            for (let y = 0; y < 15; y++) {
                for (let x = 0; x < 15; x++) {
                    const div = document.createElement('div');
                    div.className = 'cell';

                    const key = `${x},${y}`;
                    const foundItem = foundItemsMap[key];
                    const isExplored = exploredCells.has(key);

                    if (foundItem) {
                        // Afișează item-ul găsit cu animație (pentru 3 secunde)
                        div.classList.add('found-item');
                        const iconMap = {
                            'apple': '🍎',
                            'star': '⭐',
                            'diamond': '💎',
                            'heart': '❤️',
                            'bomb_extra': '💥'
                        };
                        const icon = document.createElement('span');
                        icon.className = 'found-icon';
                        icon.textContent = iconMap[foundItem] || '✨';
                        div.appendChild(icon);
                    } else if (isExplored) {
                        // Celulă explorată - arată-o ca goală dar marcată
                        div.classList.add('explored');
                        div.textContent = '✓';
                        div.style.color = '#4caf50';
                        div.style.fontSize = '20px';
                    } else {
                        // Afișează conținutul normal
                        div.textContent = cells[y][x];
                    }

                    if (state.phase === 'setup') {
                        div.onclick = () => placeBomb(x, y);
                    }

                    grid.appendChild(div);
                }
            }
        }

        function renderPlayers(state) {
            const div = document.getElementById('players');
            div.innerHTML = '';

            Object.entries(state.players).forEach(([name, p]) => {
                const item = document.createElement('div');
                item.className = 'player-item';

                if (state.phase === 'playing' && name === state.current_turn) {
                    item.classList.add('current-turn');
                }

                let info = `${p.emoji} <strong>${name}</strong>: `;

                if (state.phase === 'setup') {
                    info += `💣 ${p.bombs_placed}/5 bombe`;
                } else {
                    info += `⭐ ${p.score} puncte | ${'❤️'.repeat(p.hp)} (${p.hp} HP)`;
                }

                if (name === state.current_turn && state.phase === 'playing') {
                    info += ' <strong>👈 TURUL TĂU</strong>';
                }

                item.innerHTML = info;
                div.appendChild(item);
            });
        }

        function renderChat(state) {
            const div = document.getElementById('chat');

            if (state.chat.length > lastChatLength) {
                const newMessages = state.chat.slice(lastChatLength);
                newMessages.forEach(msg => {
                    if (msg.sender === 'SISTEM') {
                        // Mesaje ELIMINARE - pentru TOȚI jucătorii
                        if (msg.message.includes('ELIMINAT')) {
                            // Extrage numele jucătorului eliminat
                            const eliminatedPlayer = msg.message.split(' ')[1];
                            showNotification(`💀 ${eliminatedPlayer} A FOST ELIMINAT!`);
                        }
                        // Mesaje despre PROPRIILE tale acțiuni
                        else if (msg.message.includes(myName)) {
                            // Items găsite
                            if (msg.message.includes('a găsit un măr')) showNotification('🍎 +1 PUNCT!');
                            else if (msg.message.includes('a găsit o stea')) showNotification('⭐ +3 PUNCTE!');
                            else if (msg.message.includes('a găsit un diamant')) showNotification('💎 +5 PUNCTE!');
                            else if (msg.message.includes('a găsit o inimă')) showNotification('❤️ +1 HP!');
                            else if (msg.message.includes('a găsit o bombă')) showNotification('💥 -1 HP!');
                            // Damage de la bombe adversare
                            else if (msg.message.includes('lovește o bombă')) showNotification('💣 -1 HP!');
                        }
                    }
                });
                lastChatLength = state.chat.length;
            }

            div.innerHTML = state.chat.slice(-10).map(m =>
                `[${m.time}] <b>${m.sender}:</b> ${m.message}`
            ).join('<br>');
            div.scrollTop = div.scrollHeight;
        }
    </script>
</body>
</html>'''

# MAIN
if __name__ == '__main__':
    print('=' * 80)
    print('🎮 JOC MULTIPLAYER CU RABBITMQ')
    print('=' * 80)
    print('📊 Demonstrație RabbitMQ cu 5 cozi separate:')
    print('   1️⃣  game_statistics - Statistici joc')
    print('   2️⃣  game_state      - Starea jocului')
    print('   3️⃣  game_moves      - Mișcări jucători')
    print('   4️⃣  game_chat       - Mesaje chat')
    print('   5️⃣  game_actions    - Acțiuni generale')
    print('=' * 80)

    # Pornește toate consumer-ele RabbitMQ în thread-uri separate
    threads = [
        threading.Thread(target=statistics_consumer, daemon=True, name='Statistics'),
        threading.Thread(target=state_consumer, daemon=True, name='State'),
        threading.Thread(target=moves_consumer, daemon=True, name='Moves'),
        threading.Thread(target=chat_consumer, daemon=True, name='Chat'),
        threading.Thread(target=actions_consumer, daemon=True, name='Actions'),
        threading.Thread(target=cleanup_inactive_players, daemon=True, name='Cleanup')
    ]

    for thread in threads:
        thread.start()
        print(f'✅ Thread {thread.name} pornit!')
        time.sleep(0.3)

    print('=' * 80)
    print('🌐 Deschide în browser: http://localhost:5000')
    print('=' * 80)

    app.run(host='0.0.0.0', port=5000, debug=False)
