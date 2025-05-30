# needed to register the tasks for celery
import importlib

importlib.import_module("grandma_gcn.worker.gwemopt_worker")
