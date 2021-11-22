# Card Game

Our idea is to create a distributed card game, where each participant is involved in shuffling a card deck and this card deck is then used to play a simple card game.

Group name: - #27  
Members: Daniel Koch, Henrik Nygren, Sebastian Sergelius

## Detailed description of our idea

Our project will consist of a very simple card game where we have one card deck containing 52 cards. Cards are numbered from 1-52. First step is to shuffle the card deck with two nodes, one being leader and other being a random player in the game, in a manner where cheating is hard or impossible. After the deck has been shuffled we randomly choose a contester to pick up the card on top of the deck and then the leader node decides the turns when each player may pick up a card from the top of the deck. Once each contester has picked up their card, they turn them around and the winner will be the contester with the highest card.

To ensure cheating doesn't happen while shuffling the cards, we will implement the Mental poker card shuffling algorithm.
* https://en.wikipedia.org/wiki/Mental_poker#Shuffling_cards_using_commutative_encryption

Each contester will be running the same underlying system, which we will built upon using docker/docker-compose. To ensure that contesters can connect, we need to have a leader node, which is responsible for handling the connections. Connection will be established using the leader nodes IP. If a player connects to a non-leader node, this node will provide the correct IP to connect to.

For the project we will be using Docker and Python to build the distributed card game.

## The Nodes

In our approach, all the nodes are going to run identical software. We have the following node types:

- Leader node: This node will be responsible for ensuring the card shuffling is done confidentially by holding the encryption keys for the cards in the deck, and it will also be responsible for synchronizing the turns. The leader node starts the card shuffling by encrypting each card, then shuffles the deck and passes the deck to a random player, which then encrypts the cards again and shuffles the deck. This node is selected with leader election and changes only if he drops out from the session. After each participant has picked up a card, they can ask for the decryption keys from the leader node and the other node that was involved in shuffling.
- Participant node: Will be playing in the game and potentially helping with the shuffling of the encrypted deck. Will be picking up a card from the shuffled deck.

## Scalability

The chosen approach should scale to some degree. It should be possible to add many participants to the game -- the main limitation of scalability is that everyone is connecting to every other participant, meaning that at some point each node has too many connections. However, the protocol used here is so lightweight that the number of participants would need to grow to be very large before anyone is overwhelmed with messages. The scalability of the approach could be improved by utilizing a structured peer-to-peer network.

## Messages
These are some concepts for the messages and will not be final versions.

```json
{
    "sender": <sender_id>,
    "message_type": "join" | "leave" | "shuffle" | "deck" | "request_key",
    "message": see message types below
}
```
Message Type: join
```json
{
    "ip": <sender_ip>
}
```
Message Type: leave
```json
{
    "id": <sender_id>
}
```
Message Type: shuffle
```json
{
    "deck": [list of cards, order matters]
}
```
Message Type: deck
```json
{
    "deck": [list of cards, order matters]
}
```
Message Type: request_key
```json
{
    "card": <which card's key is requested>
}
```

<Some message to publish which card the player picked, or peraps this is with request_key>

### Responses:

Reponse to join
```json
{
    "leader": <leader_id>,
    "assigned_id": <id asigned by leader>
    "clients": [list of (client_id, client_ip) pairs]
}
```
Reponse to request_key
```json
{
    "key": <key>
}
```
