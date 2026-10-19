from unittest.mock import Mock

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from src.core.models import ChatMessage, Evidence
from src.services.companion import RagCompanion, validate_citations


def test_no_evidence_does_not_invent_an_answer(match):
    retriever = Mock()
    retriever.retrieve.return_value = []
    model = Mock(side_effect=AssertionError("Generation should not run without evidence"))
    response = RagCompanion(retriever, model).answer("Who won?", [], match)
    assert "couldn't find enough" in response.content
    assert not response.evidence
    model.assert_not_called()


def test_langchain_prompt_contains_evidence_and_citations(match):
    evidence = Evidence("report.md", 2, "The winger replaced the midfielder at minute 62.", 0.8)
    retriever = Mock()
    retriever.retrieve.return_value = [evidence]
    prompts = []

    def respond(prompt):
        prompts.append(prompt.to_string())
        return AIMessage(content="A winger replaced a midfielder at minute 62. [1]")

    result = RagCompanion(retriever, RunnableLambda(respond)).answer("What changed?", [], match)
    assert result.evidence == [evidence]
    assert result.content.endswith("[1]")
    assert evidence.text in prompts[0]
    assert "untrusted data" in prompts[0]
    assert "Fictional sample: True" in prompts[0]


def test_follow_up_is_rewritten_before_retrieval(match):
    prompts = []
    def respond(prompt):
        prompts.append(prompt.to_string())
        if len(prompts) == 1:
            return AIMessage(content="How did Lucas Silva affect the right flank?")
        return AIMessage(content="Lucas provided width. [1]")
    retriever = Mock()
    retriever.retrieve.return_value = [Evidence("report.md", 1, "Lucas provided width.", 0.8)]
    history = [ChatMessage("user", "Who came on?"), ChatMessage("assistant", "Lucas Silva. [1]")]
    result = RagCompanion(retriever, RunnableLambda(respond)).answer("How did he do?", history, match)
    retriever.retrieve.assert_called_once_with("How did Lucas Silva affect the right flank?")
    assert "How did he do?" in prompts[1]
    assert result.query == "How did Lucas Silva affect the right flank?"


@pytest.mark.parametrize("answer", ["No citation.", "Unsupported [2]", "Invalid [0]", "A [1] B [99]"])
def test_invalid_references_do_not_appear_as_verified_answers(answer):
    assert "couldn't produce" in validate_citations(answer, [Evidence("a.md", 1, "Text", 0.9)])
