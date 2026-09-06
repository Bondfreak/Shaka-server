.PHONY: test smoke-f1 smoke-f1-http

test:
	pytest -q

smoke-f1:
	python scripts/smoke_f1_runtime.py --mode testclient

smoke-f1-http:
	python scripts/smoke_f1_runtime.py --mode http --base-url http://127.0.0.1:8000
