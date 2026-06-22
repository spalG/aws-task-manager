# gunicorn.conf.py — Production server config
import multiprocessing

bind            = "0.0.0.0:5000"
workers         = multiprocessing.cpu_count() * 2 + 1
worker_class    = "sync"
timeout         = 30
keepalive       = 5
accesslog       = "-"
errorlog        = "-"
loglevel        = "info"
preload_app     = True
