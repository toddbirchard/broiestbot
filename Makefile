PROJECT_NAME := $(shell basename $CURDIR)
VIRTUAL_ENVIRONMENT := $(CURDIR)/.venv
LOCAL_PYTHON := $(VIRTUAL_ENVIRONMENT)/bin/python
LOCAL_PYTHON_ACTIVATE := $(VIRTUAL_ENVIRONMENT)/bin/activate

define HELP
Manage $(PROJECT_NAME). Usage:

make run        - Run $(PROJECT_NAME) locally.
make install    - Create local virtualenv & install dependencies.
make deploy     - Set up project & run locally.
make update     - Update dependencies via Poetry and output resulting `requirements.txt`.
make format     - Run Python code formatter & sort dependencies.
make lint       - Check code formatting with flake8.
make clean      - Remove extraneous compiled files, caches, logs, etc.

endef
export HELP

.PHONY: run install deploy update format lint clean help


all help:
	@echo "$$HELP"

env: $(VIRTUAL_ENVIRONMENT)

$(VIRTUAL_ENVIRONMENT):
	if [ ! -d $(VIRTUAL_ENVIRONMENT) ]; then \
		echo "Creating Python virtual environment..."; \
		python -m venv $(VIRTUAL_ENVIRONMENT); \
	fi

.PHONY: run
run: env
	$(LOCAL_PYTHON) -m gunicorn --config=gunicorn.conf.py

.PHONY: install
install: env
	$(LOCAL_PYTHON) -m pip install --upgrade pip setuptools wheel && \
	$(LOCAL_PYTHON) -m pip install -r requirements.txt && \
	echo "Installed dependencies in virtualenv \`${VIRTUAL_ENVIRONMENT}\`";

.PHONY: deploy
deploy:
	make clean \
	make install \
	make run

.PHONY: test
test: env
	$(LOCAL_PYTHON) -m \
		coverage run -m pytest -v \
		--disable-pytest-warnings && \
		coverage html --title='Coverage Report' -d .reports && \
		open .reports/index.html

.PHONY: update
update: env
	$(LOCAL_PYTHON) -m pip install --upgrade pip setuptools wheel && \
	poetry update && \
	poetry export -f requirements.txt --output requirements.txt --without-hashes && \
	echo "Updated dependencies in virtualenv \`${VIRTUAL_ENVIRONMENT}\`";

.PHONY: format
format: env
	source $(LOCAL_PYTHON_ACTIVATE) \
	isort --multi-line=3 . \
	&& black .

.PHONY: lint
lint: env
	$(LOCAL_PYTHON) -m flake8 . --count \
			--select=E9,F63,F7,F82 \
			--exclude .git,.github,__pycache__,.pytest_cache,.venv,logs,creds,.venv,docs,logs,.reports \
			--show-source \
			--statistics

.PHONY: clean
clean:
	find . -name 'poetry.lock' -delete && \
	find . -name '.coverage' -delete && \
	find . -wholename '**/*.pyc' -delete && \
	find . -wholename '**/logs/*.json' -exec rm -rf {} + && \
	find . -wholename '**/logs/*.log' -exec rm -rf {} + && \
	find . -type d -wholename '__pycache__' -exec rm -rf {} + && \
	find . -type d -wholename '.venv' -exec rm -rf {} + && \
	find . -type d -wholename '.pytest_cache' -exec rm -rf {} + && \
	find . -type d -wholename '**/.pytest_cache' -exec rm -rf {} + && \
	find . -type d -wholename './.reports/*' -exec rm -rf {} +