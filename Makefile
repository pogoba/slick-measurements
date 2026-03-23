.PHONY: repl

OUT_DIR := ./
DATA := ./data/out9-output2v2/
ROOT_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
PYARGS :=
PAPER_FIGURES := app-throughput.pdf chain-scalability.pdf microbenchmarks.pdf packet-overhead.pdf

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
		--width $(WIDTH) --height 4 \
    --1-name "Insecure" --1 $(DATA)/userspace_insecure_b32_*ns_*b_c2_*b_rep*.log \
    --2-name "Secure" --2 ./data/out10-output3v2/multivm_mirror_b32_*ns_*b_c0_v2_*b_rep*.log \
    --3-name "Naive" --3 $(DATA)/userspace_noiomgr_b32_*ns_*b_c2_*b_rep*.log \
    --4-name "Slick" --4 $(DATA)/userspace_iomgr_b32_*ns_*b_c2_*b_rep*.log \
    \
    --lat-1-name "Insecure" --lat-1 $(DATA)/vm_lat_insecure_b32_*ns_c2_*b_rep*.log \
    --lat-3-name "Naive" --lat-3 $(DATA)/vm_lat_noiomgr_b32_*ns_c2_*b_rep*.log \
    --lat-4-name "Slick" --lat-4 $(DATA)/vm_lat_iomgr_b32_*ns_c2_*b_rep*.log \

# missing:
#    --lat-2-name "Secure" --lat-2 $(DATA)/vm_lat_mirror_b32_*ns_c2_*b_rep*.log \

#    --1-name "Optimal" --1 $(DATA)/userspace_mirror_b32_*ns_0b_c2_*b_rep*.log \

#  	--1-name "Slick" --1 ./data/out1/userspace_iomgr_b32_*ns_c1_64b_rep*.log \
#  	--2-name "Naive" --2 ./data/out1/userspace_noiomgr_b32_*ns_c1_64b_rep*.log

packet-overhead.pdf:
	python3 $(PYARGS) packet-overhead.py \
		-o $(OUT_DIR)/packet-overhead.pdf \
		--width $(TWIDTH) --height 2.5 \
		--1 ./flake.nix
