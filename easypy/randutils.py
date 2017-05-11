import os
import string
import itertools
import random
import bisect
import collections
from random import choice, sample

from easypy.collections import grouped

choose = choice


def interpolate(val, mn, mx):
    return (val*(mx-mn) + mn)


def clamp(val, mn, mx):
    return max(mn, min(mx, val))


class XRandom(random.Random):

    def choose_weighted(self, *weighted_choices):
        choices, weights = zip(*weighted_choices)
        cumdist = list(itertools.accumulate(weights))
        x = self.random() * cumdist[-1]
        return choices[bisect.bisect(cumdist, x)]

    def get_size(self, lo, hi, exp=2):
        return int(interpolate(self.random()**exp, lo, hi))

    def get_chunks(self, offset, end, block_size_range, shuffle=False):
        if shuffle:
            chunks = list(self.get_chunks(offset, end, block_size_range))
            self.shuffle(chunks)
            yield from chunks
            return

        total_size = end - offset
        while total_size:
            size = self.get_size(*block_size_range)
            size = clamp(size, 1, total_size)
            if size:
                yield offset, size
            total_size -= size
            offset += size


def load_dictionary(filename):
    full_path = os.path.join(os.path.dirname(__file__), 'dictionary', filename)
    with open(full_path) as dict_file:
        dictionary = [line.strip() for line in dict_file]

    grouped_by_len = grouped(dictionary, key=len)
    return collections.defaultdict(list, grouped_by_len)


NOUNS = load_dictionary('nouns.txt')
VERBS = load_dictionary('verbs.txt')
ADVERBS = load_dictionary('adverbs.txt')
ADJECTIVES = load_dictionary('adjectives.txt')
PARTS_OF_SPEECH = (ADVERBS, VERBS, ADJECTIVES, NOUNS)


def random_meaningful_name(max_length=50, sep='-'):
    parts = []
    next_max_part_len = max_length

    if max_length < 3:
        return random_string(max_length, charset=string.ascii_lowercase)

    # Reverse iterate so that partial sentences will sound logical
    for part_group in PARTS_OF_SPEECH[::-1]:
        usable_word_groups = [
            part_group[l] for l in range(1, next_max_part_len + 1)
            if part_group[l]
        ]

        # No available words in this group with the maximal size of
        # next_max_part_len
        if not usable_word_groups:
            break

        word_group = random.choice(usable_word_groups)
        word = random.choice(word_group)
        parts.append(word)
        next_max_part_len -= (len(word) + len(sep))
        if next_max_part_len <= 0:
            break

    return sep.join(parts)


def random_string(length, charset=string.printable):
    return ''.join(random.choice(charset) for i in range(length))


def random_filename(length=(3, 50)):
    if hasattr(length, "__iter__"):
        length = random.randrange(*length)
    return random_string(length, charset=string.ascii_letters)


def random_buf(size):
    assert size < 5 * 2**20, "This is too big for a buffer (%s)" % size
    return random_string(size).encode("latin-1")
