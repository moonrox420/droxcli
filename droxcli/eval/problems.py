"""Standard benchmark problems — 12 total (E×3, M×6, H×3)."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Problem:
    id: str
    prompt: str
    test_code: str
    category: str
    difficulty: str
    tags: List[str] = field(default_factory=list)


PROBLEMS: List[Problem] = [
    # ── EASY ──────────────────────────────────────────────────────────────
    Problem(
        id="E01",
        prompt=(
            "Write a function called fizzbuzz(n) in eval_target.py that returns "
            "a list of strings: 'Fizz' for multiples of 3, 'Buzz' for multiples "
            "of 5, 'FizzBuzz' for both, otherwise the number as a string. "
            "n is the count of items."
        ),
        test_code="""
from eval_target import fizzbuzz
result = fizzbuzz(15)
assert result[2]  == 'Fizz',     f"index 2: {result[2]}"
assert result[4]  == 'Buzz',     f"index 4: {result[4]}"
assert result[14] == 'FizzBuzz', f"index 14: {result[14]}"
assert result[0]  == '1',        f"index 0: {result[0]}"
assert len(result) == 15
""",
        category="algorithm",
        difficulty="easy",
        tags=["loops", "conditionals"],
    ),
    Problem(
        id="E02",
        prompt=(
            "Write a function called is_palindrome(s) in eval_target.py that "
            "returns True if the string s is a palindrome, ignoring case and "
            "non-alphanumeric characters."
        ),
        test_code="""
from eval_target import is_palindrome
assert is_palindrome("racecar") is True
assert is_palindrome("A man a plan a canal Panama") is True
assert is_palindrome("hello") is False
assert is_palindrome("") is True
assert is_palindrome("No 'x' in Nixon") is True
""",
        category="string",
        difficulty="easy",
        tags=["strings", "two-pointer"],
    ),
    Problem(
        id="E03",
        prompt=(
            "Write a function called flatten(lst) in eval_target.py that takes "
            "a deeply nested list and returns a flat list of all values."
        ),
        test_code="""
from eval_target import flatten
assert flatten([1, [2, [3, [4]], 5]]) == [1, 2, 3, 4, 5]
assert flatten([]) == []
assert flatten([1, 2, 3]) == [1, 2, 3]
assert flatten([[1, 2], [3, [4, 5]]]) == [1, 2, 3, 4, 5]
""",
        category="data-structures",
        difficulty="easy",
        tags=["recursion", "lists"],
    ),
    # ── MEDIUM ────────────────────────────────────────────────────────────
    Problem(
        id="M01",
        prompt=(
            "Write a function called two_sum(nums, target) in eval_target.py "
            "that returns the indices of two numbers that add up to target. "
            "Each input has exactly one solution. Use a hash map for O(n) time."
        ),
        test_code="""
from eval_target import two_sum
assert sorted(two_sum([2, 7, 11, 15], 9)) == [0, 1]
assert sorted(two_sum([3, 2, 4], 6))      == [1, 2]
assert sorted(two_sum([3, 3], 6))         == [0, 1]
""",
        category="algorithm",
        difficulty="medium",
        tags=["hash-map", "arrays"],
    ),
    Problem(
        id="M02",
        prompt=(
            "Write a class called LRUCache in eval_target.py. "
            "The constructor takes capacity as an argument. "
            "It must have get(key) -> int (returns -1 if not found) "
            "and put(key, value) methods. "
            "Evict the least recently used item when over capacity."
        ),
        test_code="""
from eval_target import LRUCache
cache = LRUCache(2)
cache.put(1, 1)
cache.put(2, 2)
assert cache.get(1) == 1
cache.put(3, 3)
assert cache.get(2) == -1
cache.put(4, 4)
assert cache.get(1) == -1
assert cache.get(3) == 3
assert cache.get(4) == 4
""",
        category="data-structures",
        difficulty="medium",
        tags=["linked-list", "hash-map", "cache"],
    ),
    Problem(
        id="M03",
        prompt=(
            "Write a function called group_anagrams(words) in eval_target.py "
            "that groups a list of strings into sublists of anagrams."
        ),
        test_code="""
from eval_target import group_anagrams
result = group_anagrams(["eat", "tea", "tan", "ate", "nat", "bat"])
result_sorted = sorted([sorted(g) for g in result])
assert ['ate', 'eat', 'tea'] in result_sorted
assert ['nat', 'tan']        in result_sorted
assert ['bat']               in result_sorted
""",
        category="string",
        difficulty="medium",
        tags=["hash-map", "sorting"],
    ),
    Problem(
        id="M04",
        prompt=(
            "Write a function called parse_config(text) in eval_target.py that "
            "parses a simple INI-style config string and returns a dict of dicts. "
            "Sections are [name], keys are key=value pairs."
        ),
        test_code="""
