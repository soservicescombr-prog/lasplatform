"""Regressões do event loop persistente usado pelos workers Celery."""

import asyncio

from app.utils.async_runner import run_async


async def _loop_identity() -> int:
    await asyncio.sleep(0)
    return id(asyncio.get_running_loop())


def test_run_async_reuses_the_same_loop_in_the_worker_process():
    first_loop = run_async(_loop_identity())
    second_loop = run_async(_loop_identity())

    assert first_loop == second_loop


def test_run_async_propagates_the_coroutine_result():
    async def result():
        return {"status": "ok"}

    assert run_async(result()) == {"status": "ok"}
