# Distributed card game

Requirements:

* Python 3.9
* Poetry (https://python-poetry.org/)

First line is for Visual Studio Code support.

```bash
poetry config virtualenvs.in-project true
poetry install
```

## Running

In one terminal, run `docker-compose up --build`.

Then get the ip addresses of the containers by running `docker network inspect distributed-card-game_default`.

Attach to a running container by running `docker ps` and e.g. `docker attach distributed-card-game-app-3`.
