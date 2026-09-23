"""Ponte segura entre tasks Celery síncronas e código assíncrono.

O pool do asyncpg associa conexões ao event loop em que foram criadas. Por
isso, cada processo filho do Celery mantém um único loop durante toda a sua
vida, em vez de criar e fechar um loop diferente para cada operação.
"""

import asyncio
import os
import threading
from collections.abc import Coroutine
from typing import Any, TypeVar


T = TypeVar("T")

_loop: asyncio.AbstractEventLoop | None = None
_loop_pid: int | None = None
_loop_lock = threading.RLock()


def _get_worker_loop() -> asyncio.AbstractEventLoop:
    """Retorna um loop persistente e exclusivo para o processo atual."""
    global _loop, _loop_pid

    current_pid = os.getpid()
    if _loop is None or _loop.is_closed() or _loop_pid != current_pid:
        # Celery usa prefork. Um loop criado no processo pai nunca deve ser
        # reutilizado no filho, mesmo que ainda pareça aberto após o fork.
        _loop = asyncio.new_event_loop()
        _loop_pid = current_pid
    return _loop


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Executa uma coroutine no loop persistente do processo Celery."""
    with _loop_lock:
        loop = _get_worker_loop()
        if loop.is_running():
            coro.close()
            raise RuntimeError("O event loop persistente do worker já está em execução")
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
