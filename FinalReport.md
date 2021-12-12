# Final Report

In this project, we will create a distributed card game, where the goal is to get dealt the highest card. The participants will connect to each in peer-to-peer fashion, and the system will try to ensure that the card deck in the game will be shuffled fairly.

## Card game

Group name: - #27

Members: Daniel Koch, Henrik Nygren, Sebastian Sergelius

## Table of Contents


## Project Goal

Our project will be a very simple card game where we have one card deck containing 52 cards. Cards are numbered from 1 to 52. First step is to shuffle the card deck with two nodes, one being leader and other being a random player in the game, in a manner where cheating is hard or impossible. After the deck has been shuffled, we randomly choose a participant to pick up the card on top of the deck and then the leader node decides the turns when each player may pick up a card from the top of the deck. Once each participant has picked up their card, they turn them around and the winner will be the participant with the highest card.

To ensure cheating doesn't happen while shuffling the cards, we will implement the Mental poker card shuffling algorithm: [https://en.wikipedia.org/wiki/Mental_poker#Shuffling_cards_using_commutative_encryption](https://en.wikipedia.org/wiki/Mental_poker#Shuffling_cards_using_commutative_encryption).

Each participant will run the same software, which will be a Python program running on top of Docker. To ensure that participant can connect, we need to have a leader node, which admits new nodes to the game. Connections will be established using the leader nodes' IP. If a player connects to a non-leader node, this node will provide the correct IP to connect to.

## Core functionality

Our environment is built on docker containers, each container running the same code. Commands from nodes will be taken from STDIN in terminal. Before each command we check that the leader node is alive and healthy.

The following commands are available:
* `join <ip>` - joins an ongoing game or creates a game if first participant joining the IP
* `leave` - leaves the game


### Creating and joining a game

Each participant will be running the same environment. First participant node will join another (leader) node, which will define the leader node. The first joining participant will provide the leader node its IP-address it used to join with. Once another participant node joins, he can join any of the participants in the game. Participants will provide the leader node IP, which will then returned to joining participant, so he knows where to route his join request.

Leader node will be the one who accepts join request, names the participants with running integer and broadcasts to all other players the current state, i.e. the participants.

### Leaving a game

A participant can leave the game. Once the participants leaves the game, the master node will broadcast the player list to all nodes in game.

###

## Design Principles

