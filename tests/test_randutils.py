import pytest
import random

from easypy.randutils import random_meaningful_name


def test_random_meaningful_name():
    for _ in range(20):
        length = random.randint(1, 64)
        sep = random.choice(['_', '..', '-+-'])
        name = random_meaningful_name(length, sep=sep)
        assert len(name) <= length
