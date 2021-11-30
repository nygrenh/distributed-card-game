from typing import Dict, TypedDict
import flask
from flask import request
import cmd
import threading
import requests
from threading import Lock


# First node is player 1
NEXT_PLAYER_NUMBER = 1
MASTER_NODE_NUMBER = 1
OWN_NODE_NUMBER = 1


class Player(TypedDict):
    player_number: int
    ip: str
    score: int


class JoinRequest(TypedDict):
    your_ip: str


class JoinResponse(TypedDict):
    message: str
    nodes: Dict[str, Player]
    your_player_number: int


class NewNodeListMessage(TypedDict):
    nodes: Dict[str, Player]


nodes: Dict[str, Player] = {}

app = flask.Flask(__name__)
app.config["DEBUG"] = False


class CommandLoop(cmd.Cmd):
    def do_join(self, line: str):
        global nodes
        global OWN_NODE_NUMBER
        parts = line.strip().split()
        if len(parts) < 1:
            print("Usage: join <ip>")
            return
        ip = parts[0]
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

    def do_list(self, line):
        print("Listing all nodes in the game.")
        print(nodes)


def main():
    print("Starting node")
    server_thread = threading.Thread(target=start_server)
    server_thread.start()
    start_cmdloop()


@app.route("/", methods=["GET"])
def home():
    return {"message": "Hello, World!"}


@app.route("/health", methods=["GET"])
def health():
    return {"message": "ok"}


def start_server():
    app.run(port=6376)


def start_cmdloop():
    CommandLoop().cmdloop()


@app.route("/get-nodes", methods=["GET"])
def get_nodes():
    global nodes
    return {"message_type": "list-nodes", "nodes": nodes}


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
            nodes[MASTER_NODE_NUMBER] = Player(
                player_number=1,
                ip=json["your_ip"],
                score=0,
            )
            NEXT_PLAYER_NUMBER = 2

        # Check if node trying to join is already in-game
        if origin in nodes.keys():
            # FAULT_TOLERANCE: If node drops out of game, get list his list of nodes, if it is empty, return him the current state
            # res_obj = requests.get(f"http://{origin}:6376/get-nodes")
            # print(res_obj)
            return {"message": "You have already registered.", "nodes": nodes}, 400
        nodes[origin] = Player(ip=origin, player_number=NEXT_PLAYER_NUMBER, score=0)
        NEXT_PLAYER_NUMBER += 1
        print("nodes", nodes)
        broadcast_new_node_list()
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
    print(request)
    nodes = request.json["nodes"]
    return {"message": "New node list received"}


@app.route("/leave", methods=["POST"])
def unregister_nodes():
    origin = request.remote_addr
    if origin in nodes.keys():
        del nodes[origin]
        print("nodes_after_leave", nodes)
        return {"message": "Goodbye"}
    return {"message": "You are not part of this game"}


if __name__ == "__main__":
    main()
