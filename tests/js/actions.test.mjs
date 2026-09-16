/**
 * @file Tests for `src/txtwrght/dom/actions.js`, the JavaScript half of the
 * action verbs in `txtwrght/tools.py`.
 */

import assert from 'node:assert/strict'
import { describe, test } from 'node:test'

import { withActions } from './harness.mjs'

/** Stand in for what a snapshot leaves behind; extractor.js needs a browser. */
function snapshot(window, elements) {
  window.__txtwrght_selector_map = Object.fromEntries(
    elements.map((el, i) => [i, el]),
  )
}

describe('lookup', () => {
  test('returns the element the snapshot indexed', (t) => {
    const { window, actions, document } = withActions(t, '<button id="go">Go</button>')
    snapshot(window, [document.getElementById('go')])

    assert.equal(actions.lookup(0), document.getElementById('go'))
  })

  test('returns undefined for an index the snapshot never issued', (t) => {
    const { window, actions, document } = withActions(t, '<button>Go</button>')
    snapshot(window, [document.querySelector('button')])

    assert.equal(actions.lookup(7), undefined)
  })

  test('returns undefined before any snapshot, rather than throwing', (t) => {
    // tools._element_handle turns undefined into a ToolError telling the caller
    // to snapshot again. A TypeError here would surface as an opaque crash.
    const { actions } = withActions(t, '<button>Go</button>')

    assert.equal(actions.lookup(0), undefined)
  })
})

describe('selectorCount', () => {
  test('counts what the current snapshot indexed', (t) => {
    const { window, actions, document } = withActions(
      t,
      '<a href="/a">a</a><a href="/b">b</a><a href="/c">c</a>',
    )
    snapshot(window, [...document.querySelectorAll('a')])

    assert.equal(actions.selectorCount(), 3)
  })
})

describe('isPasswordInput', () => {
  test('true for a password field', (t) => {
    const { window, actions, document } = withActions(
      t,
      '<input type="password" name="pw">',
    )
    snapshot(window, [document.querySelector('input')])

    assert.equal(actions.isPasswordInput(0), true)
  })

  test('false for a text field', (t) => {
    const { window, actions, document } = withActions(t, '<input type="text" name="u">')
    snapshot(window, [document.querySelector('input')])

    assert.equal(actions.isPasswordInput(0), false)
  })

  test('false for an index the snapshot never issued', (t) => {
    // Documents the current fail-open: the agent only scrubs a traced
    // input_text when this returns true, so an unresolvable index means the
    // typed text is recorded verbatim. Narrow in practice because the caller
    // asks immediately after acting on that same index.
    const { window, actions, document } = withActions(t, '<input type="password">')
    snapshot(window, [document.querySelector('input')])

    assert.equal(actions.isPasswordInput(99), false)
  })
})

