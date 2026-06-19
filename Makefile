.PHONY: repl

OUT_DIR := ./pdfs/out26-output7-mem
DATA := ./data/out26-output7-mem
ROOT_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
PYARGS :=
PAPER_FIGURES := app-throughput.pdf chain-scalability.pdf microbenchmarks.pdf packet-overhead.pdf

WIDTH := 5.0
WIDTH2 := 5.5
WIDTH3 := 3.5
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
		--width $(WIDTH2) --height 2 \
    --1-name "Containers" --1 $(DATA)/vm_containers_real_b32_0ns_0b_c3_*b_rep*.log \
    --2-name "Kata" --2 $(DATA)/vm_kata_real_b32_0ns_0b_c3_*b_rep*.log \
    --3-name "Strawman" --3 $(DATA)/multivm_mirror_real_b32_0ns_0b_c0_v3_*b_rep*.log \
    --4-name "Slick" --4 $(DATA)/vm_iomgr_real_b32_0ns_0b_c3_*b_rep*.log \

    # --1-name "Un-isolated" --1 $(DATA)/vm_insecure_real_b32_0ns_0b_c3_*b_rep*.log \
    # --3-name "Naive" --3 $(DATA)/vm_noiomgr_real_b32_0ns_0b_c3_*b_rep*.log \


# works with ./data/out12-output4
chain-scalability.pdf:
	python3 $(PYARGS) chain-scalability.py \
		-o $(OUT_DIR)/chain-scalability.pdf \
		--width $(WIDTH) --height 2.3 \
    --1-name "Containers" --1 $(DATA)/vm_containers_synthetic_b32_0ns_0b_c*_1500b_rep*.log \
    --2-name "Kata" --2 $(DATA)/vm_kata_synthetic_b32_0ns_0b_c*_1500b_rep*.log \
    --3-name "Un-isolated" --3 $(DATA)/vm_insecure_synthetic_b32_0ns_0b_c*_1500b_rep*.log \
    --4-name "Strawman" --4 $(DATA)/multivm_mirror_synthetic_b32_0ns_0b_c0_v*_1500b_rep*.log \
    --5-name "Naive" --5 $(DATA)/vm_noiomgr_synthetic_b32_0ns_0b_c*_1500b_rep*.log \
    --6-name "Slick" --6 $(DATA)/vm_iomgr_synthetic_b32_0ns_0b_c*_1500b_rep*.log \
    \
    --lat-1-name "Containers" --lat-1 $(DATA)/vm_lat_containers_synthetic_b32_0ns_0b_c*_1500b_rep*.log \
    --lat-2-name "Kata" --lat-2 $(DATA)/vm_lat_kata_synthetic_b32_0ns_0b_c*_1500b_rep*.log \
    --lat-3-name "Un-isolated" --lat-3 $(DATA)/vm_lat_insecure_synthetic_b32_0ns_0b_c*_1500b_rep*.log \
    --lat-4-name "Strawman" --lat-4 $(DATA)/multivm_lat_mirror_synthetic_b32_0ns_0b_c0_v*_1500b_rep*.log \
    --lat-5-name "Naive" --lat-5 $(DATA)/vm_lat_noiomgr_synthetic_b32_0ns_0b_c*_1500b_rep*.log \
    --lat-6-name "Slick" --lat-6 $(DATA)/vm_lat_iomgr_synthetic_b32_0ns_0b_c*_1500b_rep*.log \


microbenchmarks.pdf:
	python3 $(PYARGS) microbenchmarks.py \
		-o $(OUT_DIR)/microbenchmarks.pdf \
		--width $(WIDTH) --height 4.3 \
    --1-name "Containers" --1 $(DATA)/vm_containers_synthetic_b32_*ns_*b_c2_*b_rep*.log \
    --2-name "Kata" --2 $(DATA)/vm_kata_synthetic_b32_*ns_*b_c2_*b_rep*.log \
    --3-name "Strawman" --3 $(DATA)/multivm_mirror_synthetic_b32_*ns_*b_c0_v2_*b_rep*.log \
    --4-name "Slick" --4 $(DATA)/vm_iomgr_synthetic_b32_*ns_*b_c2_*b_rep*.log \
    \
    --lat-2-name "Kata" --lat-2 $(DATA)/vm_lat_kata_synthetic_b32_*ns_*b_c2_*b_rep*.log \
    --lat-3-name "Strawman" --lat-3 $(DATA)/multivm_lat_mirror_synthetic_b32_*ns_*b_c0_v2_*b_rep*.log \
    --lat-4-name "Slick" --lat-4 $(DATA)/vm_lat_iomgr_synthetic_b32_*ns_*b_c2_*b_rep*.log \

    # --lat-1-name "Containers" --lat-1 $(DATA)/vm_lat_containers_synthetic_b32_*ns_*b_c2_*b_rep*.log \

    # --3-name "Naive" --3 $(DATA)/vm_noiomgr_synthetic_b32_*ns_*b_c2_*b_rep*.log \
    # --1-name "Un-isolated" --1 $(DATA)/vm_insecure_synthetic_b32_*ns_*b_c2_*b_rep*.log \
    # --lat-1-name "Un-isolated" --lat-1 $(DATA)/vm_lat_insecure_synthetic_b32_*ns_*b_c2_*b_rep*.log \
    # --lat-3-name "Naive" --lat-3 $(DATA)/vm_lat_noiomgr_synthetic_b32_*ns_*b_c2_*b_rep*.log \

