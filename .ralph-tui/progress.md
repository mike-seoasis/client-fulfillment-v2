# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

- **UUID columns**: Use `UUID(as_uuid=False)` with `Mapped[str]`, `default=lambda: str(uuid4())`, `server_default=text("gen_random_uuid()")`.
- **Timestamps**: `DateTime(timezone=True)` with `default=lambda: datetime.now(UTC)`, `server_default=text("now()")`. `updated_at` adds `onupdate=lambda: datetime.now(UTC)`.
- **Enum status fields**: Define `str, Enum` classes, use `.value` for `default=`, wrap in `text("'...'")` for `server_default=`.
- **Relationships**: Use `TYPE_CHECKING` guard for forward refs. Both sides need `back_populates`. Parent side uses `cascade="all, delete-orphan"`. For 1:1, use `unique=True` on FK column + `uselist=False` on the reverse relationship.
- **Models registration**: Import in `backend/app/models/__init__.py` and add to `__all__`.

---

## 2026-02-14 - S11-001
- Implemented BlogCampaign and BlogPost SQLAlchemy models
- Files changed:
  - `backend/app/models/blog.py` (new) — BlogCampaign + BlogPost models with enums
  - `backend/app/models/__init__.py` — registered both models
  - `backend/app/models/project.py` — added `blog_campaigns` relationship
  - `backend/app/models/keyword_cluster.py` — added `blog_campaign` relationship (1:1 via uselist=False)
- **Learnings:**
  - For 1:1 relationships: put `unique=True` on the FK column (BlogCampaign.cluster_id) and `uselist=False` on the reverse side (KeywordCluster.blog_campaign)
  - Pre-existing mypy error in `internal_link.py:243` (unparameterized `dict`) — not related to this change
  - ruff and import checks pass cleanly
---

