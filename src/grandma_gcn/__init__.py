# needed to register the tasks for celery
import importlib

importlib.import_module("grandma_gcn.worker.gwemopt_worker")
importlib.import_module("grandma_gcn.worker.swift_html_worker")
