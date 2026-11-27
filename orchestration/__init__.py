"""XDX Studio v4.0 Multi-Agent Orchestration, DAG Scheduler & Checkpoint Recovery (Phase 01.6B)."""

from orchestration.agent_registry import AgentRegistry, build_default_agent_registry_dict
from orchestration.capability_discovery import CAPABILITY_STATUSES, RuntimeCapabilityDiscovery
from orchestration.checkpoint_manager import (
    MANDATORY_CHECKPOINT_FIELDS,
    CheckpointError,
    CheckpointManager,
    CorruptedCheckpointError,
)
from orchestration.dependency_scheduler import (
    PhaseBoundaryExecutionBlockedError,
    SchedulerError,
    TaskDependencyScheduler,
    WorkerCompletionRejectedError,
)
from orchestration.handoff_manager import (
    ArtifactBoundaryError,
    ArtifactOwnershipLockManager,
    DuplicateArtifactPathError,
    HandoffValidationError,
    InvalidArtifactOwnershipError,
    InvalidTaskDependencyError,
    ParallelWriteConflictError,
    ReadOnlyAgentOwnershipError,
    SilentArtifactMutationError,
    TaskHandoffManager,
    UnverifiedInputArtifactError,
)
from orchestration.native_execution_adapter import (
    AgentExecutionResult,
    AgentFailureReport,
    AgentInvocationReceipt,
    AgentInvocationRequest,
    AgentReviewReport,
    NativeAgentExecutionAdapter,
)
from orchestration.revision_manager import APPROVAL_SENSITIVE_FILENAMES, RevisionManager
from orchestration.shared_state import (
    ALL_26_PROJECT_STATES_V4,
    ALLOWED_V4_STATE_TRANSITIONS,
    AUXILIARY_STATES_V4,
    PRIMARY_STATES_V4,
    TASK_STATES_V4,
    SharedProjectStateMachine,
    StateVersionConflictError,
)
from orchestration.task_router import MasterDirectorTaskRouter

__all__ = [
    "ALL_26_PROJECT_STATES_V4",
    "ALLOWED_V4_STATE_TRANSITIONS",
    "APPROVAL_SENSITIVE_FILENAMES",
    "AUXILIARY_STATES_V4",
    "CAPABILITY_STATUSES",
    "MANDATORY_CHECKPOINT_FIELDS",
    "PRIMARY_STATES_V4",
    "TASK_STATES_V4",
    "AgentExecutionResult",
    "AgentFailureReport",
    "AgentInvocationReceipt",
    "AgentInvocationRequest",
    "AgentRegistry",
    "AgentReviewReport",
    "ArtifactBoundaryError",
    "ArtifactOwnershipLockManager",
    "CheckpointError",
    "CheckpointManager",
    "CorruptedCheckpointError",
    "DuplicateArtifactPathError",
    "HandoffValidationError",
    "InvalidArtifactOwnershipError",
    "InvalidTaskDependencyError",
    "MasterDirectorTaskRouter",
    "NativeAgentExecutionAdapter",
    "ParallelWriteConflictError",
    "PhaseBoundaryExecutionBlockedError",
    "ReadOnlyAgentOwnershipError",
    "RevisionManager",
    "RuntimeCapabilityDiscovery",
    "SchedulerError",
    "SharedProjectStateMachine",
    "SilentArtifactMutationError",
    "StateVersionConflictError",
    "TaskDependencyScheduler",
    "TaskHandoffManager",
    "UnverifiedInputArtifactError",
    "WorkerCompletionRejectedError",
    "build_default_agent_registry_dict",
]
