/* Runs checker/check.py in the browser with Pyodide. The uploaded files are written to a temporary
   in-memory folder; nothing is sent anywhere or saved to the repository. */
const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.28.3/full/";
importScripts(PYODIDE + "pyodide.js");
const post = (type, data) => self.postMessage({ type, ...data });
let py = null, ready = null;

async function setup(base) {
  post("status", { text: "Starting Python in the browser…" });
  py = await loadPyodide({ stdout: s => post("log", { text: s }), stderr: s => post("log", { text: s }) });
  post("status", { text: "Installing packages (first time only takes a little longer)…" });
  await py.loadPackage(["numpy", "pandas", "scipy", "scikit-learn", "regex", "lxml", "nltk", "six", "micropip"]);
  const micropip = py.pyimport("micropip");
  await micropip.install(["krippendorff", "sacrebleu==2.6.0", "absl-py"]);
  post("status", { text: "Downloading the checker and the frozen thesis reference data…" });
  const sums = await (await fetch(base + "reference.sha256", { cache: "no-store" })).text();
  const refFiles = sums.trim().split("\n").map(l => l.split(/\s+/)[1].replace(/^\.\//, ""));
  const VENDOR = ["__init__.py", "rouge_scorer.py", "scoring.py", "tokenize.py", "tokenizers.py"];
  const files = [["checker/check.py"], ["checker/rules.py"], ["reference.sha256"], ...refFiles.map(f => ["reference/" + f]),
    ...VENDOR.map(f => ["site/vendor/rouge_score/" + f])];
  const mk = p => { let cur = ""; for (const s of p.split("/").slice(0, -1)) { if (!s) continue; cur += "/" + s; try { py.FS.mkdir(cur); } catch (_) {} } };
  await Promise.all(files.map(async ([f]) => {
    const r = await fetch(base + f, { cache: "no-store" }); if (!r.ok) throw new Error("Could not download " + f);
    const p = "/sb/" + f; mk(p); py.FS.writeFile(p, new Uint8Array(await r.arrayBuffer()));
  }));
  py.FS.mkdir("/sb/submissions");
  // sacrebleu imports portalocker, which needs the POSIX fcntl module; browsers have no file locking,
  // so a no-op stand-in is provided (the checker never locks files).
  py.FS.mkdir("/sb/shim");
  py.FS.writeFile("/sb/shim/fcntl.py", "LOCK_SH, LOCK_EX, LOCK_NB, LOCK_UN = 1, 2, 4, 8\ndef flock(fd, op): pass\ndef lockf(fd, op, *a): pass\n");
  await py.runPythonAsync(`import sys, os, warnings\nwarnings.filterwarnings("ignore")\nsys.path.insert(0, "/sb/checker"); sys.path.insert(0, "/sb/site/vendor"); sys.path.insert(0, "/sb/shim")\nos.chdir("/sb")\nimport check`);
}

async function runCheck(base, uploads, name) {
  if (!ready) ready = setup(base);
  await ready;
  post("status", { text: "Checking " + name + "…" });
  const dir = "/sb/submissions/" + name;
  py.runPython(`import shutil, os\nshutil.rmtree(${JSON.stringify(dir)}, ignore_errors=True)\nos.makedirs(${JSON.stringify(dir + "/images")})`);
  for (const u of uploads) py.FS.writeFile(dir + "/" + u.path, u.data);
  const res = await py.runPythonAsync(`
import json
rep = check.check_folder(${JSON.stringify(dir)})
json.dumps({"fails": rep.fails, "warns": rep.warns})
`);
  const report = py.FS.readFile(dir + "/REPORT.md", { encoding: "utf8" });
  const rjson = py.FS.readFile(dir + "/report.json", { encoding: "utf8" });
  post("done", { report, rjson, ...JSON.parse(res) });
}

self.onmessage = e => {
  const m = e.data;
  if (m.cmd === "check") runCheck(m.base, m.uploads, m.name).catch(err => post("error", { text: String(err && err.message || err) }));
};
