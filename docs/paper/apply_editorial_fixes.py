#!/usr/bin/env python3
"""Apply the three editorial fixes to the submitted manuscript as tracked changes.

1. §2.1 provision count 36 -> 40 (the graph holds 40 provisions, 60 nodes, 132 edges).
2. Delete the duplicated "Second, the single control false positive ..." paragraph
   in §3.2.2 (the second copy, which also reads "e-mail programmed").
3. Delete Tables 3, 4 and 5 with their captions: they report an earlier,
   superseded run, and Table 4's missed provisions contradict the frozen result.
   The revised §3 supersedes them.

Usage: python apply_editorial_fixes.py <unpacked_dir> [author]
"""
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def register_document_namespaces(path):
    """Register every prefix the document declares, so round-tripping through
    ElementTree preserves them (otherwise w14:paraId etc. come back as ns2:
    and the spliced-in root tag leaves those prefixes unbound)."""
    text = Path(path).read_text(encoding="utf-8")
    for prefix, uri in re.findall('xmlns:([A-Za-z0-9_]+)="([^"]+)"', text):
        try:
            ET.register_namespace(prefix, uri)
        except ValueError:
            pass

unpacked = sys.argv[1]
AUTHOR = sys.argv[2] if len(sys.argv) > 2 else "Manolis Maragoudakis"
STAMP = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

_next_id = [9000]


def rev_attrs():
    _next_id[0] += 1
    return {f"{W}id": str(_next_id[0]), f"{W}author": AUTHOR, f"{W}date": STAMP}


def text_of(el):
    return "".join(t.text or "" for t in el.iter(f"{W}t"))


def make_run(text, template=None):
    r = ET.Element(f"{W}r")
    if template is not None:
        rpr = template.find(f"{W}rPr")
        if rpr is not None:
            r.append(ET.fromstring(ET.tostring(rpr)))
    t = ET.SubElement(r, f"{W}t")
    t.text = text
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    return r


def run_to_deleted(run):
    """Convert a run in place into deleted-text form."""
    for t in run.findall(f"{W}t"):
        dt = ET.Element(f"{W}delText")
        dt.text = t.text
        dt.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        run.remove(t)
        run.append(dt)
    return run


def wrap_deleted(parent, runs):
    """Replace `runs` inside `parent` with a single <w:del> wrapper."""
    if not runs:
        return
    idx = list(parent).index(runs[0])
    dele = ET.Element(f"{W}del", rev_attrs())
    for r in runs:
        parent.remove(r)
        dele.append(run_to_deleted(r))
    parent.insert(idx, dele)


def delete_paragraph(p):
    """Mark every run deleted and the paragraph mark deleted, so accepting the
    revision removes the paragraph rather than leaving an empty one."""
    wrap_deleted(p, p.findall(f"{W}r"))
    ppr = p.find(f"{W}pPr")
    if ppr is None:
        ppr = ET.Element(f"{W}pPr")
        p.insert(0, ppr)
    rpr = ppr.find(f"{W}rPr")
    if rpr is None:
        rpr = ET.SubElement(ppr, f"{W}rPr")
    rpr.insert(0, ET.Element(f"{W}del", rev_attrs()))


def delete_table(tbl):
    """Mark all rows of a table deleted (row mark + cell content)."""
    for tr in tbl.findall(f"{W}tr"):
        trpr = tr.find(f"{W}trPr")
        if trpr is None:
            trpr = ET.Element(f"{W}trPr")
            tr.insert(0, trpr)
        trpr.append(ET.Element(f"{W}del", rev_attrs()))
        for tc in tr.findall(f"{W}tc"):
            for p in tc.findall(f"{W}p"):
                wrap_deleted(p, p.findall(f"{W}r"))


def delete_phrase_in_paragraph(p, phrase):
    """Tracked deletion of `phrase` inside one paragraph."""
    for run in p.findall(f"{W}r"):
        rt = text_of(run)
        if phrase not in rt:
            continue
        before, after = rt.split(phrase, 1)
        idx = list(p).index(run)
        p.remove(run)
        pieces = []
        if before:
            pieces.append(make_run(before, run))
        dele = ET.Element(f"{W}del", rev_attrs())
        dele.append(run_to_deleted(make_run(phrase, run)))
        pieces.append(dele)
        if after:
            pieces.append(make_run(after, run))
        for off, piece in enumerate(pieces):
            p.insert(idx + off, piece)
        return True
    return False


