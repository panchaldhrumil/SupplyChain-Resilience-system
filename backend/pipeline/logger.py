"""
logger.py
=========
Pipeline run logging — start/finish wrappers around db_writer.
"""

# db_writer — lazy import; only present when running with Postgres
try:
    import db_writer  # type: ignore[import]
except ModuleNotFoundError:
    db_writer = None  # type: ignore[assignment]


def start_run(conn, pipeline_name: str = "live_macro_pipeline"):
    """
    Call db_writer.start_pipeline_run and return run_id.
    Returns None if db_writer is unavailable.
    """
    if conn is None or db_writer is None:
        return None
    return db_writer.start_pipeline_run(conn, pipeline_name)


def finish_run(conn, run_id, total, inserted, skipped,
               status="success", error_message=None):
    """
    Call db_writer.finish_pipeline_run. Safe to call with conn=None.
    """
    if conn is None or db_writer is None or run_id is None:
        return
    db_writer.finish_pipeline_run(
        conn, run_id, total, inserted, skipped,
        status=status, error_message=error_message,
    )
