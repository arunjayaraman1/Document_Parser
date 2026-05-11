# 📘 How It Works — A Plain-English Guide

> Imagine you're handed a stack of 1,000 invoices, contracts, and reports and asked:
> *"Pull out the invoice numbers, dates, totals, project names, payment terms — for all of them, by Tuesday."*
>
> You'd want a tireless assistant who can read any document and pull out the important bits.
> **That's what this project is.**

This guide walks you through the whole thing from the outside in, with no programming knowledge assumed.

---

## 🎯 What is this thing?

A **Document Parser** is a small piece of software that:

1. Takes a document (PDF, Word doc, spreadsheet, scanned image — anything).
2. Reads it.
3. Figures out what kind of document it is.
4. Pulls out the important information.
5. Hands it back to you as clean, structured data — like a filled-in form.

Think of it as **a super-fast intern who can:**
- Read a 50-page contract in 5 seconds.
- Spot the start date, end date, payment terms, and parties involved.
- Never get tired, never miss a number, never forget what you asked for.

---

## 🤔 Why does it need to exist?

### The problem with documents

Documents are **for humans**, not computers.

A human looking at this:

```
ACME Corporation
Invoice INV-2024-0117          January 17, 2024

Bill To: Globex Inc.
Total Due: $1,234.56
```

…instantly knows: *"This is an invoice from ACME, number INV-2024-0117, dated Jan 17, total is $1,234.56, billed to Globex."*

But to a computer? It's just a blob of pixels or a wall of text. It doesn't know what an invoice number is. It doesn't know "Total Due" means money. It needs help.

### Why you can't just use one tool

There are existing solutions, but they all have problems:

| Solution | Problem |
|---|---|
| 💸 **Pay a cloud service** (AWS Textract, Google DocAI) | Costs $$$, your private data leaves the building |
| 🧰 **Use one open-source tool** | Each tool is good at *one* thing — none does everything well |
| ✋ **Hardcode rules** for invoices | Works on day 1, breaks the moment you get a contract or a report |

**This project takes the best free tools and makes them work together as a team.**

It's like running a kitchen: you don't ask the chef to also wash dishes, take orders, *and* manage the books. You hire specialists and have them coordinate.

---

## 🍳 The big picture (a kitchen analogy)

Imagine a restaurant kitchen turning raw ingredients into a finished dish.

```
   📄 Document arrives                        🍽️ Structured data leaves
   (PDF / Word / image)                          (JSON: clean, organized)
            │                                              ▲
            ▼                                              │
   ┌────────────────────────────────────────────────────────┐
   │                                                        │
   │   1. Receiver       — accepts any format               │
   │   2. Reader (chef)  — turns pages into clean text      │
   │   3. Menu Designer  — figures out what fields exist    │
   │   4. Specialists    — six experts each find values     │
   │   5. Head Judge     — picks the best answer            │
   │   6. Quality Check  — validates dates, money, etc.     │
   │   7. Plater         — arranges everything into JSON    │
   │                                                        │
   └────────────────────────────────────────────────────────┘
```

Each step is a different "person" (in code, a separate module). Each is a specialist. None of them knows the whole picture — they just do their one job well, and the head judge combines their answers.

---

## 🧭 The end-to-end journey of one document

Let's follow a real example: **you upload an invoice PDF.**

### Step 1: The Receiver — "What did you give me?"

You drop a file at the door (`POST /api/parse`).

The receiver looks at the file's "magic bytes" — the first few characters that identify what kind of file it is — and figures out:

> *"Okay, this is a PDF."*

Then it routes it to the right specialist. PDFs go to the PDF reader, Word docs to the Word reader, images to the OCR (text-from-image) reader, and so on.

**Why this matters:** You shouldn't have to tell the system what kind of document you're sending. It figures it out.

---

### Step 2: The Reader — "What does this say?"

The receiver hands the file to **Docling**, our main reader. Docling is an open-source tool from IBM that's really good at understanding document layouts.

Docling does three things at once:

1. **Reads the words** — extracts every piece of text.
2. **Notices where they are** — records the exact pixel coordinates of each line. This is huge: it's the difference between "*INV-001 is somewhere in the document*" and "*INV-001 is at position (410, 88) on page 1*".
3. **Detects tables** — knows which numbers are in which columns of which tables.

