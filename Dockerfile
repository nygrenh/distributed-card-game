FROM python:3.9.7-bullseye

WORKDIR /app

RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python3 -
ENV PATH = "${PATH}:/root/.poetry/bin"

COPY pyproject.toml poetry.lock /app/

RUN poetry install

COPY . /app/

CMD [ "poetry", "run", "python3", "src/main.py" ]
