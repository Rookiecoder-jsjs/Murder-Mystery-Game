const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

function mountLifecycle(pathname = '/game/saved', state) {
  const callbacks = new Map();
  const classes = new Set();
  const navigations = [];
  const window = new EventTarget();
  const document = new EventTarget();
  const viewport = new EventTarget();
  Object.assign(viewport, { height: 904, width: 407 });
  Object.assign(window, { visualViewport: viewport, innerHeight: 904, innerWidth: 407 });
  let overlay = null;
  document.querySelector = () => overlay;
  document.documentElement = { classList: {
    toggle: (name, enabled) => enabled ? classes.add(name) : classes.delete(name),
    remove: name => classes.delete(name),
  } };
  class Element {
    constructor(editing = false) { this.editing = editing; }
    matches() { return this.editing; }
    blur() { document.activeElement = new Element(); document.dispatchEvent(new Event('focusout')); }
  }
  document.activeElement = new Element();
  let cleanup;
  const context = { exports: {}, Event, KeyboardEvent: class extends Event {}, HTMLElement: Element,
    document, window, require: name => {
      if (name === 'react') return { useEffect: effect => { cleanup = effect(); } };
      if (name === 'react-router-dom') return { useLocation: () => ({ pathname, state }), useNavigate: () => value => navigations.push(value) };
      if (name === '../../utils/mobileLibrary') {
        const utility = { exports: {} };
        const src = fs.readFileSync(path.join(__dirname, '../src/utils/mobileLibrary.ts'), 'utf8');
        vm.runInNewContext(ts.transpileModule(src, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, utility);
        return utility.exports;
      }
      if (name === '@capacitor/app') return { App: { addListener: async (name, handler) => {
        callbacks.set(name, handler); return { remove: () => callbacks.delete(name) };
      }, exitApp: () => {} } };
      return { isAndroid: true };
    },
  };
  const source = fs.readFileSync(path.join(__dirname, '../src/components/common/MobileLifecycle.tsx'), 'utf8');
  vm.runInNewContext(ts.transpileModule(source, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
  }).outputText, context);
  context.exports.MobileLifecycle();
  return { window, document, classes, navigations,
    focus: () => { document.activeElement = new Element(true); document.dispatchEvent(new Event('focusin')); },
    resize: height => { viewport.height = height; viewport.dispatchEvent(new Event('resize')); },
    back: () => callbacks.get('backButton')(),
    overlay: value => { overlay = value; },
    cleanup: () => cleanup(),
  };
}

test('Android IME closes without blurring: the next back navigates immediately', () => {
  const app = mountLifecycle();
  app.focus(); app.resize(556);
  assert.ok(app.classes.has('native-keyboard-open'));
  // Android consumes the first back to close the IME, leaving the DOM input focused.
  app.resize(904);
  assert.ok(!app.classes.has('native-keyboard-open'));
  app.back();
  assert.deepEqual(app.navigations, ['/']);
  app.cleanup();
});

test('Android back returns from case details to the original library instead of skipping home', () => {
  const app = mountLifecycle('/library/case', { from: '/library' });
  app.back(); assert.deepEqual(app.navigations, ['/library']); app.cleanup();
  const personal = mountLifecycle('/library/personal', { from: '/my/stories' });
  personal.back(); assert.deepEqual(personal.navigations, ['/my/stories']); personal.cleanup();
});

test('visible keyboard and open overlays consume back before route navigation', () => {
  const app = mountLifecycle();
  app.focus(); app.resize(292);
  app.back();
  assert.deepEqual(app.navigations, []);
  app.resize(904);
  let escapes = 0;
  app.window.addEventListener('keydown', () => { escapes += 1; });
  app.overlay({}); app.back();
  assert.equal(escapes, 1);
  assert.deepEqual(app.navigations, []);
  app.overlay(null);
  const drawer = event => event.preventDefault();
  app.window.addEventListener('mystery:back', drawer); app.back();
  assert.deepEqual(app.navigations, []);
  app.window.removeEventListener('mystery:back', drawer); app.back();
  assert.deepEqual(app.navigations, ['/']);
  app.cleanup();
});
