# Final Report

In this project, we will create a distributed card game, where the goal is to get dealt the highest card. The participants will connect to each in peer-to-peer fashion, and the system will try to ensure that the card deck in the game will be shuffled fairly.

## Card game

Group name: - #27

Members: Daniel Koch, Henrik Nygren, Sebastian Sergelius

## Table of Contents


## Project Goal

Our project will be a very simple card game where we have one card deck containing 52 cards. Cards are numbered from 1 to 52. First step is to shuffle the card deck with two nodes, one being leader and other being a random player in the game, in a manner where cheating is hard or impossible. After the deck has been shuffled, we deal each participant a card in ascending order based on their player number. Once each participant has been dealt their card, they can decrypt the whole deck and verify the game.

To ensure cheating doesn't happen while shuffling the cards, we will implement the Mental poker card shuffling algorithm: [https://en.wikipedia.org/wiki/Mental_poker#Shuffling_cards_using_commutative_encryption](https://en.wikipedia.org/wiki/Mental_poker#Shuffling_cards_using_commutative_encryption).

Each participant will run the same software, which will be a Python program running on top of Docker. To ensure that participant can connect, we need to have a leader node, which admits new nodes to the game. Connections will be established using the leader nodes' IP. If a player connects to a non-leader node, this node will provide the correct IP to connect to.

## Core functionality

Our environment is built on docker containers, each container running the same code. Commands from nodes will be taken from STDIN in terminal. Before each command we check that the leader node is alive and healthy.

The following commands are available:
* `join <ip>` - joins an ongoing game or creates a game if first participant joining the IP
* `leave` - leaves the game
* `list` - list the state the node knows off

### Creating and joining a game

Each participant will be running the same environment. First participant node will join another (leader) node, which will define the leader node. The first joining participant will provide the leader node its IP-address it used to join with. Once another participant node joins, he can join any of the participants in the game.

### Leaving a game

A participant can leave the game. Once the participants leaves the game, the leader node will broadcast the updated player list to all nodes in game.

### Playing the game

The game can start once players have joined. Leader node broadcasts that game is starting. Leader picks another node who he uses to shuffle the deck with. Once deck is shuffled, each player can lift a card.

## Design Principles

## Functionalities

### Naming and node discovery

Each participant is named by a number.
### Consistency and synchronization

Consistency is achieved by broadcasting the joining and leaving nodes. If a node has crashed, this node will not be able to send a leave request. The leader node will constantly ensure that each node is in the game, if the player doesn't pick up the card or answer in a sufficient time, the node will be marked as dead. Other nodes do not need to know about these dead nodes, because the leader node will broadcast once the game has ended, by timeout or if every alive node has picked up his card.

If the leader crashes, a leader election should start, once the leader election is done, the new leader will ensure that all the nodes he knows about is alive and responds to a heartbeat.

### Fault tolerance

During programming, we noticed that some failures are possible, such as a participant dropping out of the game or not picking up a card.
If a participant drops out of the game, he will be part of the game and able to join back later, if he has the same IP-address.
Timeout is used by the leader once the game has started and the deck is shuffled. If a participant does not respond, he will not be part of the game.

Every time a node sends a command to the leader, it checks for the leader nodes health, if the leader doesn't answer within 5 seconds, we will start the Reverse Bully Algorithm (prefers small numbers).
### Consensus

Consensus is achieved when each participant sends their (encrypted) picked card up to every other participant, these participants then decrypt all cards with keys asked from two shuffling partners. Once everyone has decrypted every participant's card, the leader will broadcast the result of the game, and we will vote if the game was valid to the leader. If we have a consensus, the highest card wins.


## System scalability

The chosen approach should scale to some degree. It should be possible to add many participants to the game. One major limitation of scalability could be the fact that is that everyone is connecting to every other participant, meaning that at some point, each node has too many connections. However, the protocol used here is so lightweight that the number of participants would need to grow to be very large before anyone would be overwhelmed with messages. The scalability of the approach could be improved by utilizing a structured peer-to-peer network.

## Performance

The performance of the game is asynchronous. Performance wise there is no issue when shuffling the game deck, as currently we have 52 cards, but with a big amount of participants and a bigger deck this could cause an issue when each player has lifted their card, as once they have lifted their card, they will broadcast to each participant their encrypted card. Each player will then request the encryption keys from the leader and the randomly selected other participant, who was involved in shuffling the deck and then each player can decrypt other players cards and his own.

This encryption and decryption purpose is to make sure that no one is cheating and we can reach a consensus if there was some cheating.

## Lessons learned


## Appendix

-

