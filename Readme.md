# Distributed card game

Requirements:

* Python 3.9
* Poetry (https://python-poetry.org/)
* Docker (tested with Docker version 20.10.7)
* docker-compose (1.29.2)

First line is for Visual Studio Code support.
```bash
poetry config virtualenvs.in-project true
poetry install
```

## Running

### Easy way

Easily started by running `./start-tmux.sh` and switching to tab 0 (Ctrl + b and 0).
To get node IP, go to tab 1 (Ctrl + b and 1) and run `docker network inspect distributed-card-game_default`.

You can see logs of all processes in tab 0.

To start over, go to tab 0 and press `Ctrl + c` then type in `tmux kill-server`.
### Hard way

In one terminal, run `docker-compose up --build`.

Then get the ip addresses of the containers by running `docker network inspect distributed-card-game_default`.

Attach to a running container by running `docker ps` and e.g. `docker attach distributed-card-game-app-3`.
