.PHONY: eval test

eval:
	python -m testbudget.replay \
		--history fixtures/history_small \
		--output data/eval_results.csv

test:
	python -m pytest -q
