from typing import Dict, TypedDict
import flask
from flask import request
import cmd
import threading
import requests
import random
import json
from cryptography.fernet import Fernet
from threading import Lock, Thread
import time

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
    def encrypt(self):
        key = Fernet.generate_key()
        fernet = Fernet(key)
        for i in range(52):
            self.cards[i] = fernet.encrypt(
                self.cards[i].to_bytes(self.cards[i].bit_length + 7 // 8, "big")
            )
        return key

    # decrypt the deck using a key given as an input
    def decrypt(self, key):
        fernet = Fernet(key)
        for i in range(52):
            self.cards[i] = int.from_bytes(fernet.decrypt(self.cards[i]), "big")

    # Return a json version of the deck
    def cards_to_json(self):
        return json.dumps(self.cards)


class JoinRequest(TypedDict):
    your_ip: str


class JoinResponse(TypedDict):
    message: str
    nodes: Dict[int, Player]
    your_player_number: int


class NodeList(TypedDict):
    message: str
    nodes: Dict[int, Player]


class NewNodeListMessage(TypedDict):
    nodes: Dict[int, Player]


class ReverseBullyElectionResponse(TypedDict):
    taking_over: bool


# The distributed state of the Node
# First node is player 1
NEXT_PLAYER_NUMBER = 1
LEADER_NODE_NUMBER = 1
OWN_NODE_NUMBER = 1
nodes: Dict[int, Player] = {}
LEADER_ELECTION_ONGOING = False

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
        global nodes
        global OWN_NODE_NUMBER
        join_command_parts = line.strip().split()
        if len(join_command_parts) < 1:
            print("Usage: join <ip>")
            return
        ip = join_command_parts[0]
        join_request: JoinRequest = {"your_ip": ip}
        res_obj = requests.post(
            f"http://{ip}:6376/join",
            json=join_request,
            timeout=5,
        )
        res: JoinResponse = res_obj.json()
        print("Join request response:", res)
        nodes = res["nodes"]
        OWN_NODE_NUMBER = res["your_player_number"]

    def do_list(self, line: str):
        print("Listing all nodes in the game.")
        print(nodes)


def check_leader_node_health() -> bool:
    global LEADER_NODE_NUMBER
    global OWN_NODE_NUMBER
    global nodes
    if LEADER_NODE_NUMBER == OWN_NODE_NUMBER:
        print("Not checking leader health because I am the leader.")
        return True
    print("Checking leader node health.")
    leader_node_ip = nodes[LEADER_NODE_NUMBER]["ip"]
    try:
        health_check_res = requests.get(
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
    global nodes
    res = [node for node in nodes.values() if node["player_number"] < OWN_NODE_NUMBER]
    for node in res:
        try:
            response: ReverseBullyElectionResponse = requests.post(
                f"http://{node['ip']}:6376/election", timeout=5
            ).json
            if response["taking_over"]:
                return False
        except:
            print("Timed out waiting for response from node:", node["player_number"])
    return True


def announce_election_victory():
    print("Announcing election victory.")
    for node in nodes:
        try:
            request.post(f"http://{node['ip']}:6376/new-leader", timeout=5)
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
    global nodes
    origin = request.remote_addr
    if origin in [node["ip"] for node in nodes.values()]:
        origin_number = next(
            node["player_number"] for node in nodes.values() if node["ip"] == origin
        )
        if origin_number > OWN_NODE_NUMBER:
            Thread(target=take_over_bully).start()
            return {"taking_over": True}
    return {"taking_over": False}


@app.route("/new-leader", method=["POST"])
def assign_new_leader():
    global LEADER_NODE_NUMBER
    global LEADER_ELECTION_ONGOING
    origin = request.origin
    if origin in [node["ip"] for node in nodes.values()]:
        origin_number = next(
            node["player_number"] for node in nodes.values() if node["ip"] == origin
        )
        if origin_number < OWN_NODE_NUMBER:
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
    CommandLoop().cmdloop()


@app.route("/get-nodes", methods=["GET"])
def get_nodes():
    global nodes
    return NodeList(message="Here are my nodes I know of", nodes=nodes)


# have to prevent that two nodes don't join with the same player number
registration_lock = Lock()


@app.route("/join", methods=["POST"])
def register_nodes():
    try:
        registration_lock.acquire()
        global NEXT_PLAYER_NUMBER
        global nodes
        # print("request.data", request.json)
        json: JoinRequest = request.json
        origin = request.remote_addr
        # print("origin", origin)
        if NEXT_PLAYER_NUMBER == 1:
            nodes[LEADER_NODE_NUMBER] = Player(
                player_number=1,
                ip=json["your_ip"],
                score=0,
            )
            NEXT_PLAYER_NUMBER = 2

        # Check if node trying to join is already in-game
        if origin in [node["ip"] for node in nodes.values()]:
            print(
                "Node with IP",
                origin,
                "already in game.",
            )
            # FAULT_TOLERANCE: If node drops out of game, get list his list of nodes, if it is empty, return him the current state
            get_nodes_result = requests.get(f"http://{origin}:6376/get-nodes").json
            print(get_nodes_result)
            if get_nodes_result["nodes"].length == 0:
                print(
                    "Node did probably crash or loose connection, sending him the game state."
                )
                return {"message": "You have already registered.", "nodes": nodes}

            return {"message": "You are already part of this game."}, 400

        print("Adding player #", NEXT_PLAYER_NUMBER, " to game")
        nodes[NEXT_PLAYER_NUMBER] = Player(
            ip=origin, player_number=NEXT_PLAYER_NUMBER, score=0
        )
        NEXT_PLAYER_NUMBER += 1

        print("Broadcast to others the recently joining participant")
        print("Nodes in game:", nodes)
        broadcast_new_node_list()

        print("Return current game state to joining paricipant.")
        return JoinResponse(
            message="New node has been added",
            nodes=nodes,
            your_player_number=NEXT_PLAYER_NUMBER - 1,
        )
    finally:
        registration_lock.release()


def broadcast_new_node_list():
    global nodes
    for node in nodes.values():
        if node["player_number"] == OWN_NODE_NUMBER:
            continue
        new_node_list: NewNodeListMessage = {"nodes": nodes}
        res_obj = requests.post(
            f"http://{node['ip']}:6376/new-node-list", json=new_node_list
        )


@app.route("/new-node-list", methods=["POST"])
def new_node_list():
    global nodes
    nodes = request.json["nodes"]
    return {"message": "New node list received"}


@app.route("/leave", methods=["POST"])
def unregister_nodes():
    origin = request.remote_addr
    if origin in nodes.keys():
        del nodes[origin]
        print("nodes_after_leave", nodes)
        broadcast_new_node_list()
        return {"message": "Goodbye"}
    return {"message": "You are not part of this game"}


if __name__ == "__main__":
    main()
