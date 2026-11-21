"""Document model: numbered headings, figures, tables, notes, listings, TOC."""
import re
from html import escape


def md(s):
    """Inline markup: `code`, **bold**, *italic*, [text](href)."""
    s = escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<![*\w])\*([^*]+)\*(?![*\w])", r"<i>\1</i>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    return s


NOTE_ICON = ('<svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="9" fill="#c51a4a"/>'
             '<rect x="9" y="8.4" width="2" height="6.6" rx="0.6" fill="#fff"/>'
             '<circle cx="10" cy="5.6" r="1.25" fill="#fff"/></svg>')
IMP_ICON = ('<svg viewBox="0 0 20 20"><polygon points="10,1.5 19,18 1,18" fill="#e08a00"/>'
            '<rect x="9" y="7" width="2" height="6" rx="0.6" fill="#fff"/>'
            '<circle cx="10" cy="15.3" r="1.2" fill="#fff"/></svg>')


class Doc:
    def __init__(self):
        self.out = []
        self.toc = []
        self.ch = 0
        self.sec = 0
        self.sub = 0
        self.fig = 0
        self.tab = 0
        self.labels = {}
        self.appendix = False
        self.pending = []           # headings waiting for the block they introduce

    # Headings are held back and emitted together with the next block inside a
    # break-inside: avoid wrapper, so a heading never ends a page on its own.
    def _head(self, html):
        self.pending.append(html)

    def _emit(self, html):
        if self.pending:
            html = '<div class="keep">' + "".join(self.pending) + html + "</div>"
            self.pending = []
        self.out.append(html)

    def hold(self, html):
        self.pending.append(html)

    # ---- headings -----------------------------------------------------------------
    def chapter(self, title, appendix_letter=None):
        if appendix_letter:
            self.appendix = True
            num = f"Appendix {appendix_letter}"
            self.ch = appendix_letter
        else:
            self.ch += 1
            num = f"Chapter {self.ch}"
        self.sec = self.sub = 0
        hid = f"ch{self.ch}"
        text = f"{num}. {title}" if not appendix_letter else f"{num}: {title}"
        self.toc.append(("c", hid, text))
        self._flush()
        self.out.append(f'<h1 id="{hid}">{escape(text)}</h1>')

    def section(self, title, label=None):
        self.sec += 1
        self.sub = 0
        n = f"{self.ch}.{self.sec}."
        hid = f"s{self.ch}-{self.sec}"
        self.toc.append(("s", hid, f"{n} {title}"))
        if label:
            self.labels[label] = (f"Section {n[:-1]}", hid)
        self._head(f'<h2 id="{hid}">{escape(n + " " + title)}</h2>')

    def subsection(self, title, label=None):
        self.sub += 1
        n = f"{self.ch}.{self.sec}.{self.sub}."
        hid = f"s{self.ch}-{self.sec}-{self.sub}"
        self.toc.append(("ss", hid, f"{n} {title}"))
        if label:
            self.labels[label] = (f"Section {n[:-1]}", hid)
        self._head(f'<h3 id="{hid}">{escape(n + " " + title)}</h3>')

    def h4(self, title):
        self._head(f"<h4>{md(title)}</h4>")

    # ---- text ----------------------------------------------------------------------
    def p(self, *paras, cls=None):
        c = f' class="{cls}"' if cls else ""
        for s in paras:
            self._emit(f"<p{c}>{self.refs(md(s))}</p>")

    def ul(self, items):
        h = ["<ul>"]
        for it in items:
            if isinstance(it, (list, tuple)):
                h.append(f"<li>{self.refs(md(it[0]))}<ul>" +
                         "".join(f"<li>{self.refs(md(x))}</li>" for x in it[1]) + "</ul></li>")
            else:
                h.append(f"<li>{self.refs(md(it))}</li>")
        h.append("</ul>")
        self._emit("".join(h))

    def ol(self, items):
        self._emit("<ol>" + "".join(f"<li>{self.refs(md(x))}</li>" for x in items) + "</ol>")

    def raw(self, s):
        self._emit(s)

    def _flush(self):
        if self.pending:
            self.out.append("".join(self.pending))
            self.pending = []

    # ---- cross references: {fig:name} {tab:name} {sec:name} resolved at the end ------
    def refs(self, s):
        return s

    def resolve(self, html):
        def rep(m):
            key = m.group(1)
            if key not in self.labels:
                raise KeyError(f"unknown reference {key}")
            text, hid = self.labels[key]
            return f'<a href="#{hid}">{text}</a>'
        return re.sub(r"\{ref:([\w-]+)\}", rep, html)

    # ---- captioned blocks ------------------------------------------------------------
    def figure(self, caption, svg, label=None):
        self.fig += 1
        hid = f"fig{self.fig}"
        if label:
            self.labels[label] = (f"Figure {self.fig}", hid)
        self._emit(f'<div class="blk fig" id="{hid}"><div class="cap"><b>Figure {self.fig}.</b>'
                        f'{md(caption)}</div><div class="body">{svg}</div></div>')

    def table(self, caption, header, rows, label=None, mono=(), widths=None, small=False):
        self.tab += 1
        hid = f"tab{self.tab}"
        if label:
            self.labels[label] = (f"Table {self.tab}", hid)
        cg = ""
        if widths:
            cg = "<colgroup>" + "".join(f'<col style="width:{w}%"/>' for w in widths) + "</colgroup>"
        th = "".join(f"<th>{md(h)}</th>" for h in header)
        body = []
        for r in rows:
            tds = []
            for i, c in enumerate(r):
                cls = ' class="mono"' if i in mono else ""
                tds.append(f"<td{cls}>{self.refs(md(str(c)))}</td>")
            body.append("<tr>" + "".join(tds) + "</tr>")
        sm = " small" if small else ""
        self._emit(f'<div class="blk tbl{sm}" id="{hid}"><div class="cap"><b>Table {self.tab}.</b>'
                        f'{md(caption)}</div><div class="body"><table>{cg}<thead><tr>{th}</tr></thead>'
                        f'<tbody>{"".join(body)}</tbody></table></div></div>')

    def note(self, *paras, kind="NOTE"):
        icon = NOTE_ICON if kind == "NOTE" else IMP_ICON
        cls = "note" if kind == "NOTE" else "important"
        body = "".join(f"<p>{self.refs(md(s))}</p>" for s in paras)
        self._emit(f'<div class="blk adm {cls}"><div class="cap"><span class="lbl">{icon}{kind}</span>'
                        f'</div><div class="body">{body}</div></div>')

    def listing(self, source, code, first_line=1, lang="c"):
        lines = code.strip("\n").split("\n")
        last = first_line + len(lines) - 1
        out = []
        for i, ln in enumerate(lines):
            h = escape(ln)
            if lang in ("c", "asm"):
                h = re.sub(r"(//.*)$", r'<span class="cm">\1</span>', h)
            elif lang == "py":
                h = re.sub(r"(#.*)$", r'<span class="cm">\1</span>', h)
            elif lang == "tcl":
                h = re.sub(r"^(\s*#.*)$", r'<span class="cm">\1</span>', h)
            out.append(f'<span class="ln">{first_line + i}</span>{h}')
        self._emit(f'<div class="listing"><div class="src">Source: <a>{escape(source)}</a> '
                        f'Lines {first_line} - {last}</div><pre>' + "\n".join(out) + "</pre></div>")

    # ---- output ------------------------------------------------------------------------
    def toc_html(self):
        h = ['<ul class="toc">']
        for kind, hid, text in self.toc:
            h.append(f'<li class="{kind}"><a href="#{hid}">{escape(text)}</a></li>')
        h.append("</ul>")
        return "".join(h)