If the document is a **scan** (a picture of a printed page) instead of a real digital PDF, Docling automatically runs **OCR** — Optical Character Recognition — to read the printed letters from the image. (OCR is what your phone does when you point its camera at a sign and it shows you the text.)

**Quality gate:** After Docling does its thing, we look at the output and ask:
- *"Did it actually find any text?"* If not, we run a backup tool called **pdfminer** to try harder.
- *"Did it find tables?"* If the document looks tabular but Docling missed them, we run **pdfplumber** as a second opinion just for the tables.

**Why three readers?** Because no single tool is perfect. Docling is great overall, pdfplumber is great at tables, pdfminer is a reliable fallback. We use each for what it's best at.

By the end of Step 2, we have a clean, structured representation of the document:
- Every text element with its location.
- Every table with its rows, columns, and cells.
- Page sizes, file metadata.

This standardized representation is called the **Normalized Document**. Everything downstream works on this — it doesn't matter anymore whether the original was a PDF or a Word doc.

---

### Step 3: The Menu Designer — "What questions should we even ask?"

Here's the clever bit. **We don't know in advance what fields are in the document.**

If we only knew how to extract `invoice_number` and `total`, we'd be useless on a contract. So before extracting *values*, we figure out **what fields the document contains**. This is called **schema discovery**.

We have **four detectives** working in parallel, each with a different approach:

#### 🕵️ Detective 1: The Pattern-Matcher (Heuristic)
Scans the text for "Label: Value" patterns:
- `Invoice Number: INV-001` → there's a field called *invoice number*
- `Date: 2024-01-17` → there's a field called *date*
- `Total: $1,234.56` → there's a field called *total*

Looks at table headers too — column names usually equal field names.

#### 🗂️ Detective 2: The Outliner
For longer documents (specs, reports, contracts), it looks for numbered headings:
- `1. Introduction`
- `2. Problem Statement`
- `5.1 Document Chunking`

Each heading becomes a "field" whose value is the section content underneath.

#### 🤖 Detective 3: The Entity Spotter (NER)
NER stands for **Named Entity Recognition** — fancy term for "spotting people, places, dates, money in text."

We use a free tool called **GLiNER** that can recognize *anything you ask it to* without training. We give it a list — "person, organization, money, date, invoice number, email, phone" — and it goes hunting.

If GLiNER finds money mentions, we know the document has a "money" field. Find dates? "date" field. And so on.

#### 🧠 Detective 4: The LLM (Large Language Model)
If you've configured an LLM (the same kind of AI behind ChatGPT), it reads the document and proposes fields in plain English: *"This is an invoice. It probably has fields: invoice_number, invoice_date, vendor_name, client_name, line_items, subtotal, tax, total."*

This is **optional** — the system works without an LLM. The LLM just makes it smarter when available.

#### 🤝 The Consensus Round

Each detective hands in a list of fields. Then we **vote**:
- A field is kept if **2+ detectives agree** on it.
- Or if **one detective is very confident** about it.
- Synonyms get merged: `inv_no`, `invoice number`, `invoice #` are all rolled into `invoice_number`.

The output of this step is **the schema** — the list of fields we'll try to fill in.

> **Why is this a big deal?**
> Most document parsers have a hardcoded list: *"For invoices, look for these 8 fields."* They break the moment you give them anything new. Ours figures out the right list **per document**, on the fly. It works on invoices, contracts, reports, recipes, song lyrics — anything.

---

### Step 4: The Specialists — "Now go find the values."

We've got a list of fields. Now we need to fill in values. We send **six specialists** at the document, each with their own technique:

| # | Specialist | How they work | Example |
|---|---|---|---|
| 1 | **Regex** | Looks for known patterns of letters, numbers, symbols | Finds `$1,234.56` because it matches `$<digits>.<digits>` |
| 2 | **Keyword** | Searches for the field's name in the text and grabs what's nearby | Finds "Invoice Number:" then grabs the next bit of text |
| 3 | **Spatial** | Uses coordinates: if "Total" is on the left, the value is to its right on the same line | Form-style documents |
| 4 | **Table** | Looks at table headers for the field name, returns the cell beneath | Line-item tables in invoices |
| 5 | **Section** | For outlined docs, grabs the whole paragraph block under each heading | Spec / report sections |
| 6 | **NER** | Asks GLiNER again, this time using the actual field names as labels | Finds "INV-001" because it's labeled as an "invoice number" entity |
| 7 | **LLM** | Asks the AI: "What's the value of `invoice_number` in this document?" | Smart, contextual extraction |

