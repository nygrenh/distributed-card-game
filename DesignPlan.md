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