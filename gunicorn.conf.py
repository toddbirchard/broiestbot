import multiprocessing
from config import ENVIRONMENT

# General
wsgi_app = "main:init_bot"
proc_name = "broiestbot"
host = "127.0.0.1"

if ENVIRONMENT == "production":
    daemon = True

# Threading & Workers
workers = 1
threads = multiprocessing.cpu_count() * 4

# Debugging
if ENVIRONMENT == "development":
    reload = True
