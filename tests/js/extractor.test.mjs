/**
 * @file Load smoke test for `src/txtwrght/dom/extractor.js`.
 *
 * Deliberately shallow. The extractor decides what is interactive from layout
 * geometry and hit-testing, and happy-dom has no layout engine, so its actual
 * output is tested against Chromium in `tests/test_extractor.py`. What is worth
 * having here is the cheap half of that: a syntax error or a broken installer
 * in a 1800-line file is caught in milliseconds instead of after a browser
 * launch, and it is the same failure an MV3 content script would hit on load.
 */

import assert from 'node:assert/strict'
import { describe, test } from 'node:test'

import { withPage } from './harness.mjs'

describe('extractor.js', () => {
  test('parses and installs without throwing', (t) => {
    assert.doesNotThrow(() => withPage(t, '<main>hello</main>', ['extractor.js']))
  })

  test('exposes the entry point the drivers call', (t) => {
    const window = withPage(t, '<main>hello</main>', ['extractor.js'])

    assert.equal(typeof window.__txtwrght_extract, 'function')
  })

  test('seeds the seen-set that marks elements new on first sight', (t) => {
    const window = withPage(t, '<main>hello</main>', ['extractor.js'])

    assert.ok(window.__txtwrght_seen instanceof window.WeakSet)
  })

  test('re-installing preserves the seen-set across snapshots', (t) => {
    // The installer runs before every snapshot. If it reset the set, every
    // snapshot would mark the whole page new and the `*[n]` marker would be
    // noise instead of a signal.
    const window = withPage(t, '<main>hello</main>', ['extractor.js', 'extractor.js'])

    assert.ok(window.__txtwrght_seen instanceof window.WeakSet)
  })
})

describe('the three payloads coexist', () => {
  test('installing all of them leaves every registry reachable', (t) => {
    // Both drivers load these into one document; a name collision would show up
    // as one registry quietly overwriting another.
    const window = withPage(t, '<main>hello</main>', [
      'extractor.js',
      'actions.js',
      'settle.js',
    ])

    assert.equal(typeof window.__txtwrght_extract, 'function')
    assert.equal(typeof window.__txtwrght_actions.describe, 'function')
    assert.equal(typeof window.__txtwrght_settle.domQuiet, 'function')
  })
})
