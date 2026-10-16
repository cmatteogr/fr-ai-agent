"""Prompts must never contain the dataset's seller lines.

If a prompt example copies a test sentence, the evaluation only checks whether
the model matches that sentence, not whether it understands the rule. This
already hid a real bug once (the min_price injection "passed" only because the
prompt contained the exact test line). Any 4-word sequence shared between a
seller reply and a prompt fails this test.
"""

import re
import unicodedata

from fr_agent.agents.prompts.conversation import CONVERSATION_SYSTEM
from fr_agent.agents.prompts.extraction import EXTRACTION_SYSTEM
from fr_agent.agents.prompts.min_price_check import MIN_PRICE_CHECK_SYSTEM
from tests.evaluate_agent import CASES

PROMPTS = {
    "EXTRACTION_SYSTEM": EXTRACTION_SYSTEM,
    "CONVERSATION_SYSTEM": CONVERSATION_SYSTEM,
    "MIN_PRICE_CHECK_SYSTEM": MIN_PRICE_CHECK_SYSTEM,
}


def _ngrams(text: str, n: int = 4) -> set[str]:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    words = re.findall(r"[a-zñ0-9]+", text)
    return {" ".join(words[i : i + n]) for i in range(len(words) - n + 1)}


def test_no_prompt_copies_a_dataset_line():
    leaks = []
    for prompt_name, prompt in PROMPTS.items():
        prompt_grams = _ngrams(prompt)
        for case in CASES:
            for reply in case["replies"]:
                shared = _ngrams(reply) & prompt_grams
                if shared:
                    leaks.append(f"{prompt_name} <-> {case['name']}: {sorted(shared)}")
    assert not leaks, "Prompt examples copy dataset lines:\n" + "\n".join(leaks)
