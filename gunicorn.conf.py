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
bind = ["127.0.0.1:8005"]
reload = True
threads = 1
workers = 1

if ENVIRONMENT == "development" or ENVIRONMENT is None:
    errorlog = "logs/gunicorn_errors.log"
    capture_output = False
elif ENVIRONMENT == "production":
    daemon = True
    accesslog = f"/var/log/{proc_name}/access.log"
    errorlog = f"/var/log/{proc_name}/errors.log"
    capture_output = True
    ca_certs = "creds/ca-certificate.crt"
    dogstatsd_tags = "env:production,service:broiest,language:python"
else:
    raise ValueError(f"Unknown environment provided: `{ENVIRONMENT}`. Must be `development` or `production`.")
