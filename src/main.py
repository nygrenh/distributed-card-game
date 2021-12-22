import flask
from flask import request
import threading
import requests
from threading import Lock, Thread
import pdb
import traceback
from classes import DealResultsBroadcastRequest, Deck, DoubleEncryptedDeckRequest, GamePhase, GameWinnerVerificationResultRequest, JoinRequest, JoinResponse, NewNodeListMessage, Player, PlzHelpWithEncryptingDeckRequest, PlzHelpWithEncryptingDeckResponse, ReverseBullyElectionResponse, ShareKeyRequest, WinnerRequest
from command_line import CommandLoop, broadcast_new_node_list, verify_game_and_participate_in_fairness_voting
import state as state
import reverse_bully as bully

from flask_middleware import middleware



app = flask.Flask(__name__)
app.config["DEBUG"] = False

app.wsgi_app = middleware(app.wsgi_app)

def main():
    print("Starting node")
    server_thread = threading.Thread(target=start_server)
    server_thread.start()
    start_cmdloop()

# Start FLASK thread
def start_server():
    app.run(port=6376, host="0.0.0.0")

# Start CMD line thread
def start_cmdloop():
    try:
        CommandLoop().cmdloop()
    except Exception as e:
        print("Exception from cmdloop")
        print(e)
        traceback.print_exc()
        pdb.set_trace()


@app.route("/election", methods=["POST"])
def election() -> ReverseBullyElectionResponse:
    origin = request.remote_addr
    if origin in [node["ip"] for node in state.NODES.values()]:
        origin_number = next(
            node["player_number"] for node in state.NODES.values() if node["ip"] == origin
        )
        if origin_number > state.OWN_NODE_NUMBER:
            Thread(target=take_over_bully).start()
            return {"taking_over": True}
    return {"taking_over": False}


def take_over_bully():
    print("Taking over the election.")
    bully.reverse_bully()


@app.route("/new-leader", methods=["POST"])
def assign_new_leader():
    origin = request.origin
    if origin in [node["ip"] for node in state.NODES.values()]:
        origin_number = next(
            node["player_number"] for node in state.NODES.values() if node["ip"] == origin
        )
        if origin_number < state.OWN_NODE_NUMBER:
            print(f"Assigning new leader: {origin_number}")
            state.LEADER_NODE_NUMBER = origin_number
            state.LEADER_ELECTION_ONGOING = False
    return {"message": "Ok, assigned new leader."}


@app.route("/", methods=["GET"])
def home():
    return {"message": "Hello, World!"}


@app.route("/health", methods=["GET"])
def health():
    return {"message": "ok"}

@app.route("/get-nodes", methods=["GET"])
def get_nodes():
    return {"message": "Here are my nodes I know of", "nodes": state.NODES}


# have to prevent that two nodes don't join with the same player number
registration_lock = Lock()


@app.route("/join", methods=["POST"])
def register_nodes():
    try:
        registration_lock.acquire()

        # Do not let players join while game ongoing.
        if state.GAME_PHASE == state.GAME_PHASE.GAME_ONGOING:
            return {"message": "Game ongoing, please join later."}

        json: JoinRequest = request.json
        origin = request.remote_addr

        # Leader assigns itself once first person joins
        if state.NEXT_PLAYER_NUMBER == 1:
            state.OWN_NODE_NUMBER = 1
            state.NODES[state.LEADER_NODE_NUMBER] = Player(
                player_number=1,
                ip=json["your_ip"],
                score=0,
            )
            state.NEXT_PLAYER_NUMBER = 2

        # Check if node trying to join is/was already in-game
        if origin in [node["ip"] for node in state.NODES.values()]:
            print(
                "Node with IP",
                origin,
                "already in game.",
            )
            # FAULT_TOLERANCE: If node drops out of game, get list his list of nodes, if it is empty, return him the current state
            get_nodes_result = requests.get(f"http://{origin}:6376/get-nodes").json
            if get_nodes_result["nodes"].length == 0:
                print(
                    "Node did probably crash or lose connection, sending him the game state."
                )
                return {"message": "You have already registered.", "nodes": state.NODES}

            return {"message": "You are already part of this game."}, 400

        print("Adding player #", state.NEXT_PLAYER_NUMBER, " to game")
        state.NODES[int(state.NEXT_PLAYER_NUMBER)] = Player(
            ip=origin, player_number=state.NEXT_PLAYER_NUMBER, score=0
        )
        state.NEXT_PLAYER_NUMBER += 1

        print("Broadcast to others the recently joining participant")
        print("Nodes in game:", state.NODES)
        broadcast_new_node_list()

        print("Return current game state to joining paricipant.")
        return JoinResponse(
            message="New node has been added",
            nodes=state.NODES,
            your_player_number=state.NEXT_PLAYER_NUMBER - 1,
            leader_node_number=state.LEADER_NODE_NUMBER,
        )
    finally:
        registration_lock.release()


@app.route("/helper-key", methods=["POST"])
def handle_helper_key():
    json: ShareKeyRequest = request.json
    state.HELPER_ENCRYPTION_KEY = json["key"]
    print("I received the helper node encryption key.")
    return {"message": "Thanks!"}

