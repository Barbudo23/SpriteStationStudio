from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import PurePosixPath
from typing import Any, Iterable
import uuid


BATCH_PLAN_SCHEMA_VERSION = "1.0"
MAX_BATCH_ITEMS = 3


class BatchPlanError(ValueError):
    pass


class BatchOperation(str, Enum):
    PREVIEW = "preview"
    DIRECTIONS = "directions"
    ANIMATION = "animation"


class BatchStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BatchPlanError(f"{field_name} must be a non-empty string.")
    if "\x00" in value:
        raise BatchPlanError(f"{field_name} contains a null byte.")
    return value.strip()


def _validate_contract_path(value: object, field_name: str) -> str:
    path = PurePosixPath(_required_text(value, field_name).replace("\\", "/"))
    if ".." in path.parts:
        raise BatchPlanError(f"{field_name} must not contain parent traversal.")
    return str(path)


def _validate_utc(value: object, field_name: str) -> str:
    text = _required_text(value, field_name)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise BatchPlanError(f"{field_name} must use ISO-8601 format.") from exc
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise BatchPlanError(f"{field_name} must include the UTC offset.")
    return text


@dataclass(frozen=True)
class BatchItem:
    item_id: str
    operation: BatchOperation
    source_path: str
    output_path: str
    status: BatchStatus = BatchStatus.PENDING
    attempt_count: int = 0
    result_manifest: str | None = None
    error: str | None = None

    def validate(self) -> None:
        _required_text(self.item_id, "itemId")
        _validate_contract_path(self.source_path, "sourcePath")
        _validate_contract_path(self.output_path, "outputPath")
        if self.attempt_count < 0:
            raise BatchPlanError("attemptCount must not be negative.")
        if self.status == BatchStatus.COMPLETED and not self.result_manifest:
            raise BatchPlanError("Completed item requires resultManifest.")
        if self.status == BatchStatus.FAILED and not self.error:
            raise BatchPlanError("Failed item requires error diagnostics.")
        if self.status != BatchStatus.FAILED and self.error is not None:
            raise BatchPlanError("Only failed item may contain error diagnostics.")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "itemId": self.item_id,
            "operation": self.operation.value,
            "sourcePath": self.source_path,
            "outputPath": self.output_path,
            "status": self.status.value,
            "attemptCount": self.attempt_count,
            "resultManifest": self.result_manifest,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BatchItem":
        try:
            item = cls(
                item_id=_required_text(payload["itemId"], "itemId"),
                operation=BatchOperation(payload["operation"]),
                source_path=_validate_contract_path(payload["sourcePath"], "sourcePath"),
                output_path=_validate_contract_path(payload["outputPath"], "outputPath"),
                status=BatchStatus(payload.get("status", BatchStatus.PENDING.value)),
                attempt_count=int(payload.get("attemptCount", 0)),
                result_manifest=payload.get("resultManifest"),
                error=payload.get("error"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise BatchPlanError(f"Invalid batch item: {exc}") from exc
        item.validate()
        return item


@dataclass(frozen=True)
class BatchPlan:
    plan_id: str
    items: tuple[BatchItem, ...]
    created_utc: str
    updated_utc: str
    schema_version: str = BATCH_PLAN_SCHEMA_VERSION

    @classmethod
    def create(cls, items: Iterable[BatchItem], plan_id: str | None = None) -> "BatchPlan":
        now = _utc_now()
        plan = cls(
            plan_id=plan_id or str(uuid.uuid4()),
            items=tuple(items),
            created_utc=now,
            updated_utc=now,
        )
        plan.validate()
        return plan

    def validate(self) -> None:
        if self.schema_version != BATCH_PLAN_SCHEMA_VERSION:
            raise BatchPlanError(
                f"Unsupported BatchPlan schemaVersion: {self.schema_version}"
            )
        _required_text(self.plan_id, "planId")
        _validate_utc(self.created_utc, "createdUtc")
        _validate_utc(self.updated_utc, "updatedUtc")
        if not 1 <= len(self.items) <= MAX_BATCH_ITEMS:
            raise BatchPlanError("BatchPlan must contain between one and three items.")
        for item in self.items:
            item.validate()
        item_ids = [item.item_id for item in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise BatchPlanError("BatchPlan itemId values must be unique.")
        output_paths = [item.output_path.casefold() for item in self.items]
        if len(output_paths) != len(set(output_paths)):
            raise BatchPlanError("BatchPlan outputPath values must be unique.")
        if sum(item.status == BatchStatus.RUNNING for item in self.items) > 1:
            raise BatchPlanError("Only one BatchPlan item may be running.")

    def next_pending(self) -> BatchItem | None:
        return next((item for item in self.items if item.status == BatchStatus.PENDING), None)

    def mark_running(self, item_id: str) -> "BatchPlan":
        if any(item.status == BatchStatus.RUNNING for item in self.items):
            raise BatchPlanError("Another batch item is already running.")
        return self._transition(item_id, {BatchStatus.PENDING, BatchStatus.FAILED}, BatchStatus.RUNNING)

    def mark_completed(self, item_id: str, result_manifest: str) -> "BatchPlan":
        return self._transition(
            item_id,
            {BatchStatus.RUNNING},
            BatchStatus.COMPLETED,
            result_manifest=_validate_contract_path(result_manifest, "resultManifest"),
        )

    def mark_failed(self, item_id: str, error: str) -> "BatchPlan":
        return self._transition(
            item_id,
            {BatchStatus.RUNNING},
            BatchStatus.FAILED,
            error=_required_text(error, "error")[:1000],
        )

    def cancel_pending(self, item_id: str) -> "BatchPlan":
        return self._transition(item_id, {BatchStatus.PENDING}, BatchStatus.CANCELLED)

    def _transition(
        self,
        item_id: str,
        allowed: set[BatchStatus],
        target: BatchStatus,
        result_manifest: str | None = None,
        error: str | None = None,
    ) -> "BatchPlan":
        found = False
        changed: list[BatchItem] = []
        for item in self.items:
            if item.item_id != item_id:
                changed.append(item)
                continue
            found = True
            if item.status not in allowed:
                raise BatchPlanError(
                    f"Cannot transition {item.item_id} from {item.status.value} to {target.value}."
                )
            changed.append(replace(
                item,
                status=target,
                attempt_count=item.attempt_count + (1 if target == BatchStatus.RUNNING else 0),
                result_manifest=result_manifest,
                error=error,
            ))
        if not found:
            raise BatchPlanError(f"Unknown batch item: {item_id}")
        plan = replace(self, items=tuple(changed), updated_utc=_utc_now())
        plan.validate()
        return plan

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schemaVersion": self.schema_version,
            "planId": self.plan_id,
            "createdUtc": self.created_utc,
            "updatedUtc": self.updated_utc,
            "items": [item.to_dict() for item in self.items],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BatchPlan":
        if not isinstance(payload, dict):
            raise BatchPlanError("BatchPlan root must be a JSON object.")
        try:
            raw_items = payload["items"]
            if not isinstance(raw_items, list):
                raise BatchPlanError("BatchPlan items must be a JSON array.")
            plan = cls(
                schema_version=payload["schemaVersion"],
                plan_id=_required_text(payload["planId"], "planId"),
                created_utc=_validate_utc(payload["createdUtc"], "createdUtc"),
                updated_utc=_validate_utc(payload["updatedUtc"], "updatedUtc"),
                items=tuple(BatchItem.from_dict(item) for item in raw_items),
            )
        except (KeyError, TypeError) as exc:
            raise BatchPlanError(f"Invalid BatchPlan: {exc}") from exc
        plan.validate()
        return plan
