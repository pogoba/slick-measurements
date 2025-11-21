.PHONY: repl

OUT_DIR := ./
ROOT_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
PYARGS :=
PAPER_FIGURES := app-throughput.pdf chain-scalability.pdf microbenchmarks.pdf

WIDTH := 5.0
WIDTH2 := 5.5
DWIDTH := 11
DWIDTH2 := 13
TWIDTH := 3.5

repl:
	bpython -i <(echo 'import importlib.util; import sys; spec = importlib.util.spec_from_file_location("module.name", "${ROOT_DIR}/bpython.py"); repl = importlib.util.module_from_spec(spec); sys.modules["module.name"] = repl; spec.loader.exec_module(repl); repl.reload()')
	# bpython -i ${ROOT_DIR}/bpython.py



all: $(PAPER_FIGURES)

install:
	test -n "$(OVERLEAF)" # OVERLEAF must be set
	for f in $(PAPER_FIGURES); do test -f $(OUT_DIR)/$$f && cp $(OUT_DIR)/$$f $(OVERLEAF)/$$f || true; done


app-throughput.pdf:
	python3 $(PYARGS) app-throughput.py \
		-o $(OUT_DIR)/app-throughput.pdf \
		--width $(WIDTH) --height 2 \
		--1 ./flake.nix

chain-scalability.pdf:
	python3 $(PYARGS) chain-scalability.py \
		-o $(OUT_DIR)/chain-scalability.pdf \
		--width $(WIDTH) --height 2 \
		--1 ./flake.nix

microbenchmarks.pdf:
	python3 $(PYARGS) microbenchmarks.py \
		-o $(OUT_DIR)/microbenchmarks.pdf \
		--width $(DWIDTH) --height 2 \
		--1 ./flake.nix

packet-overhead.pdf:
	python3 $(PYARGS) packet-overhead.py \
		-o $(OUT_DIR)/packet-overhead.pdf \
		--width $(TWIDTH) --height 2.5 \
		--1 ./flake.nix
