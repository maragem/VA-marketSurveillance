// Builds docs/paper/results-section.docx from the narrative markdown plus the
// generated Table 1 CSV, with Table 1 rendered as a real Word table.
// Usage:  npm install docx  &&  node docs/paper/build-results-docx.js
// Regenerate after editing results-narrative.md or re-running make_table1.py.
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
  WidthType, ShadingType, AlignmentType, BorderStyle,
} = require('docx');

const REPO = path.resolve(__dirname, '..', '..');
const NARRATIVE = fs.readFileSync(path.join(REPO, 'docs/paper/results-narrative.md'), 'utf8');
const TABLE_MD = fs.readFileSync(path.join(REPO, 'docs/paper/table1.md'), 'utf8');

// ---------------------------------------------------------------- table 1 ----
// Parse the generated markdown table: caption, header row, body rows, provenance.
const tableLines = TABLE_MD.split('\n');
const caption = tableLines[0].replace(/\*\*/g, '');
const rowLines = tableLines.filter((l) => l.startsWith('|') && !/^\|[-|]+\|$/.test(l));
const cells = rowLines.map((l) => l.slice(1, -1).split('|').map((c) => c.trim()));
const [headerCells, ...bodyCells] = cells;
const provenance = tableLines
  .filter((l) => l.startsWith('- **'))
  .map((l) => l.replace(/^- /, '').replace(/\*\*/g, '').replace(/`/g, ''));

const TABLE_WIDTH = 9360; // landscape-ish content width in DXA
const COL_WIDTHS = [2400, 480, 900, 1180, 780, 900, 780, 1060, 880];
const sum = COL_WIDTHS.reduce((a, b) => a + b, 0);
if (sum !== TABLE_WIDTH) throw new Error(`column widths sum to ${sum}, expected ${TABLE_WIDTH}`);

const thinBorder = { style: BorderStyle.SINGLE, size: 4, color: 'AAAAAA' };
const cellBorders = { top: thinBorder, bottom: thinBorder, left: thinBorder, right: thinBorder };

function tableCell(text, { header = false, first = false, bold = false } = {}, idx = 0) {
  return new TableCell({
    width: { size: COL_WIDTHS[idx], type: WidthType.DXA },
    borders: cellBorders,
    shading: header ? { type: ShadingType.CLEAR, fill: 'E8EEF4' } : undefined,
    margins: { top: 60, bottom: 60, left: 90, right: 90 },
    children: [
      new Paragraph({
        alignment: first ? AlignmentType.LEFT : AlignmentType.CENTER,
        spacing: { before: 0, after: 0 },
        children: [new TextRun({ text, bold: header || bold, size: 17 })],
      }),
    ],
  });
}

const table1 = new Table({
  columnWidths: COL_WIDTHS,
  width: { size: TABLE_WIDTH, type: WidthType.DXA },
  rows: [
    new TableRow({
      tableHeader: true,
      children: headerCells.map((c, i) => tableCell(c, { header: true, first: i === 0 }, i)),
    }),
    ...bodyCells.map((row) => {
      const isD = row[0].startsWith('D ');
      return new TableRow({
        children: row.map((c, i) => tableCell(c, { first: i === 0, bold: isD }, i)),
      });
    }),
  ],
});

// ------------------------------------------------------------- markdown ------
// Minimal inline formatter: **bold**, *italic*, `code`.
function runs(text) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g;
  let last = 0;
  let m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index) }));
    const tok = m[0];
    if (tok.startsWith('**')) out.push(new TextRun({ text: tok.slice(2, -2), bold: true }));
    else if (tok.startsWith('`')) {
      out.push(new TextRun({ text: tok.slice(1, -1), font: 'Consolas', size: 19 }));
    } else out.push(new TextRun({ text: tok.slice(1, -1), italics: true }));
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last) }));
  return out.length ? out : [new TextRun({ text })];
}

