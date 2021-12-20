from typing import DefaultDict, Dict, TypedDict
import flask
from flask import request
import cmd
import threading
import requests
import random
import json
from cryptography.fernet import Fernet
from threading import Lock, Thread, local
import time
import pdb
from enum import Enum

from flask_middleware import middleware


class Player(TypedDict):
    player_number: int
    ip: str
    score: int


class Deck:

    # Make a new deck 0-51
    def __init__(self):
        self.cards = list(range(52))
        self.top_card = 51

    # Init Deck from a JSON deck
    def __init__(self, jsonString):
        self.cards = json.loads(jsonString)
        self.top_card = 51

    # Get the top card
    def pop(self):
        card = self.cards[self.top_card]
        self.top_card -= 1
        return card

    # Shuffle the deck
    def shuffle(self):
        random.shuffle(self.cards)

    # encrypt the deck with a key and return the key
    def encrypt_all(self):
        key = Fernet.generate_key()
        fernet = Fernet(key)
        for i in range(52):
            self.cards[i] = fernet.encrypt(
                self.cards[i].to_bytes(self.cards[i].bit_length + 7 // 8, "big")
            )
        return key

    # decrypt the deck using a key given as an input
    def decrypt_all(self, key):
        fernet = Fernet(key)
        for i in range(52):
            self.cards[i] = int.from_bytes(fernet.decrypt(self.cards[i]), "big")

    def decrypt_one(self, key, card):
        fernet = Fernet(key)
        return int.from_bytes(fernet.decrypt(card), "big")

    # Return a json version of the deck
    def cards_to_json(self):
        return json.dumps(self.cards)


class JoinRequest(TypedDict):
    your_ip: str


class JoinResponse(TypedDict):
    message: str
    # str because numbers cannot be keys in json
    nodes: Dict[str, Player]
    your_player_number: int
    leader_node_number: int

class DoubleEncryptedDeckRequest(TypedDict):
    deck: Deck

class PlzHelpWithEncryptingDeckRequest(TypedDict):
    deck: Deck

class PlzHelpWithEncryptingDeckResponse(TypedDict):
    deck: Deck

class ShareKeyRequest(TypedDict):
    key: str

class DealResultsBroadcastRequest(TypedDict):
    # Key player number, value encrypted card
    who_got_what_cards: Dict[int, str]
    helper_player_number: int


class NodeList(TypedDict):
    message: str
    nodes: Dict[int, Player]


class NewNodeListMessage(TypedDict):
    nodes: Dict[int, Player]
    next_player_number: int


class ReverseBullyElectionResponse(TypedDict):
    taking_over: bool


class GamePhase(Enum):
    WAITING_FOR_PLAYERS = 0
    GAME_ONGOING = 1
    GAME_OVER = 2

# The distributed state of NODE
# First node is player 1
NEXT_PLAYER_NUMBER = 1
LEADER_NODE_NUMBER = 1
OWN_NODE_NUMBER = -1
NODES: Dict[int, Player] = {}
LEADER_ELECTION_ONGOING = False
GAME_PHASE = GamePhase.WAITING_FOR_PLAYERS
ENCRYPTION_KEY: str | None = None
HELPER_ENCRYPTION_KEY: str | None = None
DECK: Deck | None = None
DOUBLE_ENCRYPTED_DECK: Deck | None = None
DEAL_RESULTS: Dict[int, str] | None = None
HELPER_MAP_WHO_GOT_THE_CARDS: Dict[int, False] = DefaultDict(bool)
# End global state for NODE
app = flask.Flask(__name__)
app.config["DEBUG"] = False

app.wsgi_app = middleware(app.wsgi_app)


class CommandLoop(cmd.Cmd):
    def precmd(self, line: str) -> str:
        print(f"Processing command: {line}")
        leader_node_healthy = check_leader_node_health()
        if not leader_node_healthy:
            print("Leader node is not healthy. Starting a new leader election.")
            reverse_bully()
        return super().precmd(line)

    def postcmd(self, stop: bool, line: str) -> bool:
        print(f"Finished processing command: {line}")
        return super().postcmd(stop, line)

    def do_join(self, line: str):
        global NODES
        global OWN_NODE_NUMBER
        global LEADER_NODE_NUMBER
        join_command_parts = line.strip().split()
        if len(join_command_parts) < 1:
            print("Usage: join <ip>")
            return
        ip = join_command_parts[0]

        # This is used so that leader learns their IP
        join_request: JoinRequest = {"your_ip": ip}
        res_obj = requests.post(
            f"http://{ip}:6376/join",
            json=join_request,
            timeout=5,
        )
        res: JoinResponse = res_obj.json()
        print("Join request response:", res)
        NODES = {int(k): v for k, v in res["nodes"].items()}
        OWN_NODE_NUMBER = res["your_player_number"]
        LEADER_NODE_NUMBER = res["leader_node_number"]

    def do_list(self, line: str):
        print("Listing all nodes in the game.")
        print(NODES)

    def do_start_game(self, line: str):
        global ENCRYPTION_KEY
        global DECK
        global DOUBLE_ENCRYPTED_DECK
        global GAME_PHASE

        if OWN_NODE_NUMBER == LEADER_NODE_NUMBER:
            print("Starting game.")
            broadcast_game_starting()
            # Todo handle if this fails
            GAME_PHASE = GamePhase.GAME_ONGOING
            node_that_helps_with_shuffling = choose_follower_to_help_with_shuffling()
            # Master starts the shuffling. It first chooses a key and encrypts all cards with the same key.
            DECK = Deck()
            ENCRYPTION_KEY = DECK.encrypt_all()
            DECK.shuffle()
            # Next we send the deck to the helper node
            DOUBLE_ENCRYPTED_DECK = send_deck_to_node_to_help_with_shuffling(DECK, node_that_helps_with_shuffling)
            # deal cards
            deal_request: DealResultsBroadcastRequest = { "helper_player_number": node_that_helps_with_shuffling.player_number}
            for node in NODES:
                deal_request["who_got_what_cards"][node] = DOUBLE_ENCRYPTED_DECK.pop()
            broadcast_dealt_cards(deal_request)
            # Next, the encryption keys will be published

            # As the leader, we are in different thread (Command Line) and we can wait for the HELPER_ENCRYPTION_KEY to be broadcasted
            # Via the HTTP POST by the helper node.
            # Helper will send it to us once it has received confirmation from all nodes that they have received the dealt cards
            while HELPER_ENCRYPTION_KEY == None:
                time.sleep(0.5)

            # Now we can publish leader encryption key as we received the helper key and majority has confirmed receiving the deck
            broadcast_leader_encryption_key()
            highest_card = -1
            highest_card_owner = None
            for (node, card) in deal_request["who_got_what_cards"].items():
                helper_decrypted_card = Deck.decrypt_one(card, HELPER_ENCRYPTION_KEY)
                decrypted_card_value = Deck.decrypt_one(helper_decrypted_card, ENCRYPTION_KEY)
                if decrypted_card_value > highest_card:
                    highest_card = decrypted_card_value
                    highest_card_owner = node
        else:
            print("Not the leader. Cannot start game.")

def check_leader_node_health() -> bool:
    if OWN_NODE_NUMBER == -1:
        print("Not checking leader node health")
        return True
    if LEADER_NODE_NUMBER == OWN_NODE_NUMBER:
        print("Not checking leader health because I am the leader.")
        return True
    print("Checking leader node health.")
    leader_node_ip = NODES[LEADER_NODE_NUMBER]["ip"]
    try:
        requests.get(
            f"http://{leader_node_ip}:6376/health", timeout=5
        ).json
    except:
        print("Health check failed.")
        return False
    print("The leader is healthy")
    return True


# Bully algorithm, but prefers small numbers
def reverse_bully():
    global LEADER_ELECTION_ONGOING
    print("Starting reverse bully election.")
    LEADER_ELECTION_ONGOING = True
    victory = reverse_bully_send_election_messages()
    if victory:
        print("I won the election. I am the new leader.")
        global LEADER_NODE_NUMBER
        LEADER_NODE_NUMBER = OWN_NODE_NUMBER
        announce_election_victory()
    while LEADER_ELECTION_ONGOING:
        # Fine to sleep since we're in UI thread and the http server is running on a different thread.
        time.sleep(0.1)


# Returns true if nobody wants to take over the election, false otherwise
def reverse_bully_send_election_messages() -> bool:
    global NODES
    print(
        f"Sending election messages to nodes that have number smaller than {OWN_NODE_NUMBER}."
    )
    nodes_to_receive_eletion_msg = [node for node in NODES.values() if node["player_number"] < OWN_NODE_NUMBER]
    for node in nodes_to_receive_eletion_msg:
        print(f"Sending election message to {node['player_number']}")
        try:
            response: ReverseBullyElectionResponse = requests.post(
                f"http://{node['ip']}:6376/election", timeout=5
            ).json()
            if response["taking_over"]:
                print(
                    f"Node {node['player_number']} answered and taking over election."
                )
                return False
            else:
                print(
                    f"Node {node['player_number']} answered and did not take over election."
                )
        except:
            print("Timed out waiting for response from node:", node["player_number"])
    return True


def send_deck_to_node_to_help_with_shuffling(deck: Deck, node_that_helps_with_shuffling: Player) -> Deck:
    global NODES
    print(f"Sending deck to node {node_that_helps_with_shuffling}")

    request: PlzHelpWithEncryptingDeckRequest = { deck: Deck }

    res: PlzHelpWithEncryptingDeckResponse = requests.post(
        f"http://{node_that_helps_with_shuffling['ip']}:6376/plz-help-with-encrypting", json=request, timeout=5
    ).json()
    return res["deck"]


def choose_follower_to_help_with_shuffling() -> Player:
    print(
        "Choosing node to help with shuffling"
    )
    if len(NODES.values()) == 0:
        print("The game is empty")
        raise Exception("The game is empty")
    # Exclude own player number
    players_excluding_myself = [node for node in NODES.values() if node["player_number"] != OWN_NODE_NUMBER]
    chosen_one = random.choice(players_excluding_myself)
    print(f"Node {chosen_one['player_number']} will help with shuffling.")
    return chosen_one

def announce_election_victory():
    print("Announcing election victory.")
    global OWN_NODE_NUMBER
    for node in NODES.values():
        try:
            if node["player_number"] == OWN_NODE_NUMBER:
                continue
            print("Announcing victory to node:", node["player_number"])
            requests.post(f"http://{node['ip']}:6376/new-leader", timeout=5)
            print("Announced victory to node:", node["player_number"])
        except:
            print(
                "Timed out waiting acknowledgement for election victory announcement:",
                node["player_number"],
            )


def main():
    print("Starting node")
    server_thread = threading.Thread(target=start_server)
    server_thread.start()
    start_cmdloop()


@app.route("/election", methods=["POST"])
def election() -> ReverseBullyElectionResponse:
    global NODES
    origin = request.remote_addr
    if origin in [node["ip"] for node in NODES.values()]:
        origin_number = next(
            node["player_number"] for node in NODES.values() if node["ip"] == origin
        )
        if origin_number > OWN_NODE_NUMBER:
            Thread(target=take_over_bully).start()
            return {"taking_over": True}
    return {"taking_over": False}


@app.route("/new-leader", methods=["POST"])
def assign_new_leader():
    global LEADER_NODE_NUMBER
    global LEADER_ELECTION_ONGOING
    origin = request.origin
    if origin in [node["ip"] for node in NODES.values()]:
        origin_number = next(
            node["player_number"] for node in NODES.values() if node["ip"] == origin
        )
        if origin_number < OWN_NODE_NUMBER:
            print(f"Assigning new leader: {origin_number}")
            LEADER_NODE_NUMBER = origin_number
            LEADER_ELECTION_ONGOING = False
    return {"message": "Ok, assigned new leader."}


def take_over_bully():
    print("Taking over the election.")
    reverse_bully()


@app.route("/", methods=["GET"])
def home():
    return {"message": "Hello, World!"}


@app.route("/health", methods=["GET"])
def health():
    return {"message": "ok"}


def start_server():
    app.run(port=6376, host="0.0.0.0")


def start_cmdloop():
    try:
        CommandLoop().cmdloop()
    except:
        pdb.set_trace()


@app.route("/get-nodes", methods=["GET"])
def get_nodes():
    global NODES
    return NodeList(message="Here are my nodes I know of", nodes=NODES)


# have to prevent that two nodes don't join with the same player number
registration_lock = Lock()


@app.route("/join", methods=["POST"])
def register_nodes():
    try:
        registration_lock.acquire()
        global NEXT_PLAYER_NUMBER
        global NODES
        global LEADER_NODE_NUMBER
        global GAME_PHASE

        # Do not let players join while game ongoing.
        if GAME_PHASE == GAME_PHASE.GAME_ONGOING:
            return {"message": "Game ongoing, please join later."}

        json: JoinRequest = request.json
        origin = request.remote_addr

        if NEXT_PLAYER_NUMBER == 1:
            NODES[LEADER_NODE_NUMBER] = Player(
                player_number=1,
                ip=json["your_ip"],
                score=0,
            )
            NEXT_PLAYER_NUMBER = 2

        # Check if node trying to join is/was already in-game
        if origin in [node["ip"] for node in NODES.values()]:
            print(
                "Node with IP",
                origin,
                "already in game.",
            )
            # FAULT_TOLERANCE: If node drops out of game, get list his list of nodes, if it is empty, return him the current state
            get_nodes_result = requests.get(f"http://{origin}:6376/get-nodes").json
            if get_nodes_result["nodes"].length == 0:
                print(
                    "Node did probably crash or loose connection, sending him the game state."
                )
                return {"message": "You have already registered.", "nodes": NODES}

            return {"message": "You are already part of this game."}, 400

        print("Adding player #", NEXT_PLAYER_NUMBER, " to game")
        NODES[int(NEXT_PLAYER_NUMBER)] = Player(
            ip=origin, player_number=NEXT_PLAYER_NUMBER, score=0
        )
        NEXT_PLAYER_NUMBER += 1

        print("Broadcast to others the recently joining participant")
        print("Nodes in game:", NODES)
        broadcast_new_node_list()

        print("Return current game state to joining paricipant.")
        return JoinResponse(
            message="New node has been added",
            nodes=NODES,
            your_player_number=NEXT_PLAYER_NUMBER - 1,
            leader_node_number=LEADER_NODE_NUMBER,
        )
    finally:
        registration_lock.release()


def broadcast_new_node_list():
    for node in NODES.values():
        if node["player_number"] == OWN_NODE_NUMBER:
            continue
        new_node_list: NewNodeListMessage = {"nodes": NODES, "next_player_number": NEXT_PLAYER_NUMBER}
        requests.post(
            f"http://{node['ip']}:6376/new-node-list", json=new_node_list
        )

def broadcast_game_starting():
    for node in NODES.values():
        if node["player_number"] == OWN_NODE_NUMBER:
            continue
        requests.post(
            f"http://{node['ip']}:6376/game-starting"
        )

def broadcast_helper_encryption_key():
    for node in NODES.values():
        if node["player_number"] == OWN_NODE_NUMBER:
            continue
        body: ShareKeyRequest = {"key": HELPER_ENCRYPTION_KEY}
        requests.post(
            f"http://{node['ip']}:6376/helper-key", json=body
        )

def broadcast_leader_encryption_key():
    for node in NODES.values():
        if node["player_number"] == OWN_NODE_NUMBER:
            continue
        body: ShareKeyRequest = {"key": ENCRYPTION_KEY}
        requests.post(
            f"http://{node['ip']}:6376/leader-key", json=body
        )

@app.route("/new-node-list", methods=["POST"])
def new_node_list():
    global NODES
    NODES = {int(k): v for k, v in request.json["nodes"].items()}
    return {"message": "New node list received"}

@app.route("/game-starting", methods=["POST"])
def game_starting():
    global GAME_PHASE
    GAME_PHASE = GamePhase.GAME_ONGOING
    return {"message": "Ok"}


@app.route("/plz-help-with-encrypting", methods=["POST"])
def handle_plz_help_with_encrypting() -> PlzHelpWithEncryptingDeckResponse:
    json: PlzHelpWithEncryptingDeckRequest = request.json
    global DECK
    global ENCRYPTION_KEY
    DECK = Deck(jsonString=json["deck"])
    ENCRYPTION_KEY = DECK.encrypt_all()
    DECK.shuffle()
    # Broadcast to all other nodes so that everyone can later verify that there has been no cheating
    for node in NODES.values():
        if node["player_number"] == OWN_NODE_NUMBER or node["player_number"] == LEADER_NODE_NUMBER:
            continue
        requests.post(
            f"http://{node['ip']}:6376/double-encrypted-deck", json={"deck": DECK.cards_to_json()}
        )
    return {"deck": DECK.to_json()}


@app.route("/double-encrypted-deck", methods=["POST"])
def handle_double_encrypted_deck():
    global DOUBLE_ENCRYPTED_DECK
    json: DoubleEncryptedDeckRequest = request.json
    deck = Deck(jsonString=json["deck"])
    DOUBLE_ENCRYPTED_DECK = deck
    return {"message": "Ok"}


def broadcast_dealt_cards(deal_request: DealResultsBroadcastRequest):
    for node in NODES.values():
        if node["player_number"] == OWN_NODE_NUMBER:
            continue
        requests.post(
            f"http://{node['ip']}:6376/deal-results", json=deal_request
        )

@app.route("/deal-results", methods=["POST"])
def handle_deal_results():
    global DEAL_RESULTS
    json: DealResultsBroadcastRequest = request.json
    DEAL_RESULTS = json["who_got_what_cards"]
    # Fetch the helper ip to inform I got the dealt cards
    helper_ip = next(
            node["ip"] for node in NODES.values() if node["player_number"] == json["helper_player_number"]
        )
    requests.post(f"http://{helper_ip}:6376/i-got-the-dealt-cards")
    return {"message": "Ok"}


i_got_the_dealt_cards_lock = Lock()

# Helper receives this when others have gotten the dealt cards
@app.route("/i-got-the-dealt-cards", methods=["POST"])
def handle_i_got_the_dealt_cards():
    global HELPER_MAP_WHO_GOT_THE_CARDS
    try:
        i_got_the_dealt_cards_lock.acquire()
        origin = request.remote_addr
        sender_player = next(node for node in NODES.values() if node["ip"] == origin)
        HELPER_MAP_WHO_GOT_THE_CARDS[sender_player["player_number"]] = True
        # If the majority of nodes have gotten the deck, we can pubish our encryption key to the leader
        number_of_nodes_who_got_the_cards = len([node for node in HELPER_MAP_WHO_GOT_THE_CARDS.values() if node])
        if number_of_nodes_who_got_the_cards >= len(NODES) / 2:
            # Broadcast this to everyone so that the key can be used for verification. What is more, the leader should publish their key once they have received this
            broadcast_helper_encryption_key()
        return {"message": "Ok"}
    finally:
        i_got_the_dealt_cards_lock.release()


@app.route("/leave", methods=["POST"])
def unregister_nodes():
    origin = request.remote_addr
    if origin in NODES.keys():
        del NODES[origin]
        print("nodes_after_leave", NODES)
        broadcast_new_node_list()
        return {"message": "Goodbye"}
    return {"message": "You are not part of this game"}


if __name__ == "__main__":
    main()
