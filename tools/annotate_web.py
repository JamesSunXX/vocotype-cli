#!/usr/bin/env python3
"""轻量 Web 标注工具：浏览器中播放音频、编辑 ASR 文本、保存标注。

用法：python tools/annotate_web.py [--port 8686] [--dataset-dir dataset]
"""

from __future__ import annotations

import json
import os
import argparse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# 全局配置，在 main() 中设置
DATASET_DIR: Path = Path("dataset")
ANNOTATED_PATH: Path = Path("dataset/annotated.jsonl")


def _load_records() -> list[dict]:
    jsonl = DATASET_DIR / "dataset.jsonl"
    if not jsonl.exists():
        return []
    records = []
    for line in jsonl.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def _load_annotations() -> dict[str, dict]:
    """返回 {id: annotation_record}"""
    if not ANNOTATED_PATH.exists():
        return {}
    result = {}
    for line in ANNOTATED_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            result[rec["id"]] = rec
    return result


def _save_annotation(record_id: str, original: str, corrected: str, audio: str, duration: float) -> None:
    entry = {
        "id": record_id,
        "audio": audio,
        "original_text": original,
        "text": corrected,
        "duration": duration,
    }
    with open(ANNOTATED_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# HTML 页面单独放在 _HTML 变量中，见下方
_HTML = ""  # 在文件末尾赋值


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/":
            self._send_html()
        elif parsed.path == "/api/records":
            self._send_records()
        elif parsed.path.startswith("/audio/"):
            # 提供音频文件
            wav = DATASET_DIR / parsed.path.lstrip("/")
            if wav.exists():
                self.send_response(200)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Length", str(wav.stat().st_size))
                self.end_headers()
                self.wfile.write(wav.read_bytes())
            else:
                self.send_error(404)
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/annotate":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            _save_annotation(
                body["id"], body["original_text"], body["text"],
                body["audio"], body.get("duration", 0),
            )
            self._json_response({"ok": True})
        else:
            self.send_error(404)

    def _send_html(self):
        data = _HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_records(self):
        records = _load_records()
        annotations = _load_annotations()
        # 合并标注状态，按时间倒序（最新在前）
        for r in records:
            ann = annotations.get(r["id"])
            if ann:
                r["annotated"] = True
                r["corrected_text"] = ann["text"]
            else:
                r["annotated"] = False
        records.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
        self._json_response(records)

    def _json_response(self, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # 静默常规请求日志，只打印错误
        if args and str(args[0]).startswith("4"):
            super().log_message(format, *args)


_HTML = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ASR 标注工具</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, system-ui, sans-serif; background: #1a1a2e; color: #e0e0e0; padding: 16px; }
h1 { font-size: 18px; margin-bottom: 12px; color: #a0c4ff; }
.stats { font-size: 13px; color: #888; margin-bottom: 12px; }
.filter { margin-bottom: 12px; display: flex; gap: 8px; }
.filter button { padding: 4px 12px; border: 1px solid #444; background: #2a2a4a; color: #ccc; border-radius: 4px; cursor: pointer; font-size: 13px; }
.filter button.active { background: #4a4a8a; color: #fff; border-color: #6a6aaa; }
.item { background: #16213e; border: 1px solid #333; border-radius: 8px; padding: 12px; margin-bottom: 8px; }
.item.done { opacity: 0.6; }
.item-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; font-size: 12px; color: #888; }
.asr-text { font-size: 15px; margin-bottom: 8px; line-height: 1.5; color: #f0f0f0; }
.controls { display: flex; gap: 8px; align-items: center; }
.controls input { flex: 1; padding: 6px 10px; border: 1px solid #444; background: #0f3460; color: #fff; border-radius: 4px; font-size: 14px; }
.controls button { padding: 6px 14px; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; font-weight: 500; }
.btn-play { background: #4a90d9; color: #fff; }
.btn-save { background: #27ae60; color: #fff; }
.btn-dirty { background: #e74c3c; color: #fff; }
.btn-play:hover { background: #5aa0e9; }
.btn-save:hover { background: #2ecc71; }
.btn-dirty:hover { background: #f75c4c; }
.badge { display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 11px; }
.badge-done { background: #27ae60; color: #fff; }
.badge-dirty { background: #e74c3c; color: #fff; }
.badge-pending { background: #555; color: #ccc; }
</style>
</head>
<body>
<h1>🎙 ASR 数据标注</h1>
<div class="stats" id="stats"></div>
<div class="filter">
  <button class="active" data-f="all">全部</button>
  <button data-f="pending">待标注</button>
  <button data-f="done">已标注</button>
</div>
<div id="list"></div>

<script>
let records = [];
let filter = 'all';
let audio = null;

async function load() {
  records = await (await fetch('/api/records')).json();
  render();
}

function render() {
  const list = document.getElementById('list');
  const filtered = records.filter(r =>
    filter === 'all' ? true : filter === 'done' ? r.annotated : !r.annotated
  );
  const total = records.length;
  const done = records.filter(r => r.annotated).length;
  document.getElementById('stats').textContent = `已标注 ${done}/${total}`;

  list.innerHTML = filtered.map((r, i) => {
    const badge = r.annotated
      ? (r.corrected_text === '' ? '<span class="badge badge-dirty">脏数据</span>' : '<span class="badge badge-done">已标注</span>')
      : '<span class="badge badge-pending">待标注</span>';
    return `<div class="item ${r.annotated ? 'done' : ''}" data-idx="${records.indexOf(r)}">
      <div class="item-header"><span>${fmtDate(r.timestamp)} · ${(r.duration||0).toFixed(1)}s</span>${badge}</div>
      <div class="asr-text">${esc(r.text || '')}</div>
      <div class="controls">
        <button class="btn-play" onclick="play(${records.indexOf(r)})">▶ 播放</button>
        <input id="inp-${records.indexOf(r)}" value="${esc(r.corrected_text || r.text || '')}" placeholder="输入修正文本">
        <button class="btn-save" onclick="save(${records.indexOf(r)})">✓ 保存</button>
        <button class="btn-dirty" onclick="dirty(${records.indexOf(r)})">✗ 脏数据</button>
      </div>
    </div>`;
  }).join('');
}

function esc(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

function fmtDate(ts) {
  if (!ts) return '';
  const d = new Date(ts);
  return `${d.getMonth()+1}/${d.getDate()} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
}

function play(i) {
  if (audio) { audio.pause(); }
  audio = new Audio('/' + records[i].audio);
  audio.play();
}

async function save(i) {
  const r = records[i];
  const text = document.getElementById('inp-' + i).value.trim();
  if (!text) return alert('文本不能为空，如果是脏数据请点"脏数据"按钮');
  await fetch('/api/annotate', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ id: r.id, original_text: r.text, text, audio: r.audio, duration: r.duration })
  });
  r.annotated = true;
  r.corrected_text = text;
  render();
}

async function dirty(i) {
  const r = records[i];
  await fetch('/api/annotate', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ id: r.id, original_text: r.text, text: '', audio: r.audio, duration: r.duration })
  });
  r.annotated = true;
  r.corrected_text = '';
  render();
}

// 筛选按钮
document.querySelector('.filter').addEventListener('click', e => {
  if (e.target.dataset.f) {
    filter = e.target.dataset.f;
    document.querySelectorAll('.filter button').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    render();
  }
});

// 快捷键：在输入框中按 Enter 保存，Ctrl+P 播放
document.addEventListener('keydown', e => {
  if (e.key === 'Enter' && e.target.tagName === 'INPUT') {
    const idx = parseInt(e.target.id.split('-')[1]);
    save(idx);
  }
});

load();
</script>
</body>
</html>"""


def main():
    global DATASET_DIR, ANNOTATED_PATH
    parser = argparse.ArgumentParser(description="ASR Web 标注工具")
    parser.add_argument("--port", type=int, default=8686)
    parser.add_argument("--dataset-dir", default="dataset")
    args = parser.parse_args()

    # 先 chdir 到项目根目录，再解析相对路径为绝对路径
    os.chdir(Path(__file__).resolve().parent.parent)
    DATASET_DIR = Path(args.dataset_dir).resolve()
    ANNOTATED_PATH = DATASET_DIR / "annotated.jsonl"

    if not (DATASET_DIR / "dataset.jsonl").exists():
        print(f"错误：找不到 {DATASET_DIR / 'dataset.jsonl'}")
        return
    server = HTTPServer(("127.0.0.1", args.port), Handler)
    print(f"标注工具已启动: http://127.0.0.1:{args.port}")
    print(f"数据集: {DATASET_DIR.absolute()}")
    print("按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
