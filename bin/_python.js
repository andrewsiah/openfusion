// Locate a Python >= 3.11 and run the bundled openfusion module with it.
// The package is pure Python with zero dependencies, so no venv/uv/pip is needed.
"use strict";
const { spawnSync } = require("node:child_process");
const path = require("node:path");

const SRC = path.resolve(__dirname, "..", "src");

function pythonOk(cmd) {
  const r = spawnSync(cmd, ["-c", "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"], { stdio: "ignore" });
  return r.status === 0;
}

function findPython() {
  const candidates = [process.env.FUSION_PYTHON, "python3.13", "python3.12", "python3.11", "python3", "python"].filter(Boolean);
  for (const c of candidates) if (pythonOk(c)) return c;
  process.stderr.write("openfusion: no Python >= 3.11 found on PATH. Install one (e.g. `uv python install 3.12`, brew, apt) or set FUSION_PYTHON=/path/to/python3.\n");
  process.exit(127);
}

module.exports = function run(moduleName) {
  const py = findPython();
  const env = { ...process.env, PYTHONPATH: process.env.PYTHONPATH ? `${SRC}${path.delimiter}${process.env.PYTHONPATH}` : SRC };
  const r = spawnSync(py, ["-m", moduleName, ...process.argv.slice(2)], { stdio: "inherit", env });
  process.exit(r.status === null ? 1 : r.status);
};
