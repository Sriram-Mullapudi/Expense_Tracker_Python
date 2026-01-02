.PHONY: install run docker-build docker-up test

install:
	python -m pip install --upgrade pip
	pip install -r requirements.txt

run:
	python app.py

docker-build:
	docker build -t expense-tracker:latest .

docker-up:
	docker-compose up --build -d

test:
	pytest -q
