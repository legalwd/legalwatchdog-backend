"""Central async-to-sync bridge for Celery tasks.

All Celery task modules must import ``syncify`` from here instead of using
``asyncio.run``, ``nest_asyncio``, ``asgiref.sync.async_to_sync``, or any
other ad-hoc bridging approach.

Why a dedicated thread per call?
---------------------------------
* Celery prefork workers are plain synchronous processes with no running event
  loop.  Calling ``anyio.run()`` / ``asyncio.run()`` directly in the worker
  process creates a fresh event loop, runs the coroutine, then **destroys the
  loop**.  Any SQLAlchemy ``AsyncSession`` connections opened inside that loop
  are tied to it; when the loop is destroyed the connections cannot be returned
  to the pool cleanly, eventually exhausting or corrupting it.

* Running the coroutine in a ``ThreadPoolExecutor`` thread instead means the
  thread owns the loop for its entire lifetime.  The loop is created, the
  coroutine runs to completion, the loop is closed — all inside one thread with
  no cross-loop connection leakage.

* ``asgiref.async_to_sync`` uses the same per-thread-loop strategy and is the
  reference implementation for this pattern (used by Django Channels / ASGI).

* Centralising the choice here means that if the underlying strategy ever
  needs to change there is only **one** file to update.

Root cause of the previous implementation
------------------------------------------
The previous ``else`` branch called ``asyncer.syncify(raise_sync_error=False)``
which under the hood delegates to ``anyio.run()`` — functionally identical to
calling ``asyncio.run()`` directly on the worker's main thread.  This caused
two compounding failures:

1. **Greenlet context error**: SQLAlchemy's async extension requires its own
   greenlet wrapper around the event loop.  ``anyio.run()`` / ``asyncio.run()``
   on the main thread do not establish that wrapper, so any ``await`` touching
   the DB raised::

       greenlet_spawn has not been called; can't call await_only() here

2. **Connection pool corruption**: After ``anyio.run()`` returns it destroys
   the event loop.  Any ``AsyncSession`` connections opened inside that loop
   are bound to the now-dead loop; SQLAlchemy cannot return them to the pool
   cleanly.  Under concurrency this exhausts / corrupts the pool entirely.

The ``ThreadPoolExecutor`` branch that previously only fired when a loop was
*already running* was in fact the correct strategy.  This revision makes it
the **universal** strategy for all execution contexts.

Usage::

    from app.api.utils.celery_utils import syncify

    @celery_app.task(bind=True)
    def my_task(self, arg: str) -> str:
        return syncify(my_async_impl)(arg)
"""

import asyncio
import concurrent.futures
import logging
from typing import Any, Callable, Coroutine, Optional, TypeVar

import celery

T = TypeVar("T")

logger = logging.getLogger(__name__)

_DB_EXHAUSTION_SENTINELS = (
    "too many connections",
    "remaining connection slots are reserved",
    "FATAL: sorry, too many clients already",
)


def _is_db_connection_exhaustion(exc: BaseException) -> bool:
    """Check if an exception indicates DB connection pool exhaustion.

    Args:
        exc: Exception to inspect.

    Returns:
        True if the error message matches known connection exhaustion patterns.
    """
    error_str = str(exc).lower()
    return any(sentinel in error_str for sentinel in _DB_EXHAUSTION_SENTINELS)


def retry_on_db_exhaustion(
    task: celery.Task,
    *,
    initial_delay: int = 15,
    max_retries: Optional[int] = None,
    exponential_base: int = 2,
) -> bool:
    """Retry a Celery task if it failed due to DB connection exhaustion.

    Call this inside an ``except`` block to check and retry.  Returns ``True``
    if the exception was handled (task will retry), ``False`` otherwise.

    Uses exponential backoff: ``initial_delay * (exponential_base ^ attempt)``.

    Args:
        task: The Celery task instance (``self``).
        initial_delay: Seconds to wait before first retry.
        max_retries: Override task's max_retries. None uses task default.
        exponential_base: Multiplier for exponential backoff.

    Returns:
        True if task will be retried, False otherwise.

    Example::

        @celery_app.task(bind=True, max_retries=3)
        def scrape_source_stage1(self, source_id, job_id):
            try:
                ...
            except Exception as e:
                if retry_on_db_exhaustion(self, initial_delay=15, max_retries=3):
                    return  # task will retry
                raise

    """
    if task.request.retries >= (max_retries or task.max_retries or 0):
        logger.error(
            "DB connection exhausted; task %s reached max retries (%d)",
            task.name,
            task.request.retries,
        )
        return False

    delay = initial_delay * (exponential_base**task.request.retries)
    logger.warning(
        "DB connection pool exhausted; retrying task %s in %ds (attempt %d/%d)",
        task.name,
        delay,
        task.request.retries + 1,
        max_retries or task.max_retries,
    )
    task.retry(countdown=delay, max_retries=max_retries)
    return True


def syncify(
    async_function: Callable[..., Coroutine[Any, Any, T]],
) -> Callable[..., T]:
    """Return a synchronous version of *async_function* safe for Celery workers.

    Always runs the coroutine in a dedicated ``ThreadPoolExecutor`` thread that
    owns its own event loop via ``asyncio.run()``.  This is safe in all three
    execution contexts:

    1. **Celery prefork worker** (no running loop): the thread creates a fresh
       loop, runs the coroutine, closes the loop.  SQLAlchemy ``NullPool``
       connections are opened and closed within that single loop lifetime —
       no cross-loop pool corruption.

    2. **Celery eager mode / pytest** (loop already running on the calling
       thread): the dedicated thread has its *own* separate loop so there is
       no "cannot run nested event loop" error and no need for ``nest_asyncio``.

    3. **Any other sync context**: same as (1).

    Thread-loop ownership model
    ---------------------------
    ::

        Worker main thread
          └─ ThreadPoolExecutor submits asyncio.run(coroutine) to thread T1
               Thread T1
                 └─ asyncio.run() creates event loop owned by T1
                 └─ AsyncSession opens connection bound to T1's loop
                 └─ coroutine completes → NullPool closes connection cleanly
                 └─ asyncio.run() closes loop on T1 → clean shutdown ✅
          └─ future.result() blocks main thread until T1 finishes

    With ``NullPool`` (set on ``CeleryAsyncSessionLocal`` in ``database.py``),
    the connection lifetime equals the session lifetime equals the thread
    lifetime.  Nothing leaks across task invocations.

    Args:
        async_function: An ``async def`` function to wrap.

    Returns:
        A regular (non-async) callable with the same signature and return type.

    Example::

        async def _send_email_async(recipient: str) -> bool:
            ...

        @shared_task(name="send_email")
        def send_email_task(recipient: str) -> bool:
            return syncify(_send_email_async)(recipient)
    """

    def wrapper(*args: Any, **kwargs: Any) -> T:
        # Always use a dedicated thread so the event loop is fully owned and
        # isolated to that thread.  This avoids both the "nested loop" error
        # when a loop is already running AND the pool-corruption / greenlet
        # context issue caused by destroying the loop after anyio.run() returns
        # on the worker's main thread.
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, async_function(*args, **kwargs))
            return future.result()

    return wrapper
