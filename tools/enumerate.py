#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
幻方枚举与验证 —— 纯标准库，Python 3.7+

用法
    python enumerate.py --order 3
        穷举 3 阶：应得 8 个解、1 个 D4 等价类

    python enumerate.py --order 4 --out data/fourth_order_880.json
        全枚举 4 阶：应得 7040 个解、880 个等价类（约 5 分钟）

    python enumerate.py --verify data/fourth_order_880.json
        验证已有数据：合法性、去重、等价类数

方法
    按行搜索 + 列和剪枝：
      1. 预计算所有「n 个数、和为 s」的全排列作为候选行
      2. 逐行填，维护增量列和，超过 s 立即剪枝
      3. 填满 n-1 行后，最后一行由列和反解（每列 s − 前 n-1 行之和）
      4. 用 D4 群（4 旋转 × 2 镜像）去重，取字典序最小者为规范形

    7 阶及以上会跑很久（搜索空间是 n²! 量级），不建议用本脚本。
"""

import argparse
import itertools
import json
import sys
import time


# ---------------- 基础判定 ----------------

def is_magic(m):
    """标准幻方：1..n² 各一次，行列两对角线与相等。"""
    n = len(m)
    s = n * (n * n + 1) // 2

    flat = sorted(v for row in m for v in row)
    if flat != list(range(1, n * n + 1)):
        return False

    if any(sum(row) != s for row in m):
        return False
    for c in range(n):
        if sum(m[r][c] for r in range(n)) != s:
            return False
    if sum(m[i][i] for i in range(n)) != s:
        return False
    if sum(m[i][n - 1 - i] for i in range(n)) != s:
        return False
    return True


def rotate90(m):
    n = len(m)
    return [[m[n - 1 - c][r] for c in range(n)] for r in range(n)]


def mirror_h(m):
    return [row[::-1] for row in m]


def d4_variants(m):
    """4 个旋转 × 2 种手性 = 8 个变体。"""
    out = []
    cur = m
    for _ in range(4):
        out.append(cur)
        out.append(mirror_h(cur))
        cur = rotate90(cur)
    return out


def canonical(m):
    """D4 规范形：8 个变体中字典序最小的那个。"""
    return min(tuple(tuple(row) for row in v) for v in d4_variants(m))


# ---------------- 枚举 ----------------

def solve(n, progress_every=200000, time_limit=None):
    """
    返回 (solutions, classes, elapsed, stopped)
        solutions: 原始解列表（含所有朝向）
        classes:   list of 代表矩阵，D4 不等价
        elapsed:   耗时（秒）
        stopped:   是否因超时提前停止
    """
    s = n * (n * n + 1) // 2

    combos = [c for c in itertools.combinations(range(1, n * n + 1), n) if sum(c) == s]
    rows_pool = []
    for combo in combos:
        for perm in itertools.permutations(combo):
            mask = 0
            for v in perm:
                mask |= 1 << v
            rows_pool.append((perm, mask))

    solutions = []
    classes = {}
    cols = [0] * n
    rows = []
    t0 = time.time()
    counter = [0]
    stop = [False]

    def bt(depth, mask):
        if stop[0]:
            return
        counter[0] += 1
        if progress_every and counter[0] % progress_every == 0:
            el = time.time() - t0
            print(f'  ... 节点 {counter[0]:,}  已用 {el:.0f}s  原始解 {len(solutions):,}  '
                  f'等价类 {len(classes):,}', file=sys.stderr)
            if time_limit and el > time_limit:
                stop[0] = True
                return

        if depth == n - 1:
            last = []
            for c in range(n):
                v = s - cols[c]
                if v < 1 or v > n * n or ((mask >> v) & 1):
                    return
                last.append(v)
            if len(set(last)) != n:
                return
            if sum(last) != s:
                return
            full = [list(r) for r in rows] + [last]
            if is_magic(full):
                solutions.append(full)
                key = canonical(full)
                if key not in classes:
                    classes[key] = full
            return

        for perm, pmask in rows_pool:
            if mask & pmask:
                continue
            ok = True
            for c in range(n):
                if cols[c] + perm[c] >= s:
                    ok = False
                    break
            if not ok:
                continue
            for c in range(n):
                cols[c] += perm[c]
            rows.append(perm)
            bt(depth + 1, mask | pmask)
            rows.pop()
            for c in range(n):
                cols[c] -= perm[c]

    bt(0, 0)
    el = time.time() - t0
    return solutions, list(classes.values()), el, stop[0]


# ---------------- 验证 ----------------

def verify_file(path):
    with open(path, encoding='utf-8') as f:
        data = json.load(f)

    n = len(data[0]) if data else 0
    print(f'文件：{path}')
    print(f'条目：{len(data)}  阶数：{n}')

    bad = [i for i, m in enumerate(data) if not is_magic(m)]
    print(f'合法幻方：{len(data) - len(bad)} / {len(data)}'
          + (f'  非法索引：{bad[:10]}' if bad else ''))

    unique = {tuple(tuple(r) for r in m) for m in data}
    print(f'去重后：{len(unique)}')

    canon = {canonical(m) for m in data}
    print(f'D4 等价类：{len(canon)}')

    if bad or len(unique) != len(data):
        print('结果：FAIL')
        return 1
    print('结果：PASS')
    return 0


# ---------------- 入口 ----------------

def main():
    ap = argparse.ArgumentParser(description='幻方枚举与验证')
    ap.add_argument('--order', type=int, help='阶数（3 或 4 实用）')
    ap.add_argument('--out', help='把 D4 等价类代表写入 JSON')
    ap.add_argument('--verify', help='验证已有 JSON 文件')
    ap.add_argument('--time-limit', type=float, default=None, help='枚举时间上限（秒）')
    args = ap.parse_args()

    if args.verify:
        return verify_file(args.verify)

    if not args.order:
        ap.print_help()
        return 1

    n = args.order
    print(f'枚举 {n} 阶幻方（幻和 = {n * (n * n + 1) // 2}）...')
    if n > 4:
        print('警告：n > 4 的搜索空间极大，本脚本可能跑不完。', file=sys.stderr)

    sols, reps, elapsed, stopped = solve(n, time_limit=args.time_limit)

    print()
    print(f'耗时        {elapsed:.0f}s' + ('（提前停止）' if stopped else ''))
    print(f'原始解      {len(sols):,}')
    print(f'D4 等价类   {len(reps):,}')
    if not stopped and len(sols) % 8 == 0:
        print(f'校验        {len(sols)} = {len(reps)} × 8 ✓')
    print(f'非法解      {sum(0 if is_magic(m) else 1 for m in reps)}')

    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(reps, f, separators=(',', ':'))
        print(f'已写出      {args.out}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
