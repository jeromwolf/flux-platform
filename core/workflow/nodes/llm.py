"""LLM node — AI text generation via agent/llm providers."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from core.workflow.base_node import BaseNode
from core.workflow.registry import NodeRegistry

logger = logging.getLogger(__name__)


@NodeRegistry.register
class LLMNode(BaseNode):
    name = "ai"
    display_name = "AI 처리"
    description = "LLM 텍스트 생성 (Ollama/OpenAI/Anthropic)"
    category = "ai"

    async def execute(
        self,
        input_data: list[dict[str, Any]],
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Generate text using LLM.

        Params:
            provider: LLM provider name (default: "auto")
            model: Model name (optional, provider-dependent)
            prompt_template: Prompt template with {{field}} placeholders
            system: System prompt (optional)
            temperature: Sampling temperature (default: 0.7)
            max_tokens: Max tokens (default: 2048)
            batch: If true, process each input item separately (default: false)
        """
        from agent.llm.providers import create_llm_provider

        provider_name = params.get("provider", "auto")
        model = params.get("model")
        prompt_template = params.get("prompt_template", "{{text}}")
        system = params.get("system", "")
        temperature = float(params.get("temperature", 0.7))
        max_tokens = int(params.get("max_tokens", 2048))
        batch = params.get("batch", False)

        # Create provider
        kwargs: dict[str, Any] = {}
        if model:
            kwargs["model"] = model
        provider = create_llm_provider(provider_name, **kwargs)

        if batch and input_data:
            # Process each item separately
            results = []
            for item in input_data:
                prompt = self._apply_template(prompt_template, item)
                response = await asyncio.to_thread(
                    provider.generate,
                    prompt=prompt,
                    system=system,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                results.append({"response": response, "prompt": prompt, **item})
            return results
        else:
            # Single prompt with all input merged
            merged: dict[str, Any] = {}
            for item in input_data:
                merged.update(item)
            prompt = self._apply_template(prompt_template, merged)

            response = await asyncio.to_thread(
                provider.generate,
                prompt=prompt,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return [{"response": response, "prompt": prompt}]

    @staticmethod
    def _apply_template(template: str, data: dict[str, Any]) -> str:
        """Replace {{field}} placeholders with data values."""
        result = template
        for key, val in data.items():
            result = result.replace(f"{{{{{key}}}}}", str(val))
        return result

    def get_parameter_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "provider": {
                    "type": "string",
                    "enum": ["auto", "ollama", "openai", "anthropic"],
                    "default": "auto",
                    "description": "LLM 제공자",
                },
                "model": {"type": "string", "description": "모델명 (선택)"},
                "prompt_template": {
                    "type": "string",
                    "default": "{{text}}",
                    "description": "프롬프트 템플릿 ({{필드명}} 치환)",
                },
                "system": {
                    "type": "string",
                    "default": "",
                    "description": "시스템 프롬프트",
                },
                "temperature": {
                    "type": "number",
                    "default": 0.7,
                    "description": "샘플링 온도",
                },
                "max_tokens": {
                    "type": "integer",
                    "default": 2048,
                    "description": "최대 토큰 수",
                },
                "batch": {
                    "type": "boolean",
                    "default": False,
                    "description": "개별 항목 처리 여부",
                },
            },
        }
