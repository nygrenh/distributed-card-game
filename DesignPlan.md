# Card Game

Our idea is to create a distributed card game, where each participant is involved in shuffling a card deck and this card deck is then used to play a simple card game.

Group name: -
Members: Daniel Koch, Henrik Nygren, Sebastian Sergelius

## Detailed description of our idea

Our project will consist of a very simple card game where we have one card deck containing 52 cards. First step is to shuffle the card deck with some N contesters (nodes) in a manner where cheating is hard or impossible. After the deck has been shuffled we randomly choose a contester to pick up the card on top of the deck and then in a clockwise order all the other contesters pick up the following card on top of the deck. Once each contester has picked up their card, they turn them around and the winner will be the contester with the highest card.

To ensure cheating doesn't happen while shuffling the cards, we still haven't decided on which method for implementation we will use, but we've found potential solutions, such as:
* https://en.wikipedia.org/wiki/Mental_poker#Shuffling_cards_using_commutative_encryption
* http://forensics.umass.edu/pubs/baughman.ToN.pdf
* https://www.cs.du.edu/~chrisg/publications/pittman-netgames11.pdf

Each contester will be running the same underlying system, which we will built upon using docker/docker-compose. To ensure that contesters can connect, we need to have a master node, which is responsible for handling the connections. Connection will be established using the master nodes IP or if possible, any contesters IP-address.

For the project we will be using Docker and Python to build the distributed card game.

## The nodes

In our approach, all the nodes are going to run identical software. We have the following node types:

- Leader node: This node will be responsible for ensuring the card shuffling is done confidentially by holding the encryption keys for the deck being shuffled in the game, and it will also be responsible for synchronizing the turns. The leader node deals cards from the encrypted deck to the others. This node is selected with leader election and changes after each round. If the leader node drops out or cheats, it will be penalized somehow, and a new leader node will be elected. After the game has ended, the leader node's responsibility is to release the encryption keys for the shuffled deck so that others can validate that there has been no cheating.
- Participant node: Will be playing in the game and potentially helping with the shuffling of the encrypted deck. Holds a copy of the encrypted deck and will validate the that the leader node did not cheat upon receiving the encryption keys at the end of the game. At the beginning of the round, the participant node will decide whether they want to continue in the game and whether they are willing to bet money in this game round.

## Scalability

The chosen approach should scale to some degree. It should be possible to add many participants to the game -- the main limitation of scalability is that everyone is connecting to every other participant, meaning that at some point each node has too many connections. However, the protocol used here is so lightweight that the number of participants would need to grow to be very large before anyone is overwhelmed with messages. The scalability of the approach could be improved by utilizing a structured peer-to-peer network.

## Messages
Identifying the message types isnt completely possible yet since we haven't decided the algorithm yet, however
here is some possible examples:

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
    "master": <master_id>,
    "assigned_id": <id asigned by master>
    "clients": [list of (client_id, client_ip) pairs]
}
```
Reponse to request_key
```json
{
    "key": <key>
}
```
