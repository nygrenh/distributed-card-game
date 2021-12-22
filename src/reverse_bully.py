import time
import requests
from classes import ReverseBullyElectionResponse
import state

# Bully algorithm, but prefers small numbers
def reverse_bully():
    print("Starting reverse bully election.")
    state.LEADER_ELECTION_ONGOING = True
    victory = reverse_bully_send_election_messages()
    if victory:
        print("I won the election. I am the new leader.")
        state.LEADER_NODE_NUMBER = state.OWN_NODE_NUMBER
        announce_election_victory()
    while state.LEADER_ELECTION_ONGOING:
        # Fine to sleep since we're in UI thread and the http server is running on a different thread.
        time.sleep(0.1)


# Returns true if nobody wants to take over the election, false otherwise
def reverse_bully_send_election_messages() -> bool:
    print(
        f"Sending election messages to nodes that have number smaller than {state.OWN_NODE_NUMBER}."
    )
    nodes_to_receive_eletion_msg = [node for node in state.NODES.values() if node["player_number"] < state.OWN_NODE_NUMBER]
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


def announce_election_victory():
    print("Announcing election victory.")
    for node in state.NODES.values():
        try:
            if node["player_number"] == state.OWN_NODE_NUMBER:
                continue
            print("Announcing victory to node:", node["player_number"])
            requests.post(f"http://{node['ip']}:6376/new-leader", timeout=5)
            print("Announced victory to node:", node["player_number"])
        except:
            print(
                "Timed out waiting acknowledgement for election victory announcement:",
                node["player_number"],
            )
