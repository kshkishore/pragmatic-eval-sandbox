const BASE = new URL(".", location.href).href;
const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
let uploads = [], worker = null, label = "upload";
const KINDS = { items: "New test items", replies: "Chatbot replies", judge: "Judge scores", image: "Chart image" };

function guessKind(name, text) {
  const n = name.toLowerCase();
  if (/\.(png|jpe?g)$/.test(n)) return "image";
  for (const k of ["items", "replies", "judge"]) if (n.includes(k)) return k;
  const head = (text || "").slice(0, 2000).toLowerCase();
  if (head.includes('"candidates"') || head.includes('"costar"') || /(^|,)objective(,|$)/m.test(head)) return "items";
  if (head.includes('"output"') || /(^|,)output(,|$)/m.test(head)) return "replies";
  if (head.includes('"cand"') || /(^|,)cand(,|$)/m.test(head)) return "judge";
  return "items";
}
function canonical(u) {
  if (u.kind === "image") return "images/" + u.name;
  const ext = u.name.toLowerCase().endsWith(".csv") ? ".csv" : u.name.toLowerCase().endsWith(".jsonl") ? ".jsonl" : ".json";
  return u.kind + ext;
}
function renderFiles() {
  $("#filelist").innerHTML = uploads.map((u, i) => `<li>${esc(u.name)} <select data-i="${i}" class="kind">${Object.entries(KINDS).map(([k, v]) => `<option value="${k}" ${k === u.kind ? "selected" : ""}>${v}</option>`).join("")}</select> <button data-rm="${i}" class="kind">remove</button></li>`).join("");
  document.querySelectorAll("#filelist select").forEach(s => s.onchange = () => { uploads[s.dataset.i].kind = s.value; });
  document.querySelectorAll("#filelist [data-rm]").forEach(b => b.onclick = () => { uploads.splice(+b.dataset.rm, 1); renderFiles(); });
  $("#go").disabled = !uploads.some(u => u.kind !== "image");
}
async function addFiles(list) {
  for (const f of list) {
    const data = new Uint8Array(await f.arrayBuffer());
    const text = /\.(png|jpe?g)$/i.test(f.name) ? "" : new TextDecoder().decode(data.slice(0, 4000));
    uploads.push({ name: f.name, data, kind: guessKind(f.name, text) });
  }
  label = "upload"; renderFiles();
}
$("#files").onchange = e => addFiles(e.target.files);
const drop = $("#drop");
drop.ondragover = e => { e.preventDefault(); drop.classList.add("over"); };
drop.ondragleave = () => drop.classList.remove("over");
drop.ondrop = e => { e.preventDefault(); drop.classList.remove("over"); addFiles(e.dataTransfer.files); };

const EX = { example_items: ["items.json"], example_replies: ["replies.csv"], example_judge: ["judge.csv"] };
document.querySelectorAll("[data-ex]").forEach(b => b.onclick = async () => {
  uploads = [];
  for (const f of EX[b.dataset.ex]) {
    const data = new Uint8Array(await (await fetch(BASE + "submissions/" + b.dataset.ex + "/" + f)).arrayBuffer());
    uploads.push({ name: f, data, kind: guessKind(f, "") });
  }
  label = b.dataset.ex; renderFiles();
});

function md(text) {
  const lines = text.split("\n"); let html = "", i = 0;
  const inline = s => esc(s).replace(/\*\*(PASS|FAIL|WARN)\*\*/g, '<span class="tag $1">$1</span>').replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`([^`]+)`/g, "<code>$1</code>");
  while (i < lines.length) {
    const l = lines[i];
    if (l.startsWith("|")) {
      const rows = []; while (i < lines.length && lines[i].startsWith("|")) { if (!/^\|(-{3}\|)+$/.test(lines[i])) rows.push(lines[i].slice(1, -1).split("|").map(c => c.trim())); i++; }
      const [h, ...b] = rows; html += `<div class="scroll"><table><thead><tr>${h.map(c => `<th>${inline(c)}</th>`).join("")}</tr></thead><tbody>${b.map(r => `<tr>${r.map(c => `<td>${inline(c)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`; continue;
    }
    if (l.startsWith("- ")) { html += "<ul>"; while (i < lines.length && lines[i].startsWith("- ")) { html += `<li>${inline(lines[i].slice(2))}</li>`; i++; } html += "</ul>"; continue; }
    const m = l.match(/^(#{1,3}) (.*)/);
    if (m) html += `<h${m[1].length}>${inline(m[2])}</h${m[1].length}>`; else if (l.trim()) html += `<p>${inline(l)}</p>`;
    i++;
  }
  return html;
}

$("#go").onclick = () => {
  $("#go").disabled = true; $("#out").innerHTML = "";
  if (!worker) {
    worker = new Worker("site/worker.js");
    worker.onmessage = e => {
      const m = e.data;
      if (m.type === "status") $("#status").textContent = m.text;
      if (m.type === "log") { const p = $("#log"); p.textContent += m.text + "\n"; }
      if (m.type === "done") {
        $("#status").textContent = m.fails ? `Finished: ${m.fails} check(s) failed, ${m.warns} warning(s).` : `Finished: all checks passed${m.warns ? `, ${m.warns} warning(s)` : ""}.`;
        const a = URL.createObjectURL(new Blob([m.report], { type: "text/markdown" })), j = URL.createObjectURL(new Blob([m.rjson], { type: "application/json" }));
        $("#out").innerHTML = `<div class="verdict ${m.fails ? "bad" : "ok"}"><b>${m.fails ? "Some checks failed." : "Your data passed the checks."}</b> The full report is below. <a href="${a}" download="REPORT.md">Download REPORT.md</a> · <a href="${j}" download="report.json">report.json</a></div><div class="report">${md(m.report)}</div>`;
        $("#go").disabled = false;
      }
      if (m.type === "error") { $("#status").textContent = ""; $("#out").innerHTML = `<div class="verdict bad"><b>The check could not finish:</b> ${esc(m.text)}</div>`; $("#go").disabled = false; }
    };
  }
  const files = uploads.map(u => ({ path: canonical(u), data: u.data }));
  worker.postMessage({ cmd: "check", base: BASE, uploads: files, name: label });
};
