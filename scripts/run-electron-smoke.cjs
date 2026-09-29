const { spawn } = require("node:child_process");
const path = require("node:path");
const electron = require("electron");

const projectRoot = path.resolve(__dirname, "..");
const environment = {
  ...process.env,
  FLOOR_PLANNER_SMOKE_TEST: path.join(projectRoot, "tests-js", "fixtures", "five-page-floor-plan.pdf"),
  FLOOR_PLANNER_SMOKE_SCREENSHOT: path.join(projectRoot, "tmp", "electron-smoke.png"),
};
delete environment.ELECTRON_RUN_AS_NODE;

const child = spawn(electron, [projectRoot], {
  cwd: projectRoot,
  env: environment,
  stdio: "inherit",
  windowsHide: true,
});
const timeout = setTimeout(() => {
  console.error("Electron smoke test timed out after 90 seconds.");
  child.kill();
  process.exitCode = 1;
}, 90_000);

child.once("error", (error) => {
  clearTimeout(timeout);
  console.error(error);
  process.exitCode = 1;
});

child.once("exit", (code, signal) => {
  clearTimeout(timeout);
  if (signal) console.error(`Electron smoke test exited with ${signal}.`);
  process.exitCode = code ?? 1;
});
