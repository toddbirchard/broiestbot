"""Gunicorn configuration file."""

from os import environ, path

from dotenv import load_dotenv

# Read environment variables from ".env" file.
BASE_DIR = path.abspath(path.dirname(__file__))
load_dotenv(path.join(BASE_DIR, ".env"))

# Fetch deployment environment from environment variables.
ENVIRONMENT = environ.get("ENVIRONMENT")

proc_name = "broiestbot"
wsgi_app = "wsgi:app"
bind = "unix:broiestbot.sock"
threads = 8
workers = 4

if ENVIRONMENT == "development" or ENVIRONMENT is None:
    reload = True
    workers = 1
    threads = 1
    bind = ["127.0.0.1:8005"]
elif ENVIRONMENT == "production":
    access_log_format = "%(h)s %(l)s %(u)s %(t)s %(r)s %(s)s %(b)s %(f)s %(a)s"
    daemon = True
    accesslog = "/var/log/broiestbot/info.json"
    errorlog = "/var/log/broiestbot/error.json"
    loglevel = "trace"
    dogstatsd_tags = "env:production,service:broiest,language:python"
else:
    raise ValueError(f"Unknown environment provided: `{ENVIRONMENT}`. Must be `development` or `production`.")
