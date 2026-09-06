# textbook-retrieval-pipeline — operator entrypoints (see CLAUDE.md "Commands").
# `make chapter BOOK=<id> CH=<slug>` (stages 2-4) is added by the first implementation plan.

SHELL := /bin/bash
.DEFAULT_GOAL := help

# CUDA index in PCI_BUS_ID order (= nvidia-smi index). 0 = RTX PRO 6000 Blackwell on the server box.
GPU ?= 0
PORT ?= 30000
# mineru 3.4.5 defaults to 0.5; a 1.2B VLM needs far less (0.3 ~= 30 GB incl. KV cache on 96 GB).
GPU_MEM_UTIL ?= 0.3
# The VLM mineru 3.4.5 uses by default, pinned to the commit validated at gate 1 (2026-09-06).
# To move: `make weights VLM_REVISION=<sha>`, validate, then update the default here.
VLM_REPO ?= opendatalab/MinerU2.5-Pro-2605-1.2B
VLM_REVISION ?= bff20d4ae2bf202df9f45284b4d43681555a97ed
# Optional Hugging Face mirror for `make weights`, e.g. HF_ENDPOINT=https://hf-mirror.com.
# Exported only when set: an empty HF_ENDPOINT would break huggingface_hub's URLs.
HF_ENDPOINT ?=
ifneq ($(strip $(HF_ENDPOINT)),)
export HF_ENDPOINT
endif
MIRROR ?= https://pypi.tuna.tsinghua.edu.cn/simple

.PHONY: help sync-server weights serve

help:
	@echo "make sync-server  Install/refresh the 'server' extra via the TUNA mirror; uv.lock stays on pypi.org."
	@echo "make weights      Download $(VLM_REPO)@$(VLM_REVISION) into the HF cache (idempotent)."
	@echo "make serve        MinerU VLM server on GPU $(GPU), port $(PORT). Server box only; Ctrl-C stops."
	@echo "Variables: GPU PORT GPU_MEM_UTIL VLM_REPO VLM_REVISION HF_ENDPOINT MIRROR"

# Large wheels (torch, vLLM, CUDA libs) stall from PyPI's origin CDN on this network; the TUNA
# mirror serves them. But a different index makes uv relock, so uv.lock is backed up, the mirror
# sync runs, and the backup is restored once every name/version pin matches (marker-only
# differences are expected and harmless). Only needed when torch/vllm/CUDA-library pins change.
sync-server:
	@bak=$$(mktemp); cp uv.lock "$$bak"; echo "uv.lock backed up to $$bak"; \
	UV_DEFAULT_INDEX=$(MIRROR) UV_HTTP_TIMEOUT=120 UV_CONCURRENT_DOWNLOADS=8 uv sync --extra server \
	  || { echo "uv sync failed - pypi.org uv.lock restored" >&2; cp "$$bak" uv.lock; exit 1; }; \
	pins() { grep -E '^(name|version) = ' "$$1"; }; \
	if diff <(pins "$$bak") <(pins uv.lock) >/dev/null; then \
	  cp "$$bak" uv.lock; rm -f "$$bak"; echo "all pins identical - pypi.org uv.lock restored"; \
	else \
	  echo "ERROR: the mirror resolved different versions (below). pypi.org uv.lock restored; .venv may" >&2; \
	  echo "       differ for these packages - rerun later, or 'uv sync --extra server' to reconcile." >&2; \
	  diff <(pins "$$bak") <(pins uv.lock) >&2 || true; cp "$$bak" uv.lock; exit 1; \
	fi

# Uses the venv's `hf` (huggingface-hub is pinned in uv.lock), not a global install. Files already
# in the cache are not re-downloaded; stdout is the snapshot path, progress goes to stderr.
weights:
	@p=$$(uv run --no-sync hf download $(VLM_REPO) --revision $(VLM_REVISION)) \
	  || { echo "download failed. If Hugging Face is slow from here: make weights HF_ENDPOINT=https://hf-mirror.com" >&2; exit 1; }; \
	echo "weights ready: $$p"; echo "  $$(find -L "$$p" -type f | wc -l) files, $$(du -shL "$$p" | cut -f1)"

# The model path is resolved from the cache offline and passed explicitly, so the server never
# depends on Hugging Face at start and always serves the pinned revision.
serve:
	@uv pip show vllm >/dev/null 2>&1 || { echo "vllm is not installed in .venv - run 'make sync-server' first" >&2; exit 1; }
	@model=$$(HF_HUB_OFFLINE=1 uv run --no-sync hf download $(VLM_REPO) --revision $(VLM_REVISION) --quiet 2>/dev/null) \
	  || { echo "$(VLM_REPO)@$(VLM_REVISION) is not in the HF cache - run 'make weights' first" >&2; exit 1; }; \
	echo "+ mineru-openai-server --model $$model --port $(PORT) --gpu-memory-utilization $(GPU_MEM_UTIL)  (GPU $(GPU))"; \
	CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=$(GPU) HF_HUB_OFFLINE=1 \
	uv run --no-sync mineru-openai-server --model "$$model" --port $(PORT) --gpu-memory-utilization $(GPU_MEM_UTIL)