from eval_target import parse_config
cfg = parse_config('''
[database]
host=localhost
port=5432

[cache]
ttl=300
''')
assert cfg['database']['host'] == 'localhost'
assert cfg['database']['port'] == '5432'
assert cfg['cache']['ttl']     == '300'
""",
        category="real-world",
        difficulty="medium",
        tags=["parsing", "strings"],
    ),
    Problem(
        id="M05",
        prompt=(
            "Write a function called merge_intervals(intervals) in eval_target.py "
            "that takes a list of [start, end] intervals and merges all overlapping "
            "ones. Return the merged list sorted by start time."
        ),
        test_code="""
from eval_target import merge_intervals
assert merge_intervals([[1,3],[2,6],[8,10],[15,18]]) == [[1,6],[8,10],[15,18]]
assert merge_intervals([[1,4],[4,5]])                == [[1,5]]
assert merge_intervals([[1,4]])                      == [[1,4]]
assert merge_intervals([])                           == []
""",
        category="algorithm",
        difficulty="medium",
        tags=["sorting", "arrays"],
    ),
    # ── HARD ──────────────────────────────────────────────────────────────
    Problem(
        id="H01",
        prompt=(
            "Write a function called min_edit_distance(s1, s2) in eval_target.py "
            "that returns the minimum edit distance (Levenshtein distance) between "
            "two strings using dynamic programming."
        ),
        test_code="""
from eval_target import min_edit_distance
assert min_edit_distance("kitten", "sitting") == 3
assert min_edit_distance("", "abc")           == 3
assert min_edit_distance("abc", "")           == 3
assert min_edit_distance("abc", "abc")        == 0
assert min_edit_distance("horse", "ros")      == 3
""",
        category="algorithm",
        difficulty="hard",
        tags=["dynamic-programming", "strings"],
    ),
    Problem(
        id="H02",
        prompt=(
            "Write a TreeNode class and two functions serialize_tree(root) "
            "and deserialize_tree(data) in eval_target.py. "
            "TreeNode has val (int), left, and right attributes. "
            "serialize converts a binary tree to a string. "
            "deserialize converts it back using the same TreeNode class. "
            "They must be exact inverses of each other."
        ),
        test_code="""
from eval_target import serialize_tree, deserialize_tree, TreeNode

root = TreeNode(1, TreeNode(2), TreeNode(3, TreeNode(4), TreeNode(5)))
data = serialize_tree(root)
assert isinstance(data, str)
r = deserialize_tree(data)
assert r.val == 1
assert r.left.val == 2
assert r.right.val == 3
assert r.right.left.val == 4
assert r.right.right.val == 5
assert r.left.left is None
""",
        category="data-structures",
        difficulty="hard",
        tags=["trees", "serialization"],
    ),
    Problem(
        id="H03",
        prompt=(
            "Write a function called word_break(s, word_dict) in eval_target.py "
            "that returns True if string s can be fully segmented into words "
            "from word_dict."
        ),
        test_code="""
from eval_target import word_break
assert word_break("leetcode",      ["leet", "code"])                       is True
assert word_break("applepenapple", ["apple", "pen"])                       is True
assert word_break("catsandog",     ["cats", "dog", "sand", "and", "cat"]) is False
assert word_break("",              ["a"])                                  is True
""",
        category="algorithm",
        difficulty="hard",
        tags=["dynamic-programming", "strings"],
    ),
    # ── SELF ──────────────────────────────────────────────────────────────
    Problem(
        id="S01",
        prompt=(
            "Write a function called count_source_files(root_path) in eval_target.py "
            "that counts Python source files in a directory tree, "
            "skipping any directories named .venv, __pycache__, .git, or node_modules. "
            "root_path is a pathlib.Path."
        ),
        test_code="""
from eval_target import count_source_files
from pathlib import Path
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    (root / 'a.py').write_text('x=1')
    (root / 'b.py').write_text('y=2')
    sub = root / 'sub'
    sub.mkdir()
    (sub / 'c.py').write_text('z=3')
    venv = root / '.venv'
    venv.mkdir()
    (venv / 'd.py').write_text('w=4')
    assert count_source_files(root) == 3
""",
        category="self",
        difficulty="medium",
        tags=["filesystem", "recursion"],
    ),
]
