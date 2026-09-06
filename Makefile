# textbook-retrieval-pipeline — operator entrypoints (see CLAUDE.md "Commands").
# `make chapter BOOK=<id> CH=<slug>` (stages 2-4) is added by the first implementation plan.
# Fresh server box: make sync-server && make server-models && make client-models && make serve
# Fresh client (e.g. the Mac): uv sync && make client-models

SHELL := /bin/bash
.DEFAULT_GOAL := help

# ---- server -----------------------------------------------------------------------------------
# CUDA index in PCI_BUS_ID order (= nvidia-smi index). 0 = RTX PRO 6000 Blackwell on the server box.
GPU ?= 0
PORT ?= 30000
# mineru 3.4.5 defaults to 0.5; a 1.2B VLM needs far less (0.3 ~= 30 GB incl. KV cache on 96 GB).
GPU_MEM_UTIL ?= 0.3
# PyPI mirror for `make sync-server` (large wheels stall from PyPI's origin CDN on this network).
MIRROR ?= https://pypi.tuna.tsinghua.edu.cn/simple

# ---- model weights (Hugging Face CLI practice) ------------------------------------------------
# * Use the venv's `hf` (huggingface-hub is pinned in uv.lock), never a global install.
# * Pin a commit sha per repo: reproducible, and a cached pinned snapshot resolves offline.
# * Download into the shared HF cache (~/.cache/huggingface/hub) - that is where mineru looks, so
#   nothing is fetched twice; `hf download` is idempotent and resumes partial (.incomplete) blobs.
# * Pass ONE `--include` followed by all patterns; a repeated `--include` silently keeps only the
#   last pattern (verified on huggingface-hub 0.36.2).
# * From this network, files >~100 MB run fast for a while, then stall to 0 KB/s. hf_fetch
#   therefore runs short-timeout attempts until `hf download` exits 0 (each attempt resumes).
# * hf-mirror.com does NOT work (fails huggingface_hub's metadata check). HF_ENDPOINT is only for
#   a genuine alternate endpoint and is exported only when set (empty would break the URLs).
HF_ATTEMPTS ?= 12
HF_ATTEMPT_SECS ?= 90
HF_ENDPOINT ?=
ifneq ($(strip $(HF_ENDPOINT)),)
export HF_ENDPOINT
endif

# Server model: the VLM mineru 3.4.5 serves (MinerU2.5-Pro, 1.2B params, ~2.2 GB in 13 files),
# pinned to the commit validated at gate 1 (2026-09-06). Needed on the GPU box only.
# To move: `make server-models VLM_REVISION=<sha>`, validate, then update the default here.
VLM_REPO ?= opendatalab/MinerU2.5-Pro-2605-1.2B
VLM_REVISION ?= bff20d4ae2bf202df9f45284b4d43681555a97ed

