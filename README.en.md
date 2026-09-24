# Exam Paper Generator

Turn an Excel question bank into print-ready exam papers and answer sheets, exported as
Word or PDF.

A **local desktop utility**: double-click to run. No database, no network access, no
account. Your data never leaves your machine.

**Who it's for**: teachers who build their own exams, training providers, internal
corporate assessments. Put your questions into Excel, and get a formatted paper in
minutes instead of laying it out by hand.

> 中文说明见 [README.md](README.md)

---

## Contents

- [Quick start](#quick-start)
- [Features in detail](#features-in-detail)
  - [Four question types](#four-question-types)
  - [Three ways to pick questions](#three-ways-to-pick-questions)
  - [Difficulty weighting](#difficulty-weighting)
  - [Knowledge point coverage](#knowledge-point-coverage)
  - [When you run out of questions](#when-you-run-out-of-questions)
  - [Generating multiple papers](#generating-multiple-papers)
  - [Preview: what you see is what you export](#preview-what-you-see-is-what-you-export)
  - [Output formats and paper sizes](#output-formats-and-paper-sizes)
  - [Answer sheets](#answer-sheets)
  - [Templates and history](#templates-and-history)
- [Preparing your Excel question bank](#preparing-your-excel-question-bank)
- [FAQ](#faq)
- [Running from source](#running-from-source)
- [License](#license)

---

## Quick start

1. **Get a question bank.** Click **示例** (Sample) in the app to try the bundled
   primary-school Chinese bank (130 questions). To use your own, see
   [the format below](#preparing-your-excel-question-bank).
2. **Configure the paper.** The left panel goes top to bottom: question bank, paper
   info, assembly method, filters, output. Leaving most options blank gives you the
   sensible default.
3. **Check the preview.** The right panel shows the paper's **real layout** and
   refreshes automatically as you change settings.
4. **Export.** Pick an output folder, tick Word and/or PDF, click **导出试卷** (Export).

Don't need an answer sheet? Don't want difficulty weighting or knowledge point
targeting? That's fine — leave them alone and they stay out of your way.

---

## Features in detail

### Four question types

| Type | How to enter the answer | On the paper |
|------|------------------------|--------------|
| **True/False** | `1` (true) or `0` (false) | A blank line after the question |
| **Single choice** | A letter `A`–`E`; options in the 选项A… columns | Options laid out horizontally |
| **Multiple choice** | Letters run together, e.g. `ABD` | Same as above |
| **Short answer** | The full reference answer | Ruled writing lines after the question |

- The four types **mix freely**. Reorder them with the ↑↓ buttons and set a point
  value per type.
- True/False answers also accept `√` / `×` / `对` / `错`. The app normalises them, so you
  don't have to reformat an existing question bank.
- **Short answer** reference answers are listed separately at the end of the answer key —
  running text doesn't fit the compact `1-5: A B C D` format used for objective questions.
- **Writing space follows the answer sheet.** With no answer sheet, the paper keeps a
  blank line for True/False and three ruled lines for each short-answer question
  (students write on the paper). Once you tick an answer sheet, those lines are
  **removed entirely** — students write on the sheet instead. The UI says so explicitly.

### Three ways to pick questions

**Random (随机抽取)** — the usual choice. Enter a count per question type; the app draws
them at random. A given configuration always produces the same paper, so what you
preview is exactly what you export.

**By ratio (按比例导出)** — for when you care about the mix rather than exact counts.
Enter percentages and the app does the arithmetic:

> True/False 30 / Single 50 / Multiple 20, 50 questions total → **15 / 25 / 10**

The ratios don't have to sum to 100 — `3 : 5 : 2` gives the same result as
`30 : 50 : 20`. Remainders are distributed by fractional part, so you never hit the
classic "asked for 40%, got 70%" surprise.

**Sequential (顺序导出)** — for going through the bank in its original order (say, in
chapter order). Enter a question-number range within the type, e.g. "questions 20
through 45". **The count field is ignored here** — the range alone determines how many
questions appear.

### Difficulty weighting

This section only appears when your bank has a 难度 (difficulty) column. Enter a weight
per level:

> Easy 5 / Medium 3 / Hard 2 → **50% / 30% / 20%**

As with ratios, the weights don't have to sum to any particular number. Leave all three
blank for no difficulty constraint.

If a level runs short, the app **borrows from other levels and says so** — it won't
quietly hand you a paper that's harder than you asked for. The UI also shows how many
questions exist per level ("Easy 48, Medium 48, Hard 24") so you know what's realistic.

### Knowledge point coverage

Appears when your bank has a 知识点 (knowledge point) column. Tick the topics you want
and the app will:

1. Draw questions only from the selected topics;
2. Try to ensure **every selected topic appears at least once**, so a minor chapter
   doesn't get skipped entirely.

Tick nothing for no topic constraint. Useful for "this test should cover chapters 1
through 3".

With a large bank (hundreds of topics) the list is searchable, sorted by how many
questions each topic has, and only the top entries render at once — selected topics stay
pinned at the top so you can always see what you picked.

### When you run out of questions

If you ask for more questions than the bank holds, the app **will not silently give you
fewer**. You choose the behaviour up front:

| Option | What happens |
|--------|--------------|
| **Reuse and warn** (default) | Reuses already-drawn questions to reach the count, and tells you which |
| **Shrink and warn** | Produces as many as it can, and tells you the actual count |
| **Fail outright** | Stops so you can fix the configuration |

Either way you get an explicit message. You will never see "asked for 100, got 30" with
no explanation.

### Generating multiple papers

Set 生成份数 (number of papers) to 3 and you get three papers, auto-numbered.

With **多份试卷不重复出题** (no repeats across papers) ticked, the three papers share
**no questions at all** (provided the bank is large enough). Handy for producing A/B/C
versions of the same exam.

If the bank can't support fully disjoint papers, the app falls back to the strategy you
picked above and tells you.

### Excluding previously used questions

Tick **排除历史已出过的题** and the app remembers what you've used before (stored in
`%APPDATA%\ExamPaperGen\history.json`) and avoids it. Matching is by question **content**,
so re-sorting or inserting rows in your bank doesn't break it.

You can review and clear the history from the UI.

### Preview: what you see is what you export

The preview pane renders **the actual PDF that will be exported** — not a separate
approximation. Page breaks, line wrapping, fonts and line spacing match the real file
exactly.

Any configuration change refreshes the preview automatically (debounced at 400 ms, so
typing doesn't stutter).

You can preview the **exam paper and the answer sheet separately** using the segmented
control in the preview header.

### Output formats and paper sizes

- **Exam paper**: Word (`.docx`) and PDF. Both come from the same content model, so
  question order and numbering always agree.
- **Answer sheet**: also available in Word and PDF.
- **Paper size**:
  - **A4** — the usual single sheet.
  - **A3, two A4 pages imposed** — landscape A3 with page 1 on the left half and page 2
    on the right. Fold or cut down the middle and each half is a properly laid out A4
    paper. Prints two pages at once and halves your paper usage.
- **Configurable file names.** The default is `试卷` (paper), giving `试卷-1.docx`,
  `试卷-2.docx` and so on. Set it to something like `Grade3-Chinese-Final` and the files
  follow — handy for keeping batches apart without overwriting each other.

**Black-and-white friendly**: all text is pure black; emphasis uses bold, size and solid
rules only. No light-grey fills (they turn into noise when photocopied) and no line
thinner than 0.6 pt (thinner lines vanish on many printers).

### Answer sheets

Designed for **hand marking**, and written rather than bubbled: students write `√`/`×`
for True/False and the letters `ABCD` for choice questions.

Why not bubble sheets: bubbles exist for optical mark readers and need print precision to
be fillable. For hand marking they just waste space. The written format uses less than
half the area — **120 questions fit on a single A4 sheet**, where bubbles would need two
or three.

Question numbers on the sheet match the paper exactly (if Single Choice is questions 6–10
on the paper, it's 6–10 on the sheet).

### Templates and history

- **Templates**: save the whole configuration as JSON and restore it with one click.
  Worth setting up if you produce the same kind of paper repeatedly.
- **History**: every export is logged (questions, paper count, random seed, output files)
  and can be reviewed or cleared.

---

## Preparing your Excel question bank

### Required columns

| Column | Description |
|--------|-------------|
| **题型** (type) | `判断题` / `单选题` / `多选题` / `简答题` — must match exactly |
| **题目** (question) | The question text |
| **正确答案** (answer) | See the per-type notes below |

### Optional columns

| Column | Description |
|--------|-------------|
| **选项A** … **选项E** | Choice options. Leave blank for True/False and Short Answer |
| **难度** (difficulty) | Any text label, e.g. `易` / `中` / `难`. Adding this column enables difficulty weighting |
| **知识点** (knowledge point) | Any text label, e.g. `第一章 基础护理`. Adding this column enables topic coverage |

### How to write the answer for each type

| Type | What goes in 正确答案 |
|------|----------------------|
| True/False | `1` (true) or `0` (false). Also accepts `√` `×` `对` `错` |
| Single choice | One letter, e.g. `B` |
| Multiple choice | Letters run together, e.g. `ABD` (no commas or spaces) |
| Short answer | The full reference answer; can be a paragraph |

### A complete example

| 题型 | 题目 | 正确答案 | 难度 | 知识点 | 选项A | 选项B | 选项C | 选项D |
|------|------|----------|------|--------|-------|-------|-------|-------|
| 判断题 | “日”字是象形字。 | 1 | 易 | 第一章 拼音与汉字 | | | | |
| 单选题 | 《静夜思》的作者是？ | B | 易 | 第四章 古诗文积累 | 杜甫 | 李白 | 白居易 | 王维 |
| 多选题 | 下列属于中国四大名著的有？ | ABC | 中 | 第五章 文学常识 | 《红楼梦》 | 《西游记》 | 《水浒传》 | 《聊斋志异》 |
| 简答题 | 请写出“守株待兔”的意思，并说明它告诉我们什么道理。 | 守着树桩等待兔子撞上来。比喻死守狭隘经验、不知变通…… | 中 | 第二章 词语与成语 | | | | |

### File formats

- `.xlsx`, `.xlsm` and `.csv` are supported.
- CSV encoding is auto-detected for UTF-8 and GBK, so Chinese CSVs exported from Excel
  work directly.
- **`.xls` (Excel 97-2003) is not supported** — save as `.xlsx` first.

### Don't want to start from scratch?

Click **示例** in the app to load the bundled `题库模板.xlsx` (primary-school Chinese,
130 questions, all four types, with difficulty and knowledge point columns). Editing that
is the fastest way to start.

To switch to another subject, edit the question content in
`tools/make_sample_bank.py` and re-run it to regenerate the template.

---

## FAQ

**I changed a setting but the preview didn't update.**
The preview refreshes automatically. If it stays blank, check that you've selected a
question type and entered a count — those two cases show a message in the preview pane.

**The paper has fewer questions than I asked for.**
The bank ran out. The notice bar at the top says how many were missing and how many were
actually produced. To make this an error instead, set 题目不够时 to 直接报错.

**I can't find the exported files.**
The success notice is clickable — it opens the output folder in Explorer. The folder is
shown in the 输出 (Output) section on the left.

**A colleague opened it and got a blank window.**
The interface needs the WebView2 runtime. Windows 11 always has it; the vast majority of
Windows 10 machines do too. If it's genuinely missing, the installer will detect that and
walk them through installing it.

**Can I carry it on a USB stick?**
Yes — use the folder build (copy the whole `dist/ExamPaperGenerator/` directory and
double-click the exe inside). The installer version writes to `Program Files`, so it
isn't portable. Either way, user data (history, settings) lives in
`%APPDATA%\ExamPaperGen` and doesn't travel with the folder.

**Is macOS or Linux supported?**
The code itself is cross-platform, but only Windows is packaged and tested. Running from
source on another OS is theoretically possible but would need the Chinese font paths
adjusted, and hasn't been verified.

---

## Running from source

Python 3.10 or newer.

```bash
git clone https://github.com/Hermannmayer/Examination-paper-generation-system.git
cd Examination-paper-generation-system
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe main.py
```

There's also a command-line interface for batch work:

```bash
.venv/Scripts/python.exe -m app.cli --bank 题库模板.xlsx --out ./out \
    --judgment 10 --mcq 15 --multi 5 --answers --pdf --card
```

### Building a release

Official releases are built by GitHub Actions. Just push a `v*` tag:

```bash
git tag v1.0.0 && git push origin v1.0.0
```

CI runs the tests, builds, self-checks, and attaches the installer to a GitHub Release.
For local debugging, use `powershell -ExecutionPolicy Bypass -File packaging/build.ps1`.

> Notes for contributors (architecture layering, the two artifact self-checks, and
> several engineering pitfalls) live in the code comments — see the headers of `main.py`,
> `packaging/exam.spec` and `ui/assets/css/app.css`.

---

## License

**GNU General Public License v3.0 (GPL-3.0)** — a strong copyleft licence.

You're free to use, modify and distribute this program, but **any derivative work must
also be released under the GPL with complete source**, and no additional restrictions may
be imposed. See [LICENSE](LICENSE) for the full terms.

If you intend to offer this program **as a network service** (where GPL obligations don't
trigger), AGPL-3.0 would be the right licence instead — open an issue and I'll switch it.

All bundled third-party components are GPL-3.0 compatible: reportlab (BSD),
openpyxl / python-docx / Pillow (MIT), pywebview / lxml (BSD), pdf.js (Apache-2.0),
PyInstaller (GPL-2.0+ with the bootloader exception).
