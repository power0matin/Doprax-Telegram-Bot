SHELL := /bin/bash

.PHONY: install lint format typecheck test run build clean

install:
	python -m pip install -U pip
	python -m pip install -e ".[dev]"

format:
	ruff format .

lint:
	ruff check .

typecheck:
	mypy src tests

test:
	pytest -q

run:
	python -m bot.main

build:
	python -m build

clean:
	rm -rf dist build .pytest_cache .mypy_cache .ruff_cache