# Client models: what `hybrid-http-client` runs locally (CPU, CUDA or MPS), ~1.06 GB in total,
# pinned to the snapshot the fixture sanity run used (2026-09-06). mineru itself resolves `main`
# at run time; while main == this pin (true today) it finds these files and downloads nothing.
KIT_REPO ?= opendatalab/PDF-Extract-Kit-1.0
KIT_REVISION ?= ed6b654c018d742e65a17671e379c5e6ecc87ec9
#   OCR text detection   PP-OCRv6 small det  ~10 MB  finds text lines, masks inline formulas for OCR
#   OCR text recognition PP-OCRv6 small rec  ~21 MB  reads text only where a page has no text layer
#                        (default lang=ch covers English; other --lang values fetch extra small files)
#   Layout               PP-DocLayoutV2     ~215 MB  block boxes/types, inline-formula boxes, headings
#   Formula recognition  UniMERNet small    ~814 MB  *inline* formulas -> LaTeX, run on the client;
#                        display formulas, tables and charts go to the VLM instead.
#                        `mineru -f false` skips it (the `strat` routing case):
#                        make client-models KIT_MODELS="$$(make -s print-kit-base)"
KIT_MODELS_BASE = models/OCR/paddleocr_torch/ch_PP-OCRv6_small_det_infer.safetensors \
                  models/OCR/paddleocr_torch/ch_PP-OCRv6_small_rec_infer.safetensors \
                  models/Layout/PP-DocLayoutV2/*
KIT_MODELS ?= $(KIT_MODELS_BASE) models/MFR/unimernet_hf_small_2503/*

# hf_fetch(repo, revision, include-patterns): retry loop around `hf download`. Empty patterns =
# the whole repo. Exit 124 from `timeout` means the attempt stalled; the next one resumes.
define hf_fetch
for i in $$(seq 1 $(HF_ATTEMPTS)); do \
  timeout $(HF_ATTEMPT_SECS) uv run --no-sync hf download $(1) --revision $(2) $(if $(strip $(3)),--include $(foreach p,$(3),'$(p)')) && break; \
  rc=$$?; echo "attempt $$i/$(HF_ATTEMPTS): hf download exited $$rc (124 = stalled) - retrying, resumes where it stopped" >&2; \
  [ $$i -lt $(HF_ATTEMPTS) ] || { echo "giving up on $(1) after $(HF_ATTEMPTS) attempts" >&2; exit 1; }; \
done
endef

.PHONY: help sync-server server-models client-models serve print-kit-base need-chapter-args split extract

help:
	@echo "make sync-server    Install/refresh the 'server' extra via the TUNA mirror; uv.lock stays on pypi.org."
	@echo "make server-models  Download the VLM $(VLM_REPO)@$(VLM_REVISION) (~2.2 GB) into the HF cache."
	@echo "make client-models  Download the PDF-Extract-Kit models the hybrid client runs locally (~1.06 GB)."
	@echo "make serve          MinerU VLM server on GPU $(GPU), port $(PORT). Server box only; Ctrl-C stops."
	@echo "make split BOOK=<id> CH=<n>     Stage 1: work/<id>/chNN/chapter.pdf + meta.json"
	@echo "make extract BOOK=<id> CH=<n>   Stage 2: mineru hybrid-http-client -> chapter/hybrid_auto/ (FORCE=1 re-runs)"
	@echo "Variables: GPU PORT GPU_MEM_UTIL VLM_REPO VLM_REVISION KIT_REPO KIT_REVISION KIT_MODELS"
	@echo "           HF_ATTEMPTS HF_ATTEMPT_SECS HF_ENDPOINT MIRROR BOOK CH FORCE MINERU_SERVER_URL"

print-kit-base:
	@echo $(KIT_MODELS_BASE)

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

server-models:
	@$(call hf_fetch,$(VLM_REPO),$(VLM_REVISION),)
	@p=$$(HF_HUB_OFFLINE=1 uv run --no-sync hf download $(VLM_REPO) --revision $(VLM_REVISION) --quiet); \
	echo "server models ready: $$p"; echo "  $$(find -L "$$p" -type f | wc -l) files, $$(du -shL "$$p" | cut -f1)"

client-models:
	@$(call hf_fetch,$(KIT_REPO),$(KIT_REVISION),$(KIT_MODELS))
	@p=$$(HF_HUB_OFFLINE=1 uv run --no-sync hf download $(KIT_REPO) --revision $(KIT_REVISION) --quiet 2>/dev/null); \
	echo "client models ready under: $$p"; \
	for d in $(sort $(dir $(KIT_MODELS))); do printf '  %-42s %s\n' "$$d" "$$(du -shL "$$p/$$d" 2>/dev/null | cut -f1)"; done

# The model path is resolved from the cache offline and passed explicitly, so the server never
# depends on Hugging Face at start and always serves the pinned revision.
serve:
	@uv pip show vllm >/dev/null 2>&1 || { echo "vllm is not installed in .venv - run 'make sync-server' first" >&2; exit 1; }
	@model=$$(HF_HUB_OFFLINE=1 uv run --no-sync hf download $(VLM_REPO) --revision $(VLM_REVISION) --quiet 2>/dev/null) \
	  || { echo "$(VLM_REPO)@$(VLM_REVISION) is not in the HF cache - run 'make server-models' first" >&2; exit 1; }; \
	echo "+ mineru-openai-server --model $$model --port $(PORT) --gpu-memory-utilization $(GPU_MEM_UTIL)  (GPU $(GPU))"; \
	CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=$(GPU) HF_HUB_OFFLINE=1 \
	uv run --no-sync mineru-openai-server --model "$$model" --port $(PORT) --gpu-memory-utilization $(GPU_MEM_UTIL)

# ---- pipeline stages (design: docs/plans/2026-09-06-stages-1-4-design.md) ---------------------
# make chapter BOOK=bma CH=5 runs split -> extract -> guardrail -> qa_report into work/bma/ch05/.
MINERU_SERVER_URL ?= http://127.0.0.1:30000
export MINERU_SERVER_URL
BOOK ?=
CH ?=
FORCE ?=

need-chapter-args:
	@test -n "$(BOOK)" -a -n "$(CH)" || { echo "usage: make <target> BOOK=<id> CH=<n> [FORCE=1]" >&2; exit 2; }

split: need-chapter-args
	uv run python -m src.split --book $(BOOK) --chapter $(CH)

extract: need-chapter-args
	uv run python -m src.extract --book $(BOOK) --chapter $(CH) $(if $(FORCE),--force)
