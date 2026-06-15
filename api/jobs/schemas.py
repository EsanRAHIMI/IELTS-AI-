"""Job constants. Lifecycle: pending -> processing -> done | failed."""

JOB_PENDING = "pending"
JOB_PROCESSING = "processing"
JOB_DONE = "done"
JOB_FAILED = "failed"

# Backwards-compatible aliases (older code/data may reference these names).
JOB_RUNNING = JOB_PROCESSING
JOB_ERROR = JOB_FAILED

JOB_STATUSES = {JOB_PENDING, JOB_PROCESSING, JOB_DONE, JOB_FAILED}
