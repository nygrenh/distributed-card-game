from typing import Optional, Dict, DefaultDict

from classes import Deck, GamePhase, Player

# The distributed state of NODE
# First node is player 1
NEXT_PLAYER_NUMBER = 1
LEADER_NODE_NUMBER = 1
OWN_NODE_NUMBER = -1
NODES: Dict[int, Player] = {}
LEADER_ELECTION_ONGOING = False
GAME_PHASE = GamePhase.WAITING_FOR_PLAYERS
ENCRYPTION_KEY: Optional[str] = None
HELPER_ENCRYPTION_KEY: Optional[str] = None
DECK: Optional[Deck] = None
DOUBLE_ENCRYPTED_DECK: Optional[Deck] = None
DEAL_RESULTS:  Optional[Dict[int, str]] = None
WINNER_NUMBER: Optional[int] = None
HELPER_MAP_WHO_GOT_THE_CARDS: Dict[int, bool] = DefaultDict(bool)
NUMBER_OF_NODES_THAT_AGREE_WITH_THE_RESULT = 0
NUMBER_OF_NODES_THAT_DISAGREE_WITH_THE_RESULT = 0
# End global state for NODE

def empty_game_states():
    global ENCRYPTION_KEY
    global HELPER_ENCRYPTION_KEY
    global WINNER_NUMBER
    global DECK
    global DOUBLE_ENCRYPTED_DECK
    global DEAL_RESULTS
    global HELPER_MAP_WHO_GOT_THE_CARDS
    global NUMBER_OF_NODES_THAT_AGREE_WITH_THE_RESULT
    global NUMBER_OF_NODES_THAT_DISAGREE_WITH_THE_RESULT
    global GAME_PHASE

    print("Emptying game state for next game.")
    GAME_PHASE = GamePhase.WAITING_FOR_PLAYERS
    ENCRYPTION_KEY = None
    HELPER_ENCRYPTION_KEY = None
    DECK = None
    DOUBLE_ENCRYPTED_DECK = None
    DEAL_RESULTS = None
    WINNER_NUMBER = None
    HELPER_MAP_WHO_GOT_THE_CARDS = DefaultDict(bool)
    NUMBER_OF_NODES_THAT_AGREE_WITH_THE_RESULT = 0
    NUMBER_OF_NODES_THAT_DISAGREE_WITH_THE_RESULT = 0