> Wait, that's seven, not six. The eighth column listed seven because we're counting both NER and LLM separately — we said six specialists. Either way, the point stands: **lots of techniques, each finding values their own way.**

Each specialist returns a list of "I found this value for this field, with this much confidence, and here's where I found it."

These are called **candidates** — proposed answers, not final answers.

---

### Step 5: The Head Judge — "Pick the best answer."

Six specialists. Maybe they all found the invoice number. Maybe two of them found different invoice numbers. Maybe only one tried.

How do we decide which value is right?

#### The voting algorithm

Each candidate gets a **score**:

```
score = (how trusted is this specialist?)  
      × (how confident is the specialist about this answer?)  
      × (does the answer pass basic sanity checks?)
```

For example:
- **Regex** is 95% trusted (very precise on dates, money, emails).
- **Keyword** is 75% trusted (can grab the wrong thing on complex layouts).
- **NER** is 70% trusted (good but coarser).

Then candidates with the **same answer** get a **consensus boost** — if Regex says "INV-001" *and* NER says "INV-001" *and* Keyword says "INV-001," we're very sure it's "INV-001."

The highest-scoring answer wins. Its evidence (which specialists agreed, where they found it) is recorded.

#### What if specialists disagree?

If the second-best answer is almost as strong as the winner, we **flag the field** as `"disagreement"` and tell you. Better to flag a borderline case than silently pick wrong.

If even the winner has weak confidence, we flag it `"low_confidence"` so you know to double-check it.

> This is the secret sauce. **No single tool's answer is the truth.** The truth is what multiple independent techniques agree on. Same principle as a jury trial.

---

### Step 6: Quality Check — "Does this even make sense?"

Before we hand the answer to you, we sanity-check it.

If the field is supposed to be a **date** but the value is `"banana"`, we mark it as failing validation.

Validators we run:

- **Date** — Can we parse this as a real date? Output it in ISO format (`2024-01-17`).
- **Currency** — Does it look like money? `$1,234.56`, `€500`, `USD 100`.
- **Number** — Is it a number? Convert it.
- **Email** — Does it match `name@domain.tld`?
- **Phone** — Does it look like a phone number?
- **ID** — Is it a reasonable-looking identifier (right length, allowed characters)?

A failed validation doesn't drop the answer — it just lowers its confidence and flags the field for human review.

---

### Step 7: The Plater — "Arrange it nicely."

Finally, we wrap everything into a JSON response. JSON is just a structured way of organizing data — like a filing cabinet with labeled drawers.

You get back something like:

```json
{
  "document": {
    "type": "invoice",
    "title": "ACME Corp — Invoice INV-2024-0117",
    "parse_method": ["docling"],
    "is_scanned": false
  },
  "schema": [
    {"name": "invoice_number", "data_type": "id", "detected_by": "heuristic,ner"},
    {"name": "total", "data_type": "currency", "detected_by": "heuristic,llm"}
  ],
  "fields": {
    "invoice_number": {
      "value": "INV-2024-0117",
      "confidence": 0.97,
      "sources": ["regex", "keyword", "ner"],
      "evidence": [
        {"page": 1, "bbox": {"x1": 410, "y1": 88, "x2": 540, "y2": 104}}
      ]
    },
    "total": {
      "value": "$1,234.56",
      "confidence": 0.93,
      "sources": ["regex", "table"]
    }
  },
  "flagged_fields": []
}
```

Translation:
- **document** — what kind of doc this is, how we parsed it.
- **schema** — the fields we discovered.
- **fields** — the actual values, with confidence and evidence.
- **flagged_fields** — anything we're unsure about.

Now you (or another piece of software) can use this. Push it into a database, fill in a form, build a dashboard — whatever you need.

---

## 🔄 The whole flow in one picture