#    --1-name "Optimal" --1 $(DATA)/userspace_mirror_b32_*ns_0b_c2_*b_rep*.log \

#  	--1-name "Slick" --1 ./data/out1/userspace_iomgr_b32_*ns_c1_64b_rep*.log \
#  	--2-name "Naive" --2 ./data/out1/userspace_noiomgr_b32_*ns_c1_64b_rep*.log

externalio.pdf:
	python3 $(PYARGS) externalio.py \
		-o $(OUT_DIR)/externalio.pdf \
		--width $(WIDTH2) --height 3 \
    --1-name "Containers (CVM)" --1 $(DATA)/vm_containers_*_b32_0ns_0b_c1_*b_rep*.log \
    --2-name "Kata (VM)" --2 $(DATA)/vm_kata_*_b32_0ns_0b_c1_*b_rep*.log \
    --3-name "DPDK (VM)" --3 $(DATA)/vm_mirrorUnconfidential_*_b32_0ns_0b_c1_*b_rep*.log \
    --4-name "Linux (CVM)" --4 $(DATA)/vm_mirrorKni_*_b32_0ns_0b_c1_*b_rep*.log \
    --5-name "Slick (CVM)" --5 $(DATA)/vm_mirror_*_b32_0ns_0b_c1_*b_rep*.log \

    # --2-name "DPDK (CVM)" --2 $(DATA)/vm_mirror_synthetic_b32_0ns_0b_c1_*b_rep*.log \


vnfletio.pdf:
	python3 $(PYARGS) vnfletio.py \
		-o $(OUT_DIR)/vnfletio.pdf \
		--width $(WIDTH2) --height 2 \
    --1-name "DPDK" --1 $(DATA)/vm_mirrorMicrobenchmark_*_b32_0ns_0b_c1_64b_rep*.log \
    --2-name "DPDK" --2 $(DATA)/vm_mirrorMicrobenchmark_*_b32_0ns_0b_c1_1500b_rep*.log \
    --5-name "Slick" --5 $(DATA)/vm_iomgrMicrobenchmark_*_b32_0ns_0b_c1_64b_rep*.log \
    --6-name "Slick" --6 $(DATA)/vm_iomgrMicrobenchmark_*_b32_0ns_0b_c1_1500b_rep*.log \
		-l \
    --3-name "Linux" --3 $(DATA)/vm_mirrorKniMicrobenchmark_*_b32_0ns_0b_c1_64b_rep*.log \
    --4-name "Linux" --4 $(DATA)/vm_mirrorKniMicrobenchmark_*_b32_0ns_0b_c1_1500b_rep*.log \

packet-overhead.pdf:
	python3 $(PYARGS) packet-overhead.py \
		-o $(OUT_DIR)/packet-overhead.pdf \
		--width $(TWIDTH) --height 2.5 \
		--1 ./flake.nix

network-performance.pdf:
	python3 $(PYARGS) network-performance.py \
		-o $(OUT_DIR)/network-performance.pdf \
		--width $(TWIDTH) --height 2.5 \
		--1-name "VM" --1 $(DATA)/iperf_haltpoll_forward_rep*.log \
		--2-name "swiotlb" --2 $(DATA)/iperf_swiotlb_forward_rep*.log \
		--3-name "vhost" --3 $(DATA)/iperf_vhost_forward_rep*.log \
		--4-name "snp" --4 $(DATA)/iperf_snp_forward_rep*.log \
		--5-name "snp-vhost" --5 $(DATA)/iperf_snp_vhost_forward_rep*.log \
		--6-name "snp-ipoll" --6 $(DATA)/iperf_poll_forward_rep*.log \
		--7-name "snp-vhost-ipoll" --7 $(DATA)/iperf_poll_vhost_forward_rep*.log \
		--8-name "snp-hpoll" --8 $(DATA)/iperf_haltpoll_forward_rep*.log \
		--9-name "vhost-user" --9 $(DATA)/iperf_vhost_user_forward_rep*.log \


message-size.pdf:
	python3 $(PYARGS) message-size.py \
		-o $(OUT_DIR)/message-size.pdf \
		--width $(WIDTH3) --height 2.5 \
		--1-name "Containers" --1 $(DATA)/vm_containers_synthetic_b32_0ns_0b_c1_*b_rep0.log \
		--2-name "Kata" --2 $(DATA)/vm_kata_synthetic_b32_0ns_0b_c1_*b_rep0.log \
		--3-name "CVM" --3 $(DATA)/vm_mirrorKni_synthetic_b32_0ns_0b_c1_*b_rep0.log \
		--4-name "VM (DPDK)" --4 $(DATA)/vm_mirrorUnconfidential_synthetic_b32_0ns_0b_c1_*b_rep0.log \
		--5-name "Slick (DPDK)" --5 $(DATA)/vm_mirror_synthetic_b32_0ns_0b_c1_*b_rep0.log \

memory-consumption.pdf:
	python3 $(PYARGS) memory-consumption.py \
		-o $(OUT_DIR)/memory-consumption.pdf \
		--width $(WIDTH3) --height 2.5 \
		--1-name "VM" --1 $(DATA)/mem_vm_*_rep*.log \
		--2-name "Kata" --2 $(DATA)/mem_kata_*_rep*.log \
		--3-name "CVM" --3 $(DATA)/mem_cvm_*_rep*.log \

startup-time.pdf:
	python3 $(PYARGS) startup-time.py \
		-o $(OUT_DIR)/startup-time.pdf \
		--width $(WIDTH3) --height 2.5 \
		--1-name "all" --1 $(DATA)/startup.csv
