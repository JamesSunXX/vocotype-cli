#!/usr/bin/env python3
"""ASR 数据标注工具。

播放音频 → 显示 ASR 识别结果 → 人工修正 → 保存标注。
标注结果保存到 dataset/annotated.jsonl，可直接用于 Paraformer SFT 微调。

用法：
    python tools/annotate.py                    # 标注所有未标注的样本
    python tools/annotate.py --all              # 从头标注（含已标注的）
    python tools/annotate.py --dataset-dir DIR  # 指定数据集目录
"""

from __future__ import annotations

import json
import os
import readline  # noqa: F401 — 启用输入行编辑（上下箭头、Ctrl-A 等）
import subprocess
import sys
from pathlib import Path


def load_records(dataset_dir: Path) -> list[dict]:
    jsonl = dataset_dir / "dataset.jsonl"
    if not jsonl.exists():
        print(f"错误：找不到 {jsonl}")
        sys.exit(1)
    records = []
    for line in jsonl.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def load_annotated_ids(out_path: Path) -> set[str]:
    if not out_path.exists():
        return set()
    ids = set()
    for line in out_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            ids.add(json.loads(line)["id"])
    return ids


def play_audio(wav_path: Path) -> None:
    """用 macOS afplay 播放音频，Ctrl-C 可中断播放继续标注。"""
    try:
        subprocess.run(["afplay", str(wav_path)], check=False)
    except FileNotFoundError:
        print("  ⚠ afplay 不可用，跳过播放")


def save_annotation(out_path: Path, record: dict, corrected: str) -> None:
    entry = {
        "id": record["id"],
        "audio": record["audio"],
        "original_text": record.get("text", ""),
        "text": corrected,
        "duration": record.get("duration", 0.0),
    }
    with open(out_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="ASR 数据标注工具")
    parser.add_argument("--dataset-dir", default="dataset", help="数据集目录")
    parser.add_argument("--all", action="store_true", help="标注所有样本（含已标注）")
    args = parser.parse_args()

    dataset_dir = Path(args.dataset_dir)
    out_path = dataset_dir / "annotated.jsonl"
    records = load_records(dataset_dir)

    done_ids = set() if args.all else load_annotated_ids(out_path)
    todo = [r for r in records if r["id"] not in done_ids]

    if not todo:
        print("没有需要标注的样本。用 --all 可重新标注全部。")
        return

    print(f"共 {len(todo)} 条待标注（已完成 {len(done_ids)}/{len(records)}）")
    print("命令：回车=确认原文  r=重播  s=跳过  d=标记为脏数据  q=退出\n")

    annotated = 0
    for i, rec in enumerate(todo):
        wav = dataset_dir / rec["audio"]
        asr_text = rec.get("text", "")

        print(f"── [{i+1}/{len(todo)}] {rec['id']} ({rec.get('duration', 0):.1f}s) ──")
        print(f"  ASR: {asr_text}")

        if wav.exists():
            play_audio(wav)

        while True:
            try:
                user = input("  修正 (回车=原文ok): ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n退出。")
                print(f"本次标注 {annotated} 条，总计 {len(done_ids) + annotated}/{len(records)}")
                return

            if user == "q":
                print(f"本次标注 {annotated} 条，总计 {len(done_ids) + annotated}/{len(records)}")
                return
            if user == "r":
                if wav.exists():
                    play_audio(wav)
                continue
            if user == "s":
                print("  → 跳过")
                break
            if user == "d":
                # 标记为脏数据：text 设为空，训练时可过滤
                save_annotation(out_path, rec, "")
                annotated += 1
                print("  → 已标记为脏数据")
                break

            # 回车=原文正确，否则用修正文本
            corrected = user if user else asr_text
            save_annotation(out_path, rec, corrected)
            annotated += 1
            print(f"  → 已保存: {corrected[:60]}")
            break

    print(f"\n标注完成！本次 {annotated} 条，总计 {len(done_ids) + annotated}/{len(records)}")
    print(f"标注文件: {out_path}")


if __name__ == "__main__":
    main()
