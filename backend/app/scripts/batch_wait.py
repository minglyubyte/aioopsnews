from __future__ import annotations

import logging
import time
from typing import Protocol

TERMINAL_BATCH_STATUSES = {"completed", "failed", "expired", "cancelled"}


class BatchStatusClient(Protocol):
    def get_batch_status(self, *, batch_id: str) -> str: ...


def wait_for_batch_completion(
    *,
    batch_client: BatchStatusClient,
    batch_id: str,
    poll_interval_seconds: int,
    max_wait_seconds: int | None,
    logger: logging.Logger,
) -> str:
    started_at = time.monotonic()
    status = batch_client.get_batch_status(batch_id=batch_id)

    while status not in TERMINAL_BATCH_STATUSES:
        elapsed_seconds = time.monotonic() - started_at
        if max_wait_seconds is not None and elapsed_seconds >= max_wait_seconds:
            raise TimeoutError(
                "Timed out waiting for batch "
                f"{batch_id} after {max_wait_seconds} seconds; "
                f"last status was {status}"
            )

        logger.info(
            "Batch %s is %s; sleeping %s seconds before polling again",
            batch_id,
            status,
            poll_interval_seconds,
        )
        time.sleep(poll_interval_seconds)
        status = batch_client.get_batch_status(batch_id=batch_id)

    logger.info("Batch %s reached terminal status=%s", batch_id, status)
    return status
