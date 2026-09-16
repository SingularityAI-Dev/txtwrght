/**
 * @file txtwrght element actions, installed as window.__txtwrght_actions.
 *
 * These are the JavaScript halves of the action verbs in `txtwrght/tools.py`.
 * They live in a file rather than in Python string constants because a Chrome
 * MV3 extension may not evaluate source text it received over a wire: the
 * extension driver can only run JavaScript a content script loaded from disk.
 * Keeping one copy here is what stops the Playwright driver and the extension
 * driver drifting apart.
 *
 * Every element these functions receive comes from
 * window.__txtwrght_selector_map, which extractor.js rebuilds on each snapshot.
 * Indices are only valid for the snapshot that produced them.
 *
 * Installing is a plain assignment, so re-evaluating this file is free and is
 * how a caller recovers the registry after a navigation replaced the document.
 * Every entry is an arrow-function property rather than a method shorthand, so
 * Function.prototype.toString() yields the payload verbatim and the refactor
 * that moved it here stays provable.
 */

;(() => {
  window.__txtwrght_actions = {
    /** The live element at `i` in the current snapshot, or undefined. */
    lookup: (i) => (window.__txtwrght_selector_map || {})[i],

    /** How many elements the current snapshot indexed. */
    selectorCount: () => Object.keys(window.__txtwrght_selector_map).length,

    /**
     * Is the element at `i` a password field? The agent asks before writing an
     * input_text action into the trace, so typed secrets get scrubbed. False
     * for a missing index, because an unknown element is not a licence to log.
     */
    isPasswordInput: (i) => ((window.__txtwrght_selector_map || {})[i] || {}).type === 'password',

    /**
     * Stable identity for an element, recorded in the trace at action time.
     *
     * Indices die with the snapshot; these attributes are what distillation
     * turns back into Playwright selectors long after the run. `frame_url` is
     * set only for elements reached through a same-origin iframe, since the
     * caller evaluates this in the main frame's context.
     */
    describe: (el) => {
      const attr = (n) => el.getAttribute(n) || undefined;
      const cssPath = (node) => {
        const parts = [];
        while (node && node.nodeType === 1 && parts.length < 8) {
          if (node.id) { parts.unshift('#' + CSS.escape(node.id)); break; }
          const tag = node.tagName.toLowerCase();
          const parent = node.parentElement;
          if (!parent) { parts.unshift(tag); break; }
          const sameTag = [...parent.children].filter((c) => c.tagName === node.tagName);
          parts.unshift(sameTag.length > 1
            ? tag + ':nth-of-type(' + (sameTag.indexOf(node) + 1) + ')'
            : tag);
          node = parent;
        }
        return parts.join(' > ');
      };
      return {
        tag: el.tagName.toLowerCase(),
        id: el.id || undefined,
        name: attr('name'),
        type: attr('type'),
        role: attr('role'),
        placeholder: attr('placeholder'),
        aria_label: attr('aria-label'),
        href: attr('href'),
        value_attr: attr('value'),
        text: (el.innerText || el.textContent || '').trim().slice(0, 80) || undefined,
        css: cssPath(el),
        frame_url: el.ownerDocument?.defaultView !== window
          ? el.ownerDocument?.location?.href
          : undefined,
      };
    },

    /**
     * Arm a one-shot capture listener that records whether a click was really
     * delivered to the element's document. Paired with clickSeen below.
     */
    watchClick: (el) => {
      const doc = el.ownerDocument;
      doc.__txtwrghtClickSeen = false;
      doc.addEventListener('click', () => { doc.__txtwrghtClickSeen = true; },
        { capture: true, once: true });
    },

    /** Did the listener armed by watchClick actually fire? */
    clickSeen: (el) => el.ownerDocument.__txtwrghtClickSeen === true,

    /** In-page click, the fallback when a synthesized click does not land. */
    click: (el) => el.click(),

    scrollElement: (el, args) => { el.scrollBy(0, args.sign * (args.pixels ?? el.clientHeight * args.numPages)) },

    scrollWindow: (args) => { window.scrollBy(0, args.sign * (args.pixels ?? window.innerHeight * args.numPages)) },

    scrollElementHorizontally: (el, args) => { el.scrollBy(args.sign * (args.pixels ?? el.clientWidth / 2), 0) },

    scrollWindowHorizontally: (args) => { window.scrollBy(args.sign * (args.pixels ?? window.innerWidth / 2), 0) },
  }
})()
