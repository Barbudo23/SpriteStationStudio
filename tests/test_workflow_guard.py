from assetforge.workflow import (
    ProductionWorkflowGuard,
    WorkflowAction,
    WorkflowCheckpoint,
)


def checkpoint(iteration: int = 1) -> WorkflowCheckpoint:
    return WorkflowCheckpoint(
        status="COMPLETE",
        completed_iteration=iteration,
        next_iteration=iteration + 1 if iteration < 10 else None,
        project_progress=iteration / 10.0,
        package_file=f"Iteration_{iteration:02d}.zip",
        package_sha256="abc123",
        stack_revision="Stack_03_Rev00",
    )


def test_guard_runs_first_iteration_without_checkpoint():
    decision = ProductionWorkflowGuard().evaluate(1, None)
    assert decision.action == WorkflowAction.RUN


def test_guard_skips_completed_iteration():
    decision = ProductionWorkflowGuard().evaluate(1, checkpoint())
    assert decision.action == WorkflowAction.ALREADY_COMPLETE
    assert "Next iteration: 02" in decision.message


def test_guard_allows_expected_next_iteration():
    decision = ProductionWorkflowGuard().evaluate(2, checkpoint())
    assert decision.action == WorkflowAction.RUN
    assert decision.message == "Resuming with iteration 02."


def test_guard_blocks_stale_manifest():
    decision = ProductionWorkflowGuard().evaluate(1, checkpoint(2))
    assert decision.action == WorkflowAction.BLOCKED
    assert "older than checkpoint" in decision.message


def test_guard_blocks_skipped_iteration():
    decision = ProductionWorkflowGuard().evaluate(3, checkpoint())
    assert decision.action == WorkflowAction.BLOCKED
    assert "expects iteration 02" in decision.message


def test_guard_force_allows_explicit_rebuild():
    decision = ProductionWorkflowGuard().evaluate(1, checkpoint(), force=True)
    assert decision.action == WorkflowAction.RUN
    assert decision.message == "Forced rebuild of iteration 01."


def test_guard_marks_tenth_iteration_as_terminal():
    decision = ProductionWorkflowGuard().evaluate(10, checkpoint(10))
    assert decision.action == WorkflowAction.ALREADY_COMPLETE
    assert "Next iteration: none" in decision.message