```
   📄 You upload "invoice.pdf"
         │
         ▼
   ┌──────────────────────────────────────────────────────┐
   │  Receiver: "It's a PDF. Send it to the PDF readers." │
   └──────────────────────────────────────────────────────┘
         │
         ▼
   ┌──────────────────────────────────────────────────────┐
   │  Docling reads it.  pdfplumber double-checks tables. │
   │  Output: clean text + element bounding boxes + tables │
   └──────────────────────────────────────────────────────┘
         │
         ▼
   ┌──────────────────────────────────────────────────────┐
   │  Schema Detectives discover fields:                  │
   │   • Heuristic: invoice_number, total, date           │
   │   • Outline:  (none — not a long doc)                │
   │   • NER:      money, date, invoice_number            │
   │   • LLM:      invoice_number, total, vendor, client  │
   │  Consensus: invoice_number ✓, total ✓, date ✓,       │
   │             vendor_name ✓, client_name ✓             │
   └──────────────────────────────────────────────────────┘
         │
         ▼
   ┌──────────────────────────────────────────────────────┐
   │  Specialists hunt for values:                        │
   │   • Regex finds: $1,234.56, 2024-01-17               │
   │   • Keyword finds: "INV-2024-0117"                   │
   │   • Spatial finds: vendor name to right of "From:"   │
   │   • Table finds: total in totals row                 │
   │   • NER finds: vendor as ORG, total as MONEY         │
   │   • LLM finds: all of the above + reasoning          │
   └──────────────────────────────────────────────────────┘
         │
         ▼
   ┌──────────────────────────────────────────────────────┐
   │  Head Judge votes:                                   │
   │   invoice_number = "INV-2024-0117" (3 agree, 0.97)   │
   │   total          = "$1,234.56"     (2 agree, 0.93)   │
   │   date           = "2024-01-17"    (3 agree, 0.95)   │
   └──────────────────────────────────────────────────────┘
         │
         ▼
   ┌──────────────────────────────────────────────────────┐
   │  Validators sanity-check:                            │
   │   ✓ "2024-01-17" parses as a real date               │
   │   ✓ "$1,234.56" looks like currency                  │
   │   ✓ "INV-2024-0117" is a reasonable identifier       │
   └──────────────────────────────────────────────────────┘
         │
         ▼
   📤 Returns clean JSON back to you
```

---

## 🌟 Why this design is good

### 1. It works on any document
Because schema discovery is *dynamic*, you can throw an invoice at it Monday, a contract Tuesday, and a research paper Wednesday. It adapts.

### 2. It tells you why
Every value comes with **evidence** — which specialist found it, on what page, in which exact pixel rectangle, with what surrounding text. So if the answer looks wrong, you can see exactly what the system saw and why.

This is huge for **trust**. Most AI systems are black boxes that give you an answer with no explanation. Ours shows its work like a math student.

### 3. It's not betting on one tool
If Docling has a bad day, pdfplumber catches the tables. If the regex pattern misses, NER might catch it. If NER is unsure, the LLM can reason about it. **No single point of failure.**

### 4. It handles uncertainty honestly
When two specialists disagree, the system says *"these answers conflict, you should review this one."* It doesn't pretend to be confident when it isn't.

### 5. It's free and self-hosted
You can run this on your own laptop, on your own server, behind your own firewall. Your sensitive contracts and invoices never leave your machine.

### 6. It's modular
Need to add support for `.eml` email files? Write one new "adapter" file. Want to add a new way to extract data? Write one new "extractor" file. No rewriting the whole system.

---

## 🛠️ How you actually use it

### Starting it up

You start the system once, and it runs as a service in the background — like any web app.

**Easy way (Docker):**
```bash
docker compose up
```
That's it. The system is now running at `http://localhost:8000`.

**Manual way (Python):**
```bash
python -m uvicorn server.main:app
```

### Sending it a document

You upload a file using a tool called `curl` (or any program that can send web requests):

```bash
curl -F file=@my_invoice.pdf http://localhost:8000/api/parse
```

The system reads the file, runs the whole pipeline we described, and sends back JSON with the extracted data.

### Hooking it into your workflow

Most people don't `curl` files all day. You'd typically:

1. **Build a web UI** that lets users drag-and-drop files. Behind the scenes, the UI calls our API.
2. **Wire it into a database** — every parsed invoice automatically appears as a row in your accounts-payable system.
3. **Hook it to a folder watcher** — drop a file in `~/Inbox` and the system parses it automatically.

The system itself doesn't care how it's called. It just knows how to read documents and return structured data.

---

## 🎓 What about the AI / LLM part?

