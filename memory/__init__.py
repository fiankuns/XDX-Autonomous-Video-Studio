"""XDX Studio v4.0 Shared Persistent Memory Package Marker (Scheduled for Phase 01.6B).

Intentionally contains no fake stub logic in Phase 01.6A; full atomic/locked implementations of
Knowledge, Production, Project, Execution, Error, and Quality memory arrive in Phase 01.6B.
"""

MEMORY_PARTITIONS_PLANNED_PHASE_01_6B: tuple[str, ...] = (
    "knowledge_memory",
    "production_memory",
    "project_memory",
    "execution_memory",
    "error_memory",
    "quality_memory",
)
