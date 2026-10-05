// Build the offline bundle before invoking the checked-in Gradle wrapper.
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
// Resolve a relocatable Python installation before Chaquopy creates its venv.
// A home pointing at ~/.local/bin can lose the standalone interpreter's stdlib.
if (!process.env.MMG_BUILD_PYTHON) {
  const probe = spawnSync('python3.11', ['-c', 'import os, sys; print(os.path.realpath(sys.executable))'], { encoding: 'utf8' });
  if (probe.status === 0) process.env.MMG_BUILD_PYTHON = probe.stdout.trim();
}
if (Number(process.versions.node.split('.')[0]) < 22) {
  console.error('Android 构建需要 Node.js 22 或更高版本。'); process.exit(1);
}
function run(command, args, cwd) {
  const result = spawnSync(command, args, { cwd, stdio: 'inherit', env: process.env });
  if (result.error) { console.error(result.error.message); process.exit(1); }
  if (result.status !== 0) process.exit(result.status || 1);
}
run(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['run', 'android:sync'], path.join(root, 'frontend'));
run(process.platform === 'win32' ? 'gradlew.bat' : './gradlew', [':app:assembleDebug', '--console=plain'], path.join(root, 'frontend/android'));
run(process.platform === 'win32' ? 'python' : 'python3', ['scripts/audit-android-apk.py', 'frontend/android/app/build/outputs/apk/debug/app-debug.apk'], root);
console.log('APK: frontend/android/app/build/outputs/apk/debug/app-debug.apk');
