import { cpSync, mkdirSync, rmSync } from "node:fs";
import { resolve } from "node:path";
import { spawnSync } from "node:child_process";

const root = resolve(import.meta.dirname, "..");
const dist = resolve(root, "dist");

rmSync(dist, { force: true, recursive: true });

const tsc = spawnSync("tsc", ["-p", "tsconfig.json"], {
  cwd: root,
  stdio: "inherit",
  shell: process.platform === "win32",
});

if (tsc.status !== 0) {
  process.exit(tsc.status ?? 1);
}

mkdirSync(dist, { recursive: true });
cpSync(resolve(root, "src", "harbor.css"), resolve(dist, "harbor.css"));
cpSync(resolve(root, "tokens.json"), resolve(dist, "tokens.json"));
