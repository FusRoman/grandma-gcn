# gunicorn_conf.py
bind = "0.0.0.0:5000"
workers = 4  # Number of worker processes for handling requests
threads = 2
timeout = 120
accesslog = "-"
errorlog = "-"
loglevel = "info"