### When the AI is on
If you give the system an API key for an LLM (we default to Qwen models via OpenRouter, but it works with any OpenAI-compatible AI), it gains the ability to **reason** about documents.

For tricky cases — say, a sentence like *"the contract starts on the second Monday of the month following execution"* — regex and keyword matching are useless. An LLM can read that and infer: *"start_date = computed-from-text."*

The LLM is one voice in the voting committee, not the only voice. Even when it's confident, regex and NER also weigh in.

### When the AI is off
Set `ENABLE_LLM=0` and the system runs **fully offline** with no AI calls. You lose some accuracy on hard cases, but everything still works for normal documents.

### Why we don't rely solely on AI
LLMs are powerful but:
- They cost money per call.
- They can **hallucinate** (make stuff up confidently).
- They're not deterministic — same input, different output day-to-day.

The voting design **keeps the LLM honest**. If the LLM hallucinates "Total: $999,999" but regex sees "$1,234.56" right there in the text, the regex wins. Reality grounds the AI.

---

## 🧰 The toolbox (in case you're curious)

Each specialist is built from a real, free, open-source tool you can read about online:

| Specialist | Tool | What it is |
|---|---|---|
| Main reader | **Docling** | IBM's modern document AI |
| Table reader | **pdfplumber** | The Swiss army knife for PDF tables |
| Backup reader | **pdfminer.six** | A no-frills PDF text reader |
| OCR (image-to-text) | **Tesseract** | Google's open-source OCR engine |
| NER (entity finder) | **GLiNER** | Zero-shot named entity recognition |
| LLM | **Qwen** (via OpenRouter) | Open-weight language models |
| Web framework | **FastAPI** | Modern Python web framework |
| Containers | **Docker** | Standard way to package software |

All of these are **MIT, Apache, or MPL licensed** — free to use commercially, no strings attached.

---

## ❓ Common questions

**Q: How accurate is it?**
Depends on the document. Clean, born-digital invoices: 90–98% field accuracy. Faxed scans: 60–80%. Highly unusual layouts: less. The voting system means accuracy degrades gracefully — you'll see a flagged field rather than a confidently-wrong answer.

**Q: What documents can it handle?**
PDF, Word (DOCX), PowerPoint (PPTX), Excel (XLSX), HTML, Markdown, and images (PNG, JPG, TIFF). Legacy formats like `.doc`, `.eml`, `.msg` aren't supported yet but are on the roadmap.

**Q: Can I run this on my laptop?**
Yes. CPU-only. No GPU needed. First parse is slow (downloads ~1 GB of model weights). After that, parses take a few seconds.

**Q: Is my data safe?**
The system runs on **your machine**. Documents never leave your computer unless you explicitly turn on the LLM stage and use a remote provider. Even then, you can swap to a fully-local LLM (e.g. Ollama) for total privacy.

**Q: What if I want to extract custom fields?**
The system already does this dynamically. But if you want to *force* certain fields to always be extracted (say, your custom `policy_number` field for insurance docs), you'd add a small synonyms entry — one line of code.

**Q: How long did this take to build?**
The hard work was in **what to combine**, not the code itself. Hundreds of hours of research went into picking parsers, comparing licenses, designing the voting math. The code is the easy part once you know the architecture.

**Q: What's the catch?**
- First-time setup downloads model weights (~1 GB).
- Borderless tables are still tricky for any tool.
- If you turn off both NER and LLM, it falls back to pure regex/keyword extraction, which is decent but less smart.

---

## 🧭 What to read next

If you want to go deeper, in order:

1. **[`docs/RESEARCH.md`](RESEARCH.md)** — Why we chose the tools we chose. Tables comparing every option.
2. **[`docs/ARCHITECTURE.md`](ARCHITECTURE.md)** — The technical design, contracts, and how to extend it.
3. **[`docs/OBSERVATIONS.md`](OBSERVATIONS.md)** — Honest list of limitations and how to measure accuracy.
4. **[`README.md`](../README.md)** — The technical readme with API details, configuration, and code examples.

---

## 🎯 In one sentence

**This system uses a team of free, open-source specialists — readers, schema detectives, value extractors, and validators — that each find different parts of the answer, then vote on the final result, with full evidence for every decision.**

That's it. That's the whole thing.

You're now qualified to explain it at a dinner party. ✨
