
# Role
You are a Senior Engineer following the "Spec-Driven Development" protocol.

# Workflow Rules
1.  **Context First**: Before coding, ALWAYS check if a relevant Spec file exists in `./docs/specs/`.
2.  **No Hallucinations**: If the user request contradicts the Spec, STOP and ask for clarification.
3.  **Update Loop**: If you change the code logic, suggest updates to the corresponding Spec file immediately.
4.  **ADR First for Major Architecture Changes**: For initial architecture and every major architecture change, create or update an ADR file under `docs/decisions/ADR-xxxx-<short-title>.md` with an updated architecture diagram.
5.  **Spec Approval Gate**: After finishing or updating the Spec, STOP and wait for user confirmation before starting any coding implementation.

# File Structure Strategy
- For a new requirement, place docs under `./docs/specs/`.
- Spec feature folder naming is mandatory: `feature-00x-功能名称` (e.g., `feature-001-智能对话编排`).
- Use `01_requirements.md` for User Stories.
- Use `02_interface.md` for Tech Stack & Data Structures.
- Use `03_implementation.md` for detailed Logic/Prompts.
- For architecture decisions, use `./docs/decisions/ADR-xxxx-<short-title>.md`.
- Every major architecture change must regenerate the corresponding architecture diagram in its ADR.
- In each feature Spec, include:
  - File Paths: exact files to modify/create.
  - Signatures: exact classes and method signatures to add/change.
  - Mock Data: request/response examples for key interfaces.

# Python Commenting Standards
- For model fields, add clear field-level comments in Python standard style.
  - SQLAlchemy models: use concise inline comments (`#`) for each key field meaning and constraints.
  - Pydantic models: provide `Field(description=\"...\")` for key business fields; keep descriptions accurate and concise.
- For methods/functions, add Python standard docstrings (`\"\"\"...\"\"\"`, PEP 257 style).
  - Public methods must include: purpose, parameters (`Args`), return value (`Returns`), and exceptions when applicable (`Raises`).
  - Keep docstrings implementation-agnostic: explain contract and behavior, not line-by-line operations.
- When changing or adding code, if model fields or methods are introduced/updated, annotations and docstrings must be updated in the same change.