@app.route("/leader-key", methods=["POST"])
def handle_leader_key():
    json: ShareKeyRequest = request.json
    state.ENCRYPTION_KEY = json["key"]
    print("I received the leader node private key.")
    return {"message": "Thanks!"}

@app.route("/new-node-list", methods=["POST"])
def new_node_list():
    state.NODES = {int(k): v for k, v in request.json["nodes"].items()}
    state.NEXT_PLAYER_NUMBER = request.json["next_player_number"]
    print("I received the new node list.")
    return {"message": "New node list received"}

@app.route("/game-starting", methods=["POST"])
def game_starting():
    state.GAME_PHASE = GamePhase.GAME_ONGOING
    print("Game started.")
    return {"message": "Ok"}


@app.route("/plz-help-with-encrypting", methods=["POST"])
def handle_plz_help_with_encrypting() -> PlzHelpWithEncryptingDeckResponse:
    json: PlzHelpWithEncryptingDeckRequest = request.json
    deck = Deck(json["deck"])
    state.HELPER_ENCRYPTION_KEY = deck.encrypt_all()
    deck.shuffle()

    state.DOUBLE_ENCRYPTED_DECK = deck
    # Broadcast to all other nodes so that everyone can later verify that there has been no cheating
    for node in state.NODES.values():
        if node["player_number"] == state.OWN_NODE_NUMBER or node["player_number"] == state.LEADER_NODE_NUMBER:
            continue
        requests.post(
            f"http://{node['ip']}:6376/double-encrypted-deck", json={"deck": state.DOUBLE_ENCRYPTED_DECK.cards_to_json()}
        )
    return {"deck": state.DOUBLE_ENCRYPTED_DECK.cards_to_json()}


@app.route("/double-encrypted-deck", methods=["POST"])
def handle_double_encrypted_deck():
    json: DoubleEncryptedDeckRequest = request.json
    deck = Deck(json["deck"])
    state.DOUBLE_ENCRYPTED_DECK = deck
    print("Copy of double encrypted deck received and stored for later game verification.")
    return {"message": "Ok"}


@app.route("/winner", methods=["POST"])
def handle_winner():
    json: WinnerRequest = request.json
    state.WINNER_NUMBER = json["winner"]
    print(f"Winner is player #{state.WINNER_NUMBER}")
    state.GAME_PHASE = GamePhase.VOTING
    if state.WINNER_NUMBER == state.OWN_NODE_NUMBER:
        print("I am the winner")
    else:
        print("I lost")
    Thread(target=verify_game_and_participate_in_fairness_voting).start()
    return {"message": "Ok"}


@app.route("/game-winner-verification-result", methods=["POST"])
def handle_game_winner_verification_result():
    json: GameWinnerVerificationResultRequest = request.json
    if json["agree"]:
        state.NUMBER_OF_NODES_THAT_AGREE_WITH_THE_RESULT += 1
    else:
        state.NUMBER_OF_NODES_THAT_DISAGREE_WITH_THE_RESULT += 1

    return {"message": "Ok"}

@app.route("/deal-results", methods=["POST"])
def handle_deal_results():
    json: DealResultsBroadcastRequest = request.json
    state.DEAL_RESULTS = json["who_got_what_cards"]
    # Fetch the helper ip to inform I got the dealt cards
    helper_ip = next(
            node["ip"] for node in state.NODES.values() if node["player_number"] == json["helper_player_number"]
        )
    requests.post(f"http://{helper_ip}:6376/i-got-the-dealt-cards")
    return {"message": "Ok"}


i_got_the_dealt_cards_lock = Lock()

# Helper receives this when others have gotten the dealt cards
@app.route("/i-got-the-dealt-cards", methods=["POST"])
def handle_i_got_the_dealt_cards():
    try:
        i_got_the_dealt_cards_lock.acquire()
        origin = request.remote_addr
        sender_player = next(node for node in state.NODES.values() if node["ip"] == origin)
        state.HELPER_MAP_WHO_GOT_THE_CARDS[sender_player["player_number"]] = True
        # If the majority of nodes have gotten the deck, we can pubish our encryption key to the leader
        number_of_nodes_who_got_the_cards = len([node for node in state.HELPER_MAP_WHO_GOT_THE_CARDS.values() if node])
        if number_of_nodes_who_got_the_cards >= len(state.NODES) / 2:
            # Broadcast this to everyone so that the key can be used for verification. 
            # What is more, the leader should publish their key once they have received this
            broadcast_helper_encryption_key()
        return {"message": "Ok"}
    finally:
        i_got_the_dealt_cards_lock.release()


def broadcast_helper_encryption_key():
    for node in state.NODES.values():
        if node["player_number"] == state.OWN_NODE_NUMBER:
            continue
        body: ShareKeyRequest = {"key": state.HELPER_ENCRYPTION_KEY}
        requests.post(
            f"http://{node['ip']}:6376/helper-key", json=body
        )


@app.route("/leave", methods=["POST"])
def unregister_nodes():
    origin = request.remote_addr
    player_name = next(player_name for (player_name, node) in state.NODES.items() if node["ip"] == origin)
    if player_name:
        state.NODES.pop(player_name)
        print("Nodes still in game", state.NODES)
        broadcast_new_node_list()
        return {"message": "Goodbye"}
    return {"message": "You are not part of this game"}


if __name__ == "__main__":
    main()
