import random
import time
import requests
from classes import DealResultsBroadcastRequest, Deck, GamePhase, GameWinnerVerificationResultRequest, JoinRequest, JoinResponse, NewNodeListMessage, Player, PlzHelpWithEncryptingDeckRequest, PlzHelpWithEncryptingDeckResponse, ShareKeyRequest, WinnerRequest
import pdb
import cmd
import state
import reverse_bully as bully

class CommandLoop(cmd.Cmd):
    def precmd(self, line: str) -> str:
        print(f"Processing command: {line}")
        leader_node_healthy = check_leader_node_health()
        if not leader_node_healthy:
            print("Leader node is not healthy. Starting a new leader election.")
            bully.reverse_bully()
        return super().precmd(line)

    def postcmd(self, stop: bool, line: str) -> bool:
        print(f"Finished processing command: {line}")
        return super().postcmd(stop, line)

    def do_join(self, line: str):
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
        # Set returned NODES state
        state.NODES = {int(k): v for k, v in res["nodes"].items()}
        # Set your own player number
        state.OWN_NODE_NUMBER = res["your_player_number"]
        # Assign leader
        state.LEADER_NODE_NUMBER = res["leader_node_number"]

    def do_list(self, line: str):
        print("Listing all nodes in the game.")
        print(state.NODES)

    def do_debug(self, line: str):
        pdb.set_trace()

    def do_start_game(self, line: str):

        if state.OWN_NODE_NUMBER != state.LEADER_NODE_NUMBER:
            print("Not the leader. Cannot start game.")
            return

        print("Starting game.")
        broadcast_game_starting()
        # Todo handle if this fails
        state.GAME_PHASE = GamePhase.GAME_ONGOING
        node_that_helps_with_shuffling = choose_follower_to_help_with_shuffling()
        # Master starts the shuffling. It first chooses a key and encrypts all cards with the same key.
        state.DECK = Deck()
        state.ENCRYPTION_KEY = state.DECK.encrypt_all()
        state.DECK.shuffle()
        # Next we send the deck to the helper node
        state.DOUBLE_ENCRYPTED_DECK = Deck(send_deck_to_node_to_help_with_shuffling(state.DECK, node_that_helps_with_shuffling))
        # Leader deals cards
        deal_request: DealResultsBroadcastRequest = { "who_got_what_cards": {}, "helper_player_number": node_that_helps_with_shuffling["player_number"]}
        for node in sorted(state.NODES):
            deal_request["who_got_what_cards"][node] = state.DOUBLE_ENCRYPTED_DECK.pop()
        # broadcast dealt card, each participant tells helper that they have received a card
        broadcast_dealt_cards(deal_request)
        # Next, the encryption keys will be published

        # As the leader, we are in different thread (Command Line) and we can wait for the HELPER_ENCRYPTION_KEY to be broadcasted
        # Via the HTTP POST by the helper node.
        # Helper will send it to us once it has received confirmation from all nodes that they have received the dealt cards
        while state.HELPER_ENCRYPTION_KEY == None:
            time.sleep(0.5)

        # Now we can publish leader encryption key as we received the helper key and majority has confirmed receiving the deck
        broadcast_leader_encryption_key()
        highest_card = -1
        highest_card_owner = None
        for (node, card) in deal_request["who_got_what_cards"].items():
            helper_decrypted_card = Deck.decrypt_helper(state.HELPER_ENCRYPTION_KEY, card)
            decrypted_card_value = Deck.decrypt_one(state.ENCRYPTION_KEY, helper_decrypted_card)
            print(f"Dealt card {decrypted_card_value} to player name {node}")
            if decrypted_card_value > highest_card:
                highest_card = decrypted_card_value
                highest_card_owner = node
        broadcast_winner(highest_card_owner)
        req: GameWinnerVerificationResultRequest = { "agree" : True }
        share_your_fairness_vote_and_wait_for_results(req, highest_card_owner)
        
# Used before every command by a NODE
def check_leader_node_health() -> bool:
    # Do not check for health when joining game
    if state.OWN_NODE_NUMBER == -1:
        print("Not checking leader node health")
        return True
    if state.LEADER_NODE_NUMBER == state.OWN_NODE_NUMBER:
        print("Not checking leader health because I am the leader.")
        return True
    print("Checking leader node health.")
    leader_node_ip = state.NODES[state.LEADER_NODE_NUMBER]["ip"]
    try:
        requests.get(
            f"http://{leader_node_ip}:6376/health", timeout=5
        ).json
    except:
        print("Health check failed.")
        return False
    print("The leader is healthy")
    return True