describe('describe', () => {
  test('captures the identity attributes distillation rebuilds selectors from', (t) => {
    const { actions, document } = withActions(
      t,
      `<form><input id="user" name="username" type="email" role="textbox"
        placeholder="you@example.com" aria-label="Email address" value="seed"></form>`,
    )

    const described = actions.describe(document.getElementById('user'))

    assert.equal(described.tag, 'input')
    assert.equal(described.id, 'user')
    assert.equal(described.name, 'username')
    assert.equal(described.type, 'email')
    assert.equal(described.role, 'textbox')
    assert.equal(described.placeholder, 'you@example.com')
    assert.equal(described.aria_label, 'Email address')
    assert.equal(described.value_attr, 'seed')
  })

  test('leaves absent attributes undefined so Python drops them', (t) => {
    // describe_element filters on `is not None`; an empty string would survive
    // that filter and put a meaningless key into the trace.
    const { actions, document } = withActions(t, '<button id="b">Go</button>')

    const described = actions.describe(document.getElementById('b'))

    assert.equal(described.name, undefined)
    assert.equal(described.href, undefined)
    assert.equal(described.placeholder, undefined)
    assert.equal(described.aria_label, undefined)
  })

  test('trims text and caps it at 80 characters', (t) => {
    const long = 'x'.repeat(200)
    const { actions, document } = withActions(t, `<button>   ${long}   </button>`)

    const described = actions.describe(document.querySelector('button'))

    assert.equal(described.text.length, 80)
    assert.equal(described.text, 'x'.repeat(80))
  })

  test('omits text entirely when the element has none', (t) => {
    const { actions, document } = withActions(t, '<input type="text">')

    assert.equal(actions.describe(document.querySelector('input')).text, undefined)
  })

  test('stops the css path at the nearest id', (t) => {
    const { actions, document } = withActions(
      t,
      '<div><section id="panel"><p><span>deep</span></p></section></div>',
    )

    const { css } = actions.describe(document.querySelector('span'))

    assert.equal(css, '#panel > p > span')
  })

  test('escapes an id that would otherwise break the selector', (t) => {
    const { actions, document } = withActions(t, '<div id="a.b:c"><span>x</span></div>')

    const { css } = actions.describe(document.querySelector('span'))

    assert.equal(css, '#a\\.b\\:c > span')
  })

  test('disambiguates same-tag siblings with nth-of-type', (t) => {
    const { actions, document } = withActions(
      t,
      '<ul id="list"><li>one</li><li>two</li><li>three</li></ul>',
    )

    const { css } = actions.describe(document.querySelectorAll('li')[1])

    assert.equal(css, '#list > li:nth-of-type(2)')
  })

  test('omits nth-of-type for an only child of its tag', (t) => {
    const { actions, document } = withActions(
      t,
      '<ul id="list"><li>only</li><p>other</p></ul>',
    )

    assert.equal(actions.describe(document.querySelector('li')).css, '#list > li')
  })

  test('caps the css path at 8 segments', (t) => {
    const depth = 12
    const open = '<div>'.repeat(depth)
    const close = '</div>'.repeat(depth)
    const { actions, document } = withActions(t, `${open}<span>deep</span>${close}`)

    const { css } = actions.describe(document.querySelector('span'))

    assert.equal(css.split(' > ').length, 8)
    assert.ok(css.endsWith('span'))
  })

  test('records the frame url for an element reached through an iframe', async (t) => {
    // Indices come from one flat map built in the main frame, so a distilled
    // script has no other way to know the element it must rebuild lives in a
    // child document.
    //
    // Only the positive branch is provable here: happy-dom gives eval'd code a
    // global `window` that is not `document.defaultView`, so a main-frame
    // element looks cross-frame to this payload under the harness but not in a
    // browser. The negative branch is pinned by
    // test_hardening.test_describe_omits_frame_url_in_the_main_frame instead.
    const { window, actions } = withActions(
      t,
      '<iframe id="f" srcdoc="<button id=inner>In</button>"></iframe>',
    )
    await window.happyDOM.waitUntilComplete()
    const inner = window.document.getElementById('f').contentDocument.getElementById('inner')

    const described = actions.describe(inner)

    assert.equal(described.frame_url, 'about:srcdoc')
    assert.equal(described.id, 'inner')
  })
})

describe('click delivery verification', () => {
  test('clickSeen is false once watchClick has armed the listener', (t) => {
    const { actions, document } = withActions(t, '<button>Go</button>')
    const button = document.querySelector('button')

    actions.watchClick(button)

    assert.equal(actions.clickSeen(button), false)
  })

  test('clickSeen is false before watchClick has ever run', (t) => {
    const { actions, document } = withActions(t, '<button>Go</button>')

    assert.equal(actions.clickSeen(document.querySelector('button')), false)
  })

  test('a delivered click flips clickSeen to true', (t) => {
    const { actions, document } = withActions(t, '<button>Go</button>')
    const button = document.querySelector('button')

    actions.watchClick(button)
    button.click()

    assert.equal(actions.clickSeen(button), true)
  })

  test('the in-page click fallback is itself observed as delivered', (t) => {
    // The whole point of the fallback: when Playwright reports a click that the
    // browser dropped, tools.py dispatches this one instead. If it were not
    // observable the driver would still be guessing.
    const { actions, document } = withActions(t, '<button>Go</button>')
    const button = document.querySelector('button')

    actions.watchClick(button)
    actions.click(button)

    assert.equal(actions.clickSeen(button), true)
  })

  test('a handler calling stopPropagation cannot hide the click', (t) => {
    // watchClick listens in the capture phase precisely so a page that swallows
    // the event during bubbling does not make a real click look undelivered,
    // which would send tools.py into a redundant second dispatch.
    const { actions, document } = withActions(t, '<div><button>Go</button></div>')
    const button = document.querySelector('button')
    button.addEventListener('click', (event) => event.stopPropagation())

    actions.watchClick(button)
    button.click()

    assert.equal(actions.clickSeen(button), true)
  })

  test('re-arming resets the flag for the next action', (t) => {
    // Indices and state both die with the snapshot; a stale true would make the
    // next click look delivered no matter what happened.
    const { actions, document } = withActions(t, '<button>Go</button>')
    const button = document.querySelector('button')

    actions.watchClick(button)
    button.click()
    assert.equal(actions.clickSeen(button), true)

    actions.watchClick(button)

    assert.equal(actions.clickSeen(button), false)
  })

  test('a click elsewhere in the document still counts as seen', (t) => {
    // The listener is on the document, not the element, because the click the
    // browser delivers may land on a covering overlay rather than the target.
    const { actions, document } = withActions(
      t,
      '<button id="target">Go</button><span id="overlay">x</span>',
    )
    const target = document.getElementById('target')

    actions.watchClick(target)
    document.getElementById('overlay').click()

    assert.equal(actions.clickSeen(target), true)
  })
})