const body = [];
const lines = NARRATIVE.split('\n');
let pendingBullet = null;

function flushBullet() {
  if (pendingBullet === null) return;
  body.push(new Paragraph({
    bullet: { level: 0 },
    spacing: { before: 60, after: 60 },
    children: runs(pendingBullet),
  }));
  pendingBullet = null;
}

for (let i = 0; i < lines.length; i++) {
  const raw = lines[i];
  const line = raw.trim();

  if (line === '---') { flushBullet(); continue; }
  if (line === '') { flushBullet(); continue; }

  // Continuation of a bullet (indented, no marker)
  if (pendingBullet !== null && /^\s{2,}\S/.test(raw) && !/^\s*[-*]\s/.test(raw)) {
    pendingBullet += ' ' + line;
    continue;
  }

  if (line.startsWith('# ')) {
    flushBullet();
    body.push(new Paragraph({
      heading: HeadingLevel.HEADING_1,
      spacing: { before: 240, after: 160 },
      children: runs(line.slice(2)),
    }));
    continue;
  }
  if (line.startsWith('## ')) {
    flushBullet();
    const text = line.slice(3);
    body.push(new Paragraph({
      heading: HeadingLevel.HEADING_2,
      spacing: { before: 280, after: 120 },
      children: runs(text),
    }));
    // Insert Table 1 (caption, table, provenance) where the narrative points to it.
    if (/^Table 1$/.test(text)) {
      body.push(new Paragraph({
        spacing: { before: 80, after: 120 },
        children: runs(caption),
      }));
      body.push(table1);
      body.push(new Paragraph({
        spacing: { before: 160, after: 60 },
        children: [new TextRun({ text: 'Provenance of the reported runs:', bold: true, size: 19 })],
      }));
      for (const p of provenance) {
        body.push(new Paragraph({
          bullet: { level: 0 },
          spacing: { before: 20, after: 20 },
          children: [new TextRun({ text: p, size: 18 })],
        }));
      }
      // Skip the markdown pointer line ("See docs/paper/table1.md ...").
      while (i + 1 < lines.length && !lines[i + 1].startsWith('## ')) i++;
    }
    continue;
  }
  if (line.startsWith('### ')) {
    flushBullet();
    body.push(new Paragraph({
      heading: HeadingLevel.HEADING_3,
      spacing: { before: 200, after: 100 },
      children: runs(line.slice(4)),
    }));
    continue;
  }
  if (/^[-*]\s/.test(line)) {
    flushBullet();
    pendingBullet = line.replace(/^[-*]\s+/, '');
    continue;
  }

  // Body paragraph: join wrapped lines until a blank/structural line.
  flushBullet();
  let para = line;
  while (i + 1 < lines.length) {
    const next = lines[i + 1];
    const t = next.trim();
    if (t === '' || t === '---' || t.startsWith('#') || /^[-*]\s/.test(t)) break;
    para += ' ' + t;
    i++;
  }
  body.push(new Paragraph({
    spacing: { before: 80, after: 80, line: 300 },
    children: runs(para),
  }));
}
flushBullet();

// ------------------------------------------------------------- document ------
const doc = new Document({
  styles: {
    default: {
      document: { run: { font: 'Calibri', size: 22 }, paragraph: { spacing: { line: 300 } } },
      heading1: { run: { font: 'Calibri', size: 32, bold: true, color: '1F3864' } },
      heading2: { run: { font: 'Calibri', size: 26, bold: true, color: '2E5496' } },
      heading3: { run: { font: 'Calibri', size: 23, bold: true, color: '2E5496' } },
    },
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 },      // A4 portrait
        margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 },
      },
    },
    children: body,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  const out = path.join(REPO, 'docs/paper/results-section.docx');
  fs.writeFileSync(out, buf);
  console.log(`wrote ${out} (${(buf.length / 1024).toFixed(0)} KB), ${body.length} blocks`);
});
