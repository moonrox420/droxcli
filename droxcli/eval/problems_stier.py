"""
S-Tier benchmark problems — designed to expose model capability limits.

A model scoring 100% on the standard suite should score ~60-70% here.
"""

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


PROBLEMS_STIER: List[Problem] = [
    Problem(
        id="X01",
        prompt=(
            "Write a function called skyline(buildings) in eval_target.py. "
            "buildings is a list of [left, right, height] lists. "
            "Return the skyline as a list of [x, height] points where height changes. "
            "Use a sweep line algorithm with a max-heap. "
            "Include all necessary imports. "
            "The last point must always have height 0."
        ),
        test_code="""
from eval_target import skyline
assert skyline([[2, 9, 10]]) == [[2, 10], [9, 0]]
assert skyline([[1, 3, 3], [5, 8, 2]]) == [[1, 3], [3, 0], [5, 2], [8, 0]]
result = skyline([[2,9,10],[3,7,15],[5,12,12],[15,20,10],[19,24,8]])
assert result[0] == [2, 10]
assert result[1] == [3, 15]
assert result[-1] == [24, 0]
""",
        category="algorithm",
        difficulty="s-tier",
        tags=["sweep-line", "heap"],
    ),
    Problem(
        id="X02",
        prompt=(
            "Write a function called alien_order(words) in eval_target.py. "
            "Given a list of words sorted in an alien language, return a string "
            "of unique characters in the correct alien alphabetical order. "
            "Return empty string if no valid order exists (cycle) or if a longer "
            "word appears before its prefix (e.g. ['abc', 'ab'] is invalid). "
            "Use topological sort with cycle detection."
        ),
        test_code="""
from eval_target import alien_order
result = alien_order(["wrt", "wrf", "er", "ett", "rftt"])
assert result.index('t') < result.index('f')
assert result.index('w') < result.index('e')
assert result.index('r') < result.index('t')
assert alien_order(["z", "x", "z"]) == ""
assert alien_order(["abc", "ab"]) == ""
result2 = alien_order(["abc"])
assert set(result2) == {'a', 'b', 'c'}
""",
        category="algorithm",
        difficulty="s-tier",
        tags=["topological-sort", "graph", "dfs"],
    ),
    Problem(
        id="X03",
        prompt=(
            "Write a function called max_profit_cooldown(prices) in eval_target.py. "
            "Given stock prices, find the maximum profit with a cooldown: "
            "after selling you must wait one day before buying again. "
            "You may not hold more than one stock at a time. "
            "Use a 3-state dynamic programming approach: hold, sold, rest."
        ),
        test_code="""
from eval_target import max_profit_cooldown
assert max_profit_cooldown([1, 2, 3, 0, 2]) == 3
assert max_profit_cooldown([1])             == 0
assert max_profit_cooldown([1, 2])          == 1
assert max_profit_cooldown([2, 1])          == 0
assert max_profit_cooldown([6,1,3,2,4,7])   == 6
""",
        category="algorithm",
        difficulty="s-tier",
        tags=["dynamic-programming", "state-machine"],
    ),
    Problem(
        id="X04",
        prompt=(
            "Write a function called trap_water(height) in eval_target.py. "
            "Given a list of non-negative integers representing an elevation map, "
            "compute how much water it can trap after rain. "
            "Solve in O(n) time and O(1) space using two pointers."
        ),
        test_code="""
from eval_target import trap_water
assert trap_water([0,1,0,2,1,0,1,3,2,1,2,1]) == 6
assert trap_water([4,2,0,3,2,5])              == 9
assert trap_water([])                          == 0
assert trap_water([3])                         == 0
assert trap_water([3, 0, 3])                   == 3
""",
        category="algorithm",
        difficulty="s-tier",
        tags=["two-pointer", "arrays"],
    ),
    Problem(
        id="X05",
        prompt=(
            "Write a class called MedianFinder in eval_target.py. "
            "It must have: add_num(num) to add a number, and "
            "find_median() -> float to return the current median. "
            "find_median() must return a float (e.g. 1.5 for [1,2]). "
            "Use two heaps for O(log n) add and O(1) median."
        ),
        test_code="""
from eval_target import MedianFinder
mf = MedianFinder()
mf.add_num(1)
mf.add_num(2)
assert mf.find_median() == 1.5
mf.add_num(3)
assert mf.find_median() == 2.0
mf.add_num(4)
assert mf.find_median() == 2.5
mf.add_num(5)
assert mf.find_median() == 3.0
mf2 = MedianFinder()
mf2.add_num(0)
assert mf2.find_median() == 0.0
""",
        category="data-structures",
        difficulty="s-tier",
        tags=["heap", "median", "design"],
    ),
    Problem(
        id="X06",
        prompt=(
            "Write a class called WordDictionary in eval_target.py. "
            "It must support: add_word(word) and search(word) -> bool. "
            "search supports '.' as a wildcard matching any single character. "
            "Implement using a Trie."
        ),
        test_code="""
from eval_target import WordDictionary
wd = WordDictionary()
wd.add_word("bad")
wd.add_word("dad")
wd.add_word("mad")
assert wd.search("pad") is False
assert wd.search("bad") is True
assert wd.search(".ad") is True
assert wd.search("b..") is True
assert wd.search("...") is True
assert wd.search("b.d.") is False
wd.add_word("at")
assert wd.search("a.") is True
assert wd.search(".t") is True
""",
        category="data-structures",
        difficulty="s-tier",
        tags=["trie", "dfs", "wildcard"],
    ),
    Problem(
        id="X07",
        prompt=(
            "Write a class called RangeSum in eval_target.py. "
            "Constructor takes a list of integers. "
            "update(i, val) sets index i to val. "
            "range_sum(left, right) returns sum from index left to right inclusive. "
            "Both operations must run in O(log n). Use a Binary Indexed Tree (Fenwick Tree)."
        ),
        test_code="""
from eval_target import RangeSum
rs = RangeSum([1, 3, 5, 7, 9, 11])
assert rs.range_sum(0, 2) == 9
assert rs.range_sum(2, 5) == 32
rs.update(1, 2)
assert rs.range_sum(0, 2) == 8
assert rs.range_sum(0, 5) == 35
rs.update(3, 10)
assert rs.range_sum(2, 4) == 24
""",
        category="data-structures",
        difficulty="s-tier",
        tags=["fenwick-tree", "range-query"],
    ),
    Problem(
        id="X08",
        prompt=(
            "Write a function called parse_json_path(data, path) in eval_target.py. "
            "data is a nested dict/list. path is a dot-notation string like "
            "'users.0.address.city' where integers index into lists. "
            "Return the value at that path, or None if any key/index doesn't exist."
        ),
        test_code="""
from eval_target import parse_json_path
data = {
    "users": [
        {"name": "Alice", "address": {"city": "NYC", "zip": "10001"}},
        {"name": "Bob",   "address": {"city": "LA"}},
    ],
    "count": 2,
}
assert parse_json_path(data, "count")                == 2
assert parse_json_path(data, "users.0.name")         == "Alice"
assert parse_json_path(data, "users.1.address.city") == "LA"
assert parse_json_path(data, "users.0.address.zip")  == "10001"
assert parse_json_path(data, "users.2.name")         is None
assert parse_json_path(data, "users.0.phone")        is None
assert parse_json_path(data, "missing.key")          is None
""",
        category="real-world",
        difficulty="s-tier",
        tags=["parsing", "nested-data"],
    ),
    Problem(
        id="X09",
        prompt=(
            "Write a function called tokenize_expression(expr) in eval_target.py. "
            "Given a math expression string like '3 + x * (2.5 - y)', "
            "return a list of token dicts, each with 'type' and 'value'. "
            "Types: NUMBER, IDENT (variable/function name), "
            "OP (+ - * / ^ %), LPAREN, RPAREN. "
            "The 'value' field must be the EXACT substring from the input — "
            "do not convert or parse it, just slice it as-is from the source string. "
            "Ignore whitespace. Raise ValueError on unknown characters."
        ),
        test_code="""
from eval_target import tokenize_expression
tokens = tokenize_expression("3 + x * (2.5 - y)")
types  = [t['type']  for t in tokens]
values = [t['value'] for t in tokens]
assert types  == ['NUMBER','OP','IDENT','OP','LPAREN','NUMBER','OP','IDENT','RPAREN']
assert values == ['3', '+', 'x', '*', '(', '2.5', '-', 'y', ')']

t2 = tokenize_expression("-1 + 2")
assert t2[0] == {'type': 'OP', 'value': '-'}
assert t2[1] == {'type': 'NUMBER', 'value': '1'}

t3 = tokenize_expression("x_1 + theta_2")
assert t3[0] == {'type': 'IDENT', 'value': 'x_1'}

import pytest
with pytest.raises(ValueError):
    tokenize_expression("x @ y")
""",
        category="real-world",
        difficulty="s-tier",
        tags=["tokenizer", "lexer", "parsing"],
    ),
    Problem(
        id="X10",
        prompt=(
            "Write a class called RateLimiter in eval_target.py implementing "
            "a sliding window rate limiter. "
            "Constructor: RateLimiter(max_calls, window_seconds). "
            "Method: is_allowed(timestamp) -> bool. "
            "Returns True if the call at this timestamp is within the rate limit. "
            "timestamp is a float (unix seconds). "
            "Do NOT use time.time() — use only the provided timestamp."
        ),
        test_code="""
from eval_target import RateLimiter
rl = RateLimiter(3, 10)
assert rl.is_allowed(1.0)  is True
assert rl.is_allowed(2.0)  is True
assert rl.is_allowed(3.0)  is True
assert rl.is_allowed(4.0)  is False
assert rl.is_allowed(11.1) is True
assert rl.is_allowed(12.0) is True
assert rl.is_allowed(13.0) is True
assert rl.is_allowed(14.0) is False
assert rl.is_allowed(22.5) is True
""",
        category="real-world",
        difficulty="s-tier",
        tags=["sliding-window", "rate-limiting", "design"],
    ),
    Problem(
        id="XS1",
        prompt=(
            "Write a function called diff_summary(original, modified) in eval_target.py. "
            "Both arguments are strings (file contents). "
            "Return a dict with keys: "
            "'added' (list of lines in modified but not original), "
            "'removed' (list of lines in original but not modified), "
            "'unchanged' (int count of lines present in both). "
            "Use the longest common subsequence approach. "
            "Use only Python standard library — no third-party packages."
        ),
        test_code="""
from eval_target import diff_summary
orig = "line1\\nline2\\nline3\\nline4"
mod  = "line1\\nline2 modified\\nline3\\nline5"
result = diff_summary(orig, mod)
assert "line2 modified" in result['added']
assert "line5"          in result['added']
assert "line2"          in result['removed']
assert "line4"          in result['removed']
assert result['unchanged'] == 2

r2 = diff_summary("", "hello\\nworld")
assert r2['added']     == ["hello", "world"]
assert r2['removed']   == []
assert r2['unchanged'] == 0

r3 = diff_summary("a\\nb\\nc", "a\\nb\\nc")
assert r3['added']     == []
assert r3['removed']   == []
assert r3['unchanged'] == 3
""",
        category="self",
        difficulty="s-tier",
        tags=["lcs", "diff", "dynamic-programming"],
    ),
]