describe('scrolling', () => {
  /** Record the deltas a payload asks for instead of relying on layout. */
  function spy(target) {
    const calls = []
    target.scrollBy = (x, y) => calls.push([x, y])
    return calls
  }

  test('scrollWindow uses an explicit pixel count', (t) => {
    const { window, actions } = withActions(t, '')
    const calls = spy(window)

    actions.scrollWindow({ sign: 1, pixels: 250, numPages: 1 })

    assert.deepEqual(calls, [[0, 250]])
  })

  test('scrollWindow falls back to viewport heights when pixels is null', (t) => {
    // Python sends None for an unset pixel count, which arrives as null.
    const { window, actions } = withActions(t, '')
    const calls = spy(window)

    actions.scrollWindow({ sign: 1, pixels: null, numPages: 2 })

    assert.deepEqual(calls, [[0, window.innerHeight * 2]])
  })

  test('scrollWindow treats a pixel count of zero as zero, not a page', (t) => {
    // `??` rather than `||`: with `||` an explicit 0 would silently become a
    // full-page scroll, which is the opposite of what the caller asked for.
    const { window, actions } = withActions(t, '')
    const calls = spy(window)

    actions.scrollWindow({ sign: 1, pixels: 0, numPages: 1 })

    assert.deepEqual(calls, [[0, 0]])
  })

  test('scrollWindow scrolls up when the sign is negative', (t) => {
    const { window, actions } = withActions(t, '')
    const calls = spy(window)

    actions.scrollWindow({ sign: -1, pixels: 300, numPages: 1 })

    assert.deepEqual(calls, [[0, -300]])
  })

  test('scrollWindow handles a fractional page count', (t) => {
    const { window, actions } = withActions(t, '')
    const calls = spy(window)

    actions.scrollWindow({ sign: 1, pixels: null, numPages: 0.5 })

    assert.deepEqual(calls, [[0, window.innerHeight * 0.5]])
  })

  test('scrollElement scrolls the container by its own height', (t) => {
    const { actions, document } = withActions(t, '<div id="pane">content</div>')
    const pane = document.getElementById('pane')
    Object.defineProperty(pane, 'clientHeight', { value: 400 })
    const calls = spy(pane)

    actions.scrollElement(pane, { sign: 1, pixels: null, numPages: 1 })

    assert.deepEqual(calls, [[0, 400]])
  })

  test('scrollElement prefers an explicit pixel count over its height', (t) => {
    const { actions, document } = withActions(t, '<div id="pane">content</div>')
    const pane = document.getElementById('pane')
    Object.defineProperty(pane, 'clientHeight', { value: 400 })
    const calls = spy(pane)

    actions.scrollElement(pane, { sign: -1, pixels: 120, numPages: 3 })

    assert.deepEqual(calls, [[0, -120]])
  })

  test('scrollWindowHorizontally moves half a viewport width', (t) => {
    const { window, actions } = withActions(t, '')
    const calls = spy(window)

    actions.scrollWindowHorizontally({ sign: 1, pixels: null })

    assert.deepEqual(calls, [[window.innerWidth / 2, 0]])
  })

  test('scrollWindowHorizontally honours sign and explicit pixels', (t) => {
    const { window, actions } = withActions(t, '')
    const calls = spy(window)

    actions.scrollWindowHorizontally({ sign: -1, pixels: 90 })

    assert.deepEqual(calls, [[-90, 0]])
  })

  test('scrollElementHorizontally moves half the container width', (t) => {
    const { actions, document } = withActions(t, '<div id="strip">content</div>')
    const strip = document.getElementById('strip')
    Object.defineProperty(strip, 'clientWidth', { value: 600 })
    const calls = spy(strip)

    actions.scrollElementHorizontally(strip, { sign: 1, pixels: null })

    assert.deepEqual(calls, [[300, 0]])
  })
})
