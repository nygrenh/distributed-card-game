#!/bin/bash

tmux new-session -d -s foo
tmux rename-window 'docker-compose'
tmux send-keys -t foo:0 'docker-compose up --build'

tmux new-window -t foo:1
tmux rename-window -t foo:1 'info'
tmux send-keys -t foo:1 'docker network inspect distributed-card-game_default'

tmux new-window -t foo:2
tmux rename-window -t foo:2 'replica 1'
tmux send-keys -t foo:2 'docker attach distributed-card-game-app-1'

tmux new-window -t foo:3
tmux rename-window -t foo:3 'replica 2'
tmux send-keys -t foo:3 'docker attach distributed-card-game-app-2'

tmux new-window -t foo:4
tmux rename-window -t foo:4 'replica 3'
tmux send-keys -t foo:4 'docker attach distributed-card-game-app-3'

tmux new-window -t foo:5
tmux rename-window -t foo:5 'replica 4'
tmux send-keys -t foo:5 'docker attach distributed-card-game-app-4'

tmux new-window -t foo:6
tmux rename-window -t foo:6 'replica 5'
tmux send-keys -t foo:6 'docker attach distributed-card-game-app-5'

tmux new-window -t foo:7
tmux rename-window -t foo:7 'replica 6'
tmux send-keys -t foo:7 'docker attach distributed-card-game-app-6'

tmux -2 attach-session -t foo

