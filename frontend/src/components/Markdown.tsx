import { useEffect, useRef } from "react";
import { marked } from "marked";
import katex from "katex";

marked.setOptions({ breaks: true, gfm: true });

// CommonMark won't close `**情绪：**与…`: a closing `**` after punctuation must be
// followed by a space or punctuation, which Chinese text never has. Take a plain
// `**…**` run as bold first, whatever surrounds it (`__` stays standard: it
// appears inside identifiers).
const STRONG = /^\*\*(?!\s)([^\n]*?[^\s*\\])\*\*/;
marked.use({
  extensions: [{
    name: "cjkStrong",
    level: "inline",
    start(src: string) {
      const i = src.indexOf("**");
      return i < 0 ? undefined : i;
    },
    tokenizer(this: any, src: string) {
      const m = STRONG.exec(src);
      if (!m) return undefined;
      return { type: "strong", raw: m[0], text: m[1], tokens: this.lexer.inlineTokens(m[1]) };
    },
  }],
});

const BLOCKED_TAGS = new Set(["SCRIPT", "IFRAME", "OBJECT", "EMBED", "STYLE", "LINK", "META", "BASE", "FORM"]);
const UNSAFE_URL = /^\s*(?:javascript|vbscript|data\s*:\s*text\/html)/i;

function sanitizeHtml(html: string): string {
  if (typeof DOMParser === "undefined") return html;
  const doc = new DOMParser().parseFromString(html, "text/html");
  for (const el of Array.from(doc.body.querySelectorAll("*"))) {
    if (BLOCKED_TAGS.has(el.tagName)) {
      el.remove();
      continue;
    }
    for (const attr of Array.from(el.attributes)) {
      const name = attr.name.toLowerCase();
      if (name.startsWith("on") || name === "srcdoc") {
        el.removeAttribute(attr.name);
      } else if ((name === "href" || name === "src" || name === "xlink:href" || name === "action") && UNSAFE_URL.test(attr.value)) {
        el.removeAttribute(attr.name);
      }
    }
  }
  return doc.body.innerHTML;
}

// Render math BEFORE markdown: marked would otherwise mangle LaTeX (underscores
// become <em>, backslashes get altered), leaving raw $$...$$ in the output. We
// mask code blocks/spans first so shell variables like `$HOME` inside code are
// untouched, then render math with KaTeX, run marked, sanitize HTML, and splice
// rendered KaTeX back in.
function renderWithMath(text: string): string {
  const codeStore: string[] = [];
  const mathStore: string[] = [];
  const stashCode = (raw: string) => {
    codeStore.push(raw);
    return `%%CODE${codeStore.length - 1}%%`;
  };
  const stashMath = (tex: string, display: boolean) => {
    let html: string;
    try {
      html = katex.renderToString(tex.trim(), { displayMode: display, throwOnError: false });
    } catch {
      html = display ? `$$${tex}$$` : `$${tex}$`;
    }
    mathStore.push(html);
    return `%%KTX${mathStore.length - 1}%%`;
  };

  let s = text;
  // Preserve fenced code blocks and inline code spans before math extraction.
  s = s.replace(/(^|\n)[ \t]*(```|~~~)[^\n]*\n[\s\S]*?(?:\n[ \t]*\2[ \t]*(?=\n|$)|$)/g, (m) => stashCode(m));
  s = s.replace(/(`+)([^\n`]|(?<!`)\n(?!`))+?\1/g, (m) => stashCode(m));

  s = s.replace(/\$\$([\s\S]+?)\$\$/g, (_m, tex) => stashMath(tex, true)); // $$ ... $$
  s = s.replace(/\\\[([\s\S]+?)\\\]/g, (_m, tex) => stashMath(tex, true)); // \[ ... \]
  s = s.replace(/\\\(([\s\S]+?)\\\)/g, (_m, tex) => stashMath(tex, false)); // \( ... \)
  s = s.replace(/\$([^$\n]+?)\$/g, (_m, tex) => stashMath(tex, false)); // $ ... $

  s = s.replace(/%%CODE(\d+)%%/g, (_m, i) => codeStore[Number(i)] ?? "");
  let html = sanitizeHtml(marked.parse(s) as string);
  html = html.replace(/%%KTX(\d+)%%/g, (_m, i) => mathStore[Number(i)] ?? "");
  return html;
}

export function Markdown({ text }: { text: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    try {
      ref.current.innerHTML = renderWithMath(text || "");
    } catch {
      ref.current.textContent = text || "";
    }
  }, [text]);
  return <div className="markdown" ref={ref} />;
}
