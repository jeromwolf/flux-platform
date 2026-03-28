"""Tests for RAGConfig.from_env()."""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from rag.engines.models import RAGConfig, RetrievalMode

pytestmark = pytest.mark.unit


class TestRAGConfigFromEnv:
    def test_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = RAGConfig.from_env()
        assert cfg.mode == RetrievalMode.HYBRID
        assert cfg.top_k == 5
        assert cfg.similarity_threshold == 0.7
        assert cfg.rerank is False
        assert cfg.reranker_backend == "score_boost"
        assert cfg.include_metadata is True

    def test_custom_values(self):
        env = {
            "RAG_MODE": "semantic",
            "RAG_TOP_K": "10",
            "RAG_SIMILARITY_THRESHOLD": "0.5",
            "RAG_RERANK": "true",
            "RAG_RERANKER_BACKEND": "cross_encoder",
            "RAG_INCLUDE_METADATA": "false",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = RAGConfig.from_env()
        assert cfg.mode == RetrievalMode.SEMANTIC
        assert cfg.top_k == 10
        assert cfg.similarity_threshold == 0.5
        assert cfg.rerank is True
        assert cfg.reranker_backend == "cross_encoder"
        assert cfg.include_metadata is False

    def test_keyword_mode(self):
        with patch.dict(os.environ, {"RAG_MODE": "keyword"}, clear=True):
            cfg = RAGConfig.from_env()
        assert cfg.mode == RetrievalMode.KEYWORD

    def test_invalid_mode_falls_back_to_hybrid(self):
        with patch.dict(os.environ, {"RAG_MODE": "invalid"}, clear=True):
            cfg = RAGConfig.from_env()
        assert cfg.mode == RetrievalMode.HYBRID

    def test_rerank_yes(self):
        with patch.dict(os.environ, {"RAG_RERANK": "1"}, clear=True):
            cfg = RAGConfig.from_env()
        assert cfg.rerank is True
