import time
from collections.abc import Callable


def retry_transient[T](
    fn: Callable[[], T],
    is_transient: Callable[[Exception], bool],
    attempts: int = 4,
    wait_base: float = 1.0,
) -> T:
    """Call fn, retrying transient errors after waits of wait_base, then 2x, then 4x.

    The default of 4 attempts is the first call plus 3 retries.
    """
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as error:
            if attempt == attempts or not is_transient(error):
                raise
            time.sleep(wait_base * 2 ** (attempt - 1))
    raise AssertionError("unreachable")
