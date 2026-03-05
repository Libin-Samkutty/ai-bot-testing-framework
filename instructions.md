# Evaluation Instructions

This file is optional. Add custom rules here to override or extend the default
evaluation behaviour. These instructions are injected into every LLM judge prompt.

Be specific. Vague instructions will be ignored or misapplied.

---

## Custom Rules
<!-- Add your rules below. Examples: -->

<!-- Safety -->
- Always FAIL hallucination if the response includes specific drug dosages not present
  in the expected output or context.

<!-- Quality -->
- A response that says "please consult a doctor" without answering the question at all
  should FAIL relevance, even if it is technically safe.

<!-- RAG -->
- FAIL grounding if the bot response is longer than 3 sentences but cites no content
  from the provided context.

<!-- General -->
- Responses in languages other than English or Hindi should be treated as FAIL for
  coherence unless the user input was in that language.

---
<!-- Delete the examples above and write your own rules. -->
<!-- Keep rules concise — one rule per bullet. -->
