# Coding Agent Instructions

## Source of Truth
- Follow approved specifications in docs/requirements/.
- Do not independently change project scope or architecture.
- Record proposed design changes for human review.

## Current Development Phase
- Requirements and design only.
- Do not implement application code until authorized.

## Architecture Constraints
- Three agents: Coordinator, Weather, Ocean.
- Centralized coordination with bounded ReAct.
- Deterministic safety validation.
- No semantic RAG, full ToT, or additional agents
  without an approved design change.

## Implementation Expectations
- Follow documented data schemas and tool contracts.
- Write tests against defined acceptance criteria.
- Use synthetic data in tests.
- Never commit secrets or sensitive user information.
- Preserve source attribution and evidence timestamps.