def choose_follower_to_help_with_shuffling() -> Player:
    print("Choosing node to help with shuffling")
    if len(state.NODES.values()) == 0:
        print("The game is empty")
        raise Exception("The game is empty")
    # Exclude own player number
    players_excluding_myself = [node for node in state.NODES.values() if node["player_number"] != state.OWN_NODE_NUMBER]
    chosen_one = random.choice(players_excluding_myself)
    print(f"Node {chosen_one['player_number']} will help with shuffling.")
    return chosen_one


def verify_game_and_participate_in_fairness_voting():
    verify_dealt_cards = {}
    print("Verifying game.")
    for node in sorted(state.NODES):
        verify_dealt_cards[node] = state.DOUBLE_ENCRYPTED_DECK.pop()


    highest_card = -1
    highest_card_owner = None
    for (node, card) in verify_dealt_cards.items():
        helper_decrypted_card = Deck.decrypt_helper(state.HELPER_ENCRYPTION_KEY, card)
        decrypted_card_value = Deck.decrypt_one(state.ENCRYPTION_KEY, helper_decrypted_card)
        print(f"According to my knowledge, player {node} received card {decrypted_card_value}.")
        if decrypted_card_value > highest_card:
            highest_card = decrypted_card_value
            highest_card_owner = node

    agree_on_winner = highest_card_owner == state.WINNER_NUMBER 
    print(f"I found out that the player {highest_card_owner} is the winner, my agreement with leader: {agree_on_winner}")
    game_winner: GameWinnerVerificationResultRequest = { "agree": agree_on_winner }
    share_your_fairness_vote_and_wait_for_results(game_winner, state.WINNER_NUMBER)


def share_your_fairness_vote_and_wait_for_results(game_winner: GameWinnerVerificationResultRequest, winner_number: int):
    print("Starting fairness vote.")
    for node in state.NODES.values():
        requests.post(f"http://{node['ip']}:6376/game-winner-verification-result", json=game_winner)
    while True:
        if state.NUMBER_OF_NODES_THAT_AGREE_WITH_THE_RESULT >= len(state.NODES) / 2:
            print(f"The winner is confirmed to be {winner_number}")
            break
        elif state.NUMBER_OF_NODES_THAT_DISAGREE_WITH_THE_RESULT >= len(state.NODES) / 2:
            print(f"Winner cannot be detemined because cheating.")
            break
    state.empty_game_states()


def broadcast_dealt_cards(deal_request: DealResultsBroadcastRequest):
    for node in state.NODES.values():
        requests.post(
            f"http://{node['ip']}:6376/deal-results", json=deal_request
        )

# Used when a new player joins a game
def broadcast_new_node_list():
    for node in state.NODES.values():
        if node["player_number"] == state.OWN_NODE_NUMBER:
            continue
        new_node_list: NewNodeListMessage = {"nodes": state.NODES, "next_player_number": state.NEXT_PLAYER_NUMBER}
        requests.post(
            f"http://{node['ip']}:6376/new-node-list", json=new_node_list
        )

def broadcast_game_starting():
    for node in state.NODES.values():
        if node["player_number"] == state.OWN_NODE_NUMBER:
            continue
        requests.post(
            f"http://{node['ip']}:6376/game-starting"
        )

def broadcast_leader_encryption_key():
    for node in state.NODES.values():
        if node["player_number"] == state.OWN_NODE_NUMBER:
            continue
        body: ShareKeyRequest = {"key": state.ENCRYPTION_KEY}
        requests.post(
            f"http://{node['ip']}:6376/leader-key", json=body
        )

# Winner of the game
def broadcast_winner(winner_number: int):
    for node in state.NODES.values():
        if node["player_number"] == state.OWN_NODE_NUMBER:
            continue
        body: WinnerRequest = {"winner": winner_number}
        requests.post(
            f"http://{node['ip']}:6376/winner", json=body
        )



def send_deck_to_node_to_help_with_shuffling(deck: Deck, node_that_helps_with_shuffling: Player) -> Deck:
    print(f"Sending deck to node {node_that_helps_with_shuffling}")

    request: PlzHelpWithEncryptingDeckRequest = { "deck": deck.cards_to_json() }

    res: PlzHelpWithEncryptingDeckResponse = requests.post(f"http://{node_that_helps_with_shuffling['ip']}:6376/plz-help-with-encrypting", json=request, timeout=5).json()
    return res["deck"]


