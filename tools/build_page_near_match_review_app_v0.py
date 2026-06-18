#!/usr/bin/env python3
"""Build a compact CSV and local card UI for first-batch near-match review."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path
from typing import Any
from urllib.parse import quote


DEFAULT_REVIEW = Path(
    r"E:\commons\DocSpectrum\page_near_match_first30_evidence_v0.csv"
)
DEFAULT_COMPACT = Path(
    r"E:\commons\DocSpectrum\page_near_match_first30_compact_v0.csv"
)
DEFAULT_HTML = Path(
    r"E:\commons\DocSpectrum\page_near_match_first30_review_v0.html"
)

LABELS = [
    ("", "Не выбрано"),
    ("borrowing_candidate", "Возможное заимствование"),
    ("normative_form", "Нормативная / стандартная форма"),
    ("estimate_boilerplate", "Сметный шаблон"),
    ("shared_technical_content", "Общий технический материал"),
    ("false_positive", "Ложное совпадение"),
    ("uncertain", "Недостаточно данных"),
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def one_line(value: str) -> str:
    return " | ".join(part.strip() for part in (value or "").splitlines() if part.strip())


def useful_lines(value: str, limit: int = 14) -> list[str]:
    lines = []
    seen = set()
    for raw in (value or "").splitlines():
        line = raw.strip()
        key = line.casefold()
        if not line or key in seen:
            continue
        if len(line) <= 2 or line.replace(".", "").replace("-", "").isdigit():
            continue
        seen.add(key)
        lines.append(line)
    lines.sort(key=lambda item: (-len(item), item.casefold()))
    return lines[:limit]


def file_url(path: str, page: str) -> str:
    normalized = path.replace("\\", "/")
    if not normalized.startswith("/"):
        normalized = "/" + normalized
    return "file://" + quote(normalized, safe="/:") + f"#page={int(float(page))}&zoom=page-fit"


def compact_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    compact = []
    for row in rows:
        shared = useful_lines(row["shared_text_excerpt"], 10)
        left_only = useful_lines(row["left_only_text_excerpt"], 5)
        right_only = useful_lines(row["right_only_text_excerpt"], 5)
        compact.append(
            {
                "номер": row["review_rank"],
                "раздел": row["section"],
                "организация_1": row["left_organization"],
                "объект_1": row["left_object"],
                "файл_1": row["left_file"],
                "страница_1": row["left_page"],
                "pdf_1": row["left_pdf_path"],
                "организация_2": row["right_organization"],
                "объект_2": row["right_object"],
                "файл_2": row["right_file"],
                "страница_2": row["right_page"],
                "pdf_2": row["right_pdf_path"],
                "структурное_сходство": row["structural_similarity"],
                "сходство_текста": row["text_jaccard"],
                "общих_сегментов": row["shared_text_segments_metric"],
                "редких_общих_сегментов": row["rare_shared_text_segments"],
                "общих_форм_таблиц": row["shared_table_layouts"],
                "кратко_общий_текст": one_line("\n".join(shared)),
                "кратко_только_слева": one_line("\n".join(left_only)),
                "кратко_только_справа": one_line("\n".join(right_only)),
                "review_label": row["review_label"],
                "review_confidence": row["review_confidence"],
                "reviewer": row["reviewer"],
                "review_note": row["review_note"],
                "reviewed_at": row["reviewed_at"],
                "candidate_id": row["candidate_id"],
            }
        )
    return compact


def app_data(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        result.append(
            {
                "rank": int(row["review_rank"]),
                "candidateId": row["candidate_id"],
                "section": row["section"],
                "strength": row["candidate_strength"],
                "left": {
                    "organization": row["left_organization"],
                    "object": row["left_object"],
                    "file": row["left_file"],
                    "page": int(row["left_page"]),
                    "pdfUrl": file_url(row["left_pdf_path"], row["left_page"]),
                },
                "right": {
                    "organization": row["right_organization"],
                    "object": row["right_object"],
                    "file": row["right_file"],
                    "page": int(row["right_page"]),
                    "pdfUrl": file_url(row["right_pdf_path"], row["right_page"]),
                },
                "metrics": {
                    "structure": row["structural_similarity"],
                    "text": row["text_jaccard"],
                    "shared": row["shared_text_segments_metric"],
                    "rare": row["rare_shared_text_segments"],
                    "layouts": row["shared_table_layouts"],
                },
                "shared": useful_lines(row["shared_text_excerpt"], 14),
                "leftOnly": useful_lines(row["left_only_text_excerpt"], 7),
                "rightOnly": useful_lines(row["right_only_text_excerpt"], 7),
                "initial": {
                    "label": row["review_label"],
                    "confidence": row["review_confidence"],
                    "reviewer": row["reviewer"],
                    "note": row["review_note"],
                    "reviewedAt": row["reviewed_at"],
                },
            }
        )
    return result


def html_document(rows: list[dict[str, str]]) -> str:
    data = json.dumps(app_data(rows), ensure_ascii=False).replace("</", "<\\/")
    options = "".join(
        f'<option value="{html.escape(value)}">{html.escape(label)}</option>'
        for value, label in LABELS
    )
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DocSpectrum — проверка 30 совпадений</title>
<style>
:root {{
  --paper:#f4efe4; --ink:#17201d; --muted:#6d756e; --line:#c9c1b2;
  --accent:#b6422e; --panel:#fffdf7; --green:#315c4a;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; color:var(--ink); background:
  radial-gradient(circle at 10% 0%, #e8d8b9 0, transparent 32rem),
  linear-gradient(135deg, var(--paper), #e8ece5);
  font-family:Georgia, "Times New Roman", serif; }}
header {{ position:sticky; top:0; z-index:5; display:flex; gap:18px;
  align-items:center; padding:14px 22px; background:rgba(244,239,228,.96);
  border-bottom:1px solid var(--line); backdrop-filter:blur(8px); }}
h1 {{ margin:0; font-size:22px; letter-spacing:.02em; }}
.progress {{ margin-left:auto; color:var(--muted); }}
button, select, input, textarea {{ font:inherit; }}
button {{ border:1px solid var(--ink); background:var(--panel); padding:8px 13px;
  cursor:pointer; border-radius:2px; }}
button.primary {{ color:white; background:var(--green); border-color:var(--green); }}
main {{ max-width:1800px; margin:auto; padding:18px; }}
.meta {{ display:grid; grid-template-columns:1fr auto; gap:18px; padding:16px;
  background:var(--panel); border:1px solid var(--line); }}
.pair-title {{ font-size:20px; line-height:1.35; }}
.chips {{ display:flex; flex-wrap:wrap; gap:7px; margin-top:10px; }}
.chip {{ padding:4px 8px; border:1px solid var(--line); background:#f7f1e4;
  font:13px Consolas, monospace; }}
.pdf-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:12px; }}
.pdf-card {{ background:var(--panel); border:1px solid var(--line); }}
.pdf-head {{ padding:10px 12px; min-height:70px; border-bottom:1px solid var(--line); }}
.pdf-head strong {{ display:block; margin-bottom:4px; }}
.pdf-head a {{ color:var(--accent); }}
iframe {{ width:100%; height:58vh; border:0; background:#ddd; }}
.evidence {{ display:grid; grid-template-columns:1.4fr 1fr 1fr; gap:12px; margin-top:12px; }}
.evidence section, .decision {{ padding:14px; background:var(--panel); border:1px solid var(--line); }}
h2 {{ margin:0 0 10px; font-size:17px; }}
ul {{ margin:0; padding-left:20px; }}
li {{ margin:4px 0; line-height:1.3; }}
.decision {{ display:grid; grid-template-columns:1.4fr .8fr .8fr; gap:12px;
  align-items:start; margin-top:12px; }}
label {{ display:block; font-size:13px; color:var(--muted); margin-bottom:4px; }}
select, input, textarea {{ width:100%; padding:8px; border:1px solid var(--line);
  background:white; }}
textarea {{ min-height:76px; resize:vertical; }}
.wide {{ grid-column:1/-1; }}
.nav {{ display:flex; justify-content:space-between; gap:10px; margin-top:12px; }}
.done {{ color:var(--green); font-weight:bold; }}
@media(max-width:900px) {{
  .pdf-grid,.evidence,.decision {{ grid-template-columns:1fr; }}
  iframe {{ height:48vh; }}
  header {{ flex-wrap:wrap; }}
}}
</style>
</head>
<body>
<header>
  <h1>DocSpectrum · 30 пар для калибровки</h1>
  <button id="prev">← Предыдущая</button>
  <button id="next">Следующая →</button>
  <button id="nextPending">Следующая без решения</button>
  <button class="primary" id="export">Выгрузить разметку CSV</button>
  <span class="progress" id="progress"></span>
</header>
<main>
  <div class="meta">
    <div>
      <div class="pair-title" id="pairTitle"></div>
      <div class="chips" id="chips"></div>
    </div>
    <div id="state"></div>
  </div>
  <div class="pdf-grid">
    <article class="pdf-card"><div class="pdf-head" id="leftHead"></div><iframe id="leftPdf"></iframe></article>
    <article class="pdf-card"><div class="pdf-head" id="rightHead"></div><iframe id="rightPdf"></iframe></article>
  </div>
  <div class="evidence">
    <section><h2>Характерный общий текст</h2><ul id="shared"></ul></section>
    <section><h2>Только слева</h2><ul id="leftOnly"></ul></section>
    <section><h2>Только справа</h2><ul id="rightOnly"></ul></section>
  </div>
  <div class="decision">
    <div><label>Вердикт</label><select id="label">{options}</select></div>
    <div><label>Уверенность</label><select id="confidence">
      <option value="">Не выбрано</option><option value="high">Высокая</option>
      <option value="medium">Средняя</option><option value="low">Низкая</option>
    </select></div>
    <div><label>Рецензент</label><input id="reviewer" value="human"></div>
    <div class="wide"><label>Короткое обоснование</label><textarea id="note"></textarea></div>
  </div>
  <div class="nav"><button id="prevBottom">← Предыдущая</button><button class="primary" id="nextBottom">Сохранить и дальше →</button></div>
</main>
<script>
const candidates={data};
const storageKey="docspectrum-near-match-first30-v0";
let saved=JSON.parse(localStorage.getItem(storageKey)||"{{}}");
let index=0;
const $=id=>document.getElementById(id);
function esc(s){{return String(s??"").replace(/[&<>"']/g,c=>({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}}[c]));}}
function valueFor(c){{return saved[c.candidateId]||c.initial||{{}};}}
function saveCurrent(){{
 const c=candidates[index];
 saved[c.candidateId]={{label:$("label").value,confidence:$("confidence").value,
  reviewer:$("reviewer").value,note:$("note").value,
  reviewedAt:$("label").value?(new Date()).toISOString().slice(0,10):""}};
 localStorage.setItem(storageKey,JSON.stringify(saved));
}}
function list(id,values){{$(id).innerHTML=(values.length?values:["—"]).map(v=>`<li>${{esc(v)}}</li>`).join("");}}
function render(){{
 const c=candidates[index],v=valueFor(c);
 $("progress").textContent=`Пара ${{index+1}} из ${{candidates.length}} · размечено ${{candidates.filter(x=>valueFor(x).label).length}}`;
 $("pairTitle").textContent=`${{c.section}} · ${{c.left.organization}} / ${{c.right.organization}}`;
 $("chips").innerHTML=[
  `структура ${{c.metrics.structure}}`,`текст ${{c.metrics.text}}`,
  `общих сегментов ${{c.metrics.shared}}`,`редких ${{c.metrics.rare}}`,
  `форм таблиц ${{c.metrics.layouts}}`].map(x=>`<span class="chip">${{x}}</span>`).join("");
 $("leftHead").innerHTML=`<strong>${{esc(c.left.object)}} · ${{esc(c.left.file)}}</strong>страница ${{c.left.page}} · <a href="${{c.left.pdfUrl}}" target="_blank">открыть PDF отдельно</a>`;
 $("rightHead").innerHTML=`<strong>${{esc(c.right.object)}} · ${{esc(c.right.file)}}</strong>страница ${{c.right.page}} · <a href="${{c.right.pdfUrl}}" target="_blank">открыть PDF отдельно</a>`;
 $("leftPdf").src=c.left.pdfUrl; $("rightPdf").src=c.right.pdfUrl;
 list("shared",c.shared); list("leftOnly",c.leftOnly); list("rightOnly",c.rightOnly);
 $("label").value=v.label||""; $("confidence").value=v.confidence||"";
 $("reviewer").value=v.reviewer||"human"; $("note").value=v.note||"";
 $("state").innerHTML=v.label?'<span class="done">Размечено</span>':'Ожидает решения';
 $("prev").disabled=$("prevBottom").disabled=index===0;
 $("next").disabled=$("nextBottom").disabled=index===candidates.length-1;
}}
function move(delta){{saveCurrent();index=Math.max(0,Math.min(candidates.length-1,index+delta));render();}}
function movePending(){{
 saveCurrent();
 for(let offset=1;offset<=candidates.length;offset++){{
  const candidateIndex=(index+offset)%candidates.length;
  if(!valueFor(candidates[candidateIndex]).label){{index=candidateIndex;render();return;}}
 }}
}}
function csvCell(v){{return '"'+String(v??"").replaceAll('"','""').replaceAll("\\n"," ")+'"';}}
function exportCsv(){{
 saveCurrent();
 const head=["candidate_id","review_label","review_confidence","reviewer","review_note","reviewed_at"];
 const lines=[head.map(csvCell).join(",")];
 for(const c of candidates){{const v=valueFor(c);lines.push([c.candidateId,v.label,v.confidence,v.reviewer,v.note,v.reviewedAt].map(csvCell).join(","));}}
 const blob=new Blob(["\\ufeff"+lines.join("\\r\\n")],{{type:"text/csv;charset=utf-8"}});
 const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download="page_near_match_triage_labels_v0.csv";a.click();URL.revokeObjectURL(a.href);
}}
$("prev").onclick=$("prevBottom").onclick=()=>move(-1);
$("next").onclick=$("nextBottom").onclick=()=>move(1);
$("nextPending").onclick=movePending;
$("export").onclick=exportCsv;
for(const id of ["label","confidence","reviewer","note"])$(id).onchange=saveCurrent;
const firstPending=candidates.findIndex(candidate=>!valueFor(candidate).label);
if(firstPending>=0)index=firstPending;
render();
</script>
</body>
</html>"""


def build(review_path: Path, compact_path: Path, html_path: Path) -> None:
    rows = read_csv(review_path)
    compact = compact_rows(rows)
    write_csv(compact_path, compact, list(compact[0]) if compact else [])
    html_path.write_text(html_document(rows), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build compact and card-based near-match review interfaces."
    )
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--compact", type=Path, default=DEFAULT_COMPACT)
    parser.add_argument("--html", type=Path, default=DEFAULT_HTML)
    args = parser.parse_args()
    build(args.review, args.compact, args.html)
    print(args.compact)
    print(args.html)


if __name__ == "__main__":
    main()
