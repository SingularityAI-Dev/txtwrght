/**
 * @file Loads the injected payloads from `src/txtwrght/dom/` into a happy-dom
 * window, so they can be tested without starting a browser.
 *
 * What this harness can and cannot prove:
 *
 * happy-dom implements events, MutationObserver, CSS.escape, shadow roots and
 * the DOM tree faithfully, so every payload that is event or attribute logic is
 * tested here in milliseconds. It has no layout engine: getBoundingClientRect,
 * offsetWidth and clientHeight are all zero, and there is no elementFromPoint.
 * extractor.js decides what is interactive from geometry and hit-testing, so it
 * cannot be tested here and stays on the Playwright suite in `tests/`, which is
 * the right tool for it. The one extractor test in this directory checks that
 * the file loads and installs, nothing more.
 */

import { readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { Window } from 'happy-dom'

const HERE = dirname(fileURLToPath(import.meta.url))

/**
 * Where the payloads are read from. Overridable so the negative control can run
 * this same suite against a deliberately broken copy and prove it goes red.
 */
export const PAYLOAD_DIR = process.env.TXTWRGHT_JS_DIR
  ? resolve(process.env.TXTWRGHT_JS_DIR)
  : resolve(HERE, '..', '..', 'src', 'txtwrght', 'dom')

/**
 * A window with `html` in its body and each named payload installed.
 *
 * Installation goes through window.eval rather than an import because that is
 * how both real drivers do it: Playwright evaluates the file's text, and an MV3
 * content script loads the same file into the page. Importing it as a module
 * would test a form of the payload that nothing ships.
 */
export function loadPage(html = '', payloads = ['actions.js'], { url } = {}) {
  const window = new Window({
    url: url ?? 'https://example.test/page',
    width: 1280,
    height: 720,
  })
  window.document.body.innerHTML = html
  for (const name of payloads) {
    window.eval(readFileSync(join(PAYLOAD_DIR, name), 'utf8'))
  }
  return window
}

/** Register a window for teardown on a node:test context. */
export function withPage(t, ...args) {
  const window = loadPage(...args)
  t.after(() => window.happyDOM.close())
  return window
}

/** The `window.__txtwrght_actions` registry of a freshly loaded page. */
export function withActions(t, html, options) {
  const window = withPage(t, html, ['actions.js'], options)
  return { window, actions: window.__txtwrght_actions, document: window.document }
}