def replace_text_in_paragraph(p, old, new):
    """Tracked replacement of `old` with `new` inside one paragraph."""
    for run in p.findall(f"{W}r"):
        rt = text_of(run)
        if old not in rt:
            continue
        before, after = rt.split(old, 1)
        idx = list(p).index(run)
        p.remove(run)
        pieces = []
        if before:
            pieces.append(make_run(before, run))
        dele = ET.Element(f"{W}del", rev_attrs())
        dele.append(run_to_deleted(make_run(old, run)))
        pieces.append(dele)
        ins = ET.Element(f"{W}ins", rev_attrs())
        ins.append(make_run(new, run))
        pieces.append(ins)
        if after:
            pieces.append(make_run(after, run))
        for off, piece in enumerate(pieces):
            p.insert(idx + off, piece)
        return True
    return False


DOC = f"{unpacked}/word/document.xml"
ORIGINAL_XML = Path(DOC).read_text(encoding="utf-8")
# ElementTree only re-declares namespaces it knows, which would strip the
# w14/w15/w16* declarations that mc:Ignorable references. Keep the original
# root start tag and splice it back after writing.
register_document_namespaces(DOC)
_m = re.search(r"<w:document\b[^>]*>", ORIGINAL_XML)
ORIGINAL_ROOT_TAG = _m.group(0) if _m else None

tree = ET.parse(DOC)
body = tree.getroot().find(f"{W}body")
blocks = list(body)
applied = []

# --- Fix 1: provision count ------------------------------------------------
for el in blocks:
    if el.tag == f"{W}p":
        t = text_of(el)
        if "provision nodes (36 at time of writing" in t:
            if replace_text_in_paragraph(el, "(36 at time of writing", "(40 at time of writing"):
                applied.append("fix 1: §2.1 provision count 36 -> 40")
            break

# --- Fix 2: duplicated paragraph (delete the copy containing the typo) ------
dups = [el for el in blocks if el.tag == f"{W}p"
        and text_of(el).startswith("Second, the single control false positive")]
if len(dups) >= 2:
    target = next((d for d in dups if "programmed" in text_of(d)), dups[-1])
    delete_paragraph(target)
    applied.append("fix 2: deleted the duplicated §3.2.2 paragraph (the 'programmed' copy)")

# --- Fix 3: superseded Tables 3, 4 and 5 with their captions ---------------
for n in (3, 4, 5):
    cap = next((el for el in blocks if el.tag == f"{W}p"
                and text_of(el).startswith(f"Table {n}.")), None)
    if cap is None:
        continue
    i = blocks.index(cap)
    tbl = next((blocks[j] for j in range(i + 1, min(i + 4, len(blocks)))
                if blocks[j].tag == f"{W}tbl"), None)
    delete_paragraph(cap)
    if tbl is not None:
        delete_table(tbl)
    applied.append(f"fix 3: deleted Table {n} and its caption (superseded run)")

# --- Fix 3b: references to the deleted tables -----------------------------
blocks = list(body)
for el in blocks:
    if el.tag != f"{W}p":
        continue
    t = text_of(el)
    if "the deviation counts of Table 5 reflect" in t:
        if replace_text_in_paragraph(el, "the deviation counts of Table 5 reflect",
                                     "the deviation counts reported here reflect"):
            applied.append("fix 3b: Figure 2 caption no longer cites the deleted Table 5")
    elif "while Tables 3-5 preserve" in t:
        if delete_phrase_in_paragraph(
                el, ", while Tables 3-5 preserve the manuscript's detailed diagnostic "
                    "material for traceability"):
            applied.append("fix 3b: removed the sentence clause pointing to Tables 3-5")
    elif t.startswith("The detailed pattern remains useful diagnostically"):
        delete_paragraph(el)
        applied.append("fix 3b: deleted the paragraph that existed only to caveat Table 3")

tree.write(DOC, xml_declaration=True, encoding="UTF-8", method="xml")
if ORIGINAL_ROOT_TAG:
    # Restore the original root start tag, but keep any namespace ElementTree
    # hoisted onto the root (declarations that lived on inner elements in the
    # original, e.g. the drawing "a" prefix, are emitted at the root instead).
    out = Path(DOC).read_text(encoding="utf-8")
    written = re.search(r"<w:document\b[^>]*>", out)
    merged = ORIGINAL_ROOT_TAG
    if written:
        have = dict(re.findall('xmlns:([A-Za-z0-9_]+)="([^"]+)"', ORIGINAL_ROOT_TAG))
        for prefix, uri in re.findall('xmlns:([A-Za-z0-9_]+)="([^"]+)"', written.group(0)):
            if prefix not in have:
                merged = merged[:-1] + f' xmlns:{prefix}="{uri}">'
        out = out[:written.start()] + merged + out[written.end():]
    Path(DOC).write_text(out, encoding="utf-8")
print(f"author: {AUTHOR}")
for a in applied:
    print("  -", a)
print(f"{len(applied)} edit group(s) applied")
