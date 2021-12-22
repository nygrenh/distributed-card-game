import json
from typing import Dict, TypedDict
import base64
import random
from enum import Enum

from cryptography.fernet import Fernet

class Player(TypedDict):
    player_number: int
    ip: str
    score: int


class Deck:

    # Make a new deck 0-51
    # Init Deck from a JSON deck if provided
    def __init__(self, jsonString = None):
        if jsonString is None:
            self.cards = list(range(52))
        else:
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
            card = self.cards[i]
            card_bytes = None
            if type(card) == int:
                card_bytes = card.to_bytes(self.cards[i].bit_length() + 7 // 8, "big")
            if type(card) == str:
                card_bytes =  base64.b64decode(card.encode("ascii"))
            if type(card) == bytes:
                card_bytes = card
            self.cards[i] = base64.b64encode(fernet.encrypt(
                card_bytes
            )).decode("ascii")
        return base64.b64encode(key).decode("ascii")

    def decrypt_helper(key: str, card):
        fernet = Fernet(base64.b64decode(key.encode("ascii")))
        decrypted = None
        try:
            decrypted = fernet.decrypt(base64.b64decode(card.encode("ascii")))
        except:
            decrypted = fernet.decrypt(card.encode("ascii"))
        return decrypted.decode("ascii")

    def decrypt_one(key: str, card):
        fernet = Fernet(base64.b64decode(key.encode("ascii")))
        decrypted = None
        try:
            decrypted = fernet.decrypt(base64.b64decode(card.encode("ascii")))
        except:
            decrypted = fernet.decrypt(card.encode("ascii"))
        return int.from_bytes(decrypted, "big")

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
    deck: str


class WinnerRequest(TypedDict):
    winner: int

class GameWinnerVerificationResultRequest(TypedDict):
    agree: bool

class PlzHelpWithEncryptingDeckRequest(TypedDict):
    deck: str

class PlzHelpWithEncryptingDeckResponse(TypedDict):
    deck: str

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
    VOTING = 2
    GAME_OVER = 3