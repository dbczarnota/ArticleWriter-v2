import asyncio
import pytest
from toolsets.scraping.rate_limiter import get_jina_semaphore, reset_jina_semaphore


@pytest.fixture(autouse=True)
def reset_semaphore():
    reset_jina_semaphore()
    yield
    reset_jina_semaphore()


def test_get_jina_semaphore_returns_semaphore():
    sem = get_jina_semaphore()
    assert isinstance(sem, asyncio.Semaphore)


def test_get_jina_semaphore_is_singleton():
    sem1 = get_jina_semaphore()
    sem2 = get_jina_semaphore()
    assert sem1 is sem2


def test_get_jina_semaphore_custom_max():
    sem = get_jina_semaphore(max_concurrent=4)
    assert isinstance(sem, asyncio.Semaphore)


def test_reset_creates_new_instance():
    sem1 = get_jina_semaphore()
    reset_jina_semaphore()
    sem2 = get_jina_semaphore()
    assert sem1 is not sem2
