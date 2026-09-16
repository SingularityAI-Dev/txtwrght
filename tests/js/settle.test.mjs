/**
 * @file Tests for `src/txtwrght/dom/settle.js`, the mutation-quiet wait that
 * `Browser.settle()` uses when networkidle has nothing useful to say.
 *
 * These are timing tests against real timers, so every bound is deliberately
 * loose: they assert the shape of the wait (quiet resolves early, a busy page
 * resolves at the cap) rather than a millisecond figure that a loaded machine
 * would make flaky.
 */

import assert from 'node:assert/strict'
import { describe, test } from 'node:test'

import { withPage } from './harness.mjs'

const QUIET = 60
const CAP = 2000

function settlePage(t, html = '<main>hello</main>') {
  const window = withPage(t, html, ['settle.js'])
  return { window, domQuiet: window.__txtwrght_settle.domQuiet }
}

/** Mutate the document until `stop()` is called. */
function churn(window, everyMs = 20) {
  const timer = window.setInterval(() => {
    window.document.body.appendChild(window.document.createElement('span'))
  }, everyMs)
  return () => window.clearInterval(timer)
}

describe('domQuiet', () => {
  test('resolves promptly on a document that is already still', async (t) => {
    const { domQuiet } = settlePage(t)

    const waited = await domQuiet({ quietMs: QUIET, capMs: CAP })

    assert.equal(typeof waited, 'number')
    assert.ok(waited >= QUIET, `waited ${waited}ms, expected at least ${QUIET}ms`)
    assert.ok(waited < CAP, `waited ${waited}ms, expected well under the ${CAP}ms cap`)
  })

  test('keeps waiting while the DOM is still being written to', async (t) => {
    // A client-rendered page reaches networkidle long before it stops
    // rendering. Resolving at the first idle moment is what this exists to stop.
    const { window, domQuiet } = settlePage(t)
    const stop = churn(window)
    window.setTimeout(stop, 400)

    const waited = await domQuiet({ quietMs: QUIET, capMs: CAP })

    assert.ok(waited >= 400, `waited ${waited}ms, expected to outlast 400ms of mutation`)
    assert.ok(waited < CAP, `waited ${waited}ms, expected to resolve before the cap`)
  })

  test('gives up at the cap on a document that never goes quiet', async (t) => {
    // Carousels, tickers and polling widgets mutate forever. Without the cap
    // every snapshot on such a page would hang for the full settle budget and
    // then some.
    const shortCap = 300
    const { window, domQuiet } = settlePage(t)
    const stop = churn(window)
    t.after(stop)

    const waited = await domQuiet({ quietMs: 100000, capMs: shortCap })

    assert.ok(waited >= shortCap, `waited ${waited}ms, expected to reach the ${shortCap}ms cap`)
    assert.ok(waited < shortCap * 4, `waited ${waited}ms, expected to stop near the cap`)
  })

  test('notices attribute changes, not just added nodes', async (t) => {
    // Frameworks that toggle classes or aria state without touching the tree
    // are still mid-render; the observer is configured for all four kinds.
    const { window, domQuiet } = settlePage(t, '<main id="app">hello</main>')
    const app = window.document.getElementById('app')
    let ticks = 0
    const timer = window.setInterval(() => {
      app.setAttribute('data-tick', String(++ticks))
    }, 20)
    window.setTimeout(() => window.clearInterval(timer), 400)

    const waited = await domQuiet({ quietMs: QUIET, capMs: CAP })

    assert.ok(waited >= 400, `waited ${waited}ms, expected attribute churn to extend the wait`)
  })

  test('notices text changes inside an existing node', async (t) => {
    const { window, domQuiet } = settlePage(t, '<main id="app">hello</main>')
    const app = window.document.getElementById('app')
    let ticks = 0
    const timer = window.setInterval(() => {
      app.firstChild.data = `hello ${++ticks}`
    }, 20)
    window.setTimeout(() => window.clearInterval(timer), 400)

    const waited = await domQuiet({ quietMs: QUIET, capMs: CAP })

    assert.ok(waited >= 400, `waited ${waited}ms, expected text churn to extend the wait`)
  })

  test('disconnects its observer before resolving', async (t) => {
    // settle() runs after every action for the life of the session. A leaked
    // observer per call would accumulate silently and slow the page down.
    const { window, domQuiet } = settlePage(t)
    let disconnects = 0
    const Real = window.MutationObserver
    window.MutationObserver = class extends Real {
      disconnect() {
        disconnects += 1
        return super.disconnect()
      }
    }
    t.after(() => {
      window.MutationObserver = Real
    })

    await domQuiet({ quietMs: QUIET, capMs: CAP })

    assert.equal(disconnects, 1)
  })

  test('disconnects its observer when it gives up at the cap too', async (t) => {
    const { window, domQuiet } = settlePage(t)
    let disconnects = 0
    const Real = window.MutationObserver
    window.MutationObserver = class extends Real {
      disconnect() {
        disconnects += 1
        return super.disconnect()
      }
    }
    const stop = churn(window, 10)
    t.after(() => {
      stop()
      window.MutationObserver = Real
    })

    await domQuiet({ quietMs: 100000, capMs: 300 })

    assert.equal(disconnects, 1)
  })
})
