/**
 * @file txtwrght settle primitives, installed as window.__txtwrght_settle.
 *
 * The JavaScript half of `Browser.settle()` in `txtwrght/browser.py`. Same
 * reason as actions.js for living in a file: MV3 will not evaluate source text
 * delivered over a wire, so anything the extension driver has to run must exist
 * as a loadable content script.
 *
 * Installing is a plain assignment, so re-evaluating this file is free and is
 * how a caller recovers the registry after a navigation replaced the document.
 * The entry is an arrow-function property rather than a method shorthand, so
 * Function.prototype.toString() yields the payload verbatim.
 */

;(() => {
  window.__txtwrght_settle = {
    /**
     * Resolve once the DOM has stopped changing for `cfg.quietMs`, or after
     * `cfg.capMs` regardless, with the milliseconds waited. A page that never
     * stops mutating is why the cap is not optional.
     */
    domQuiet: (cfg) => new Promise((resolve) => {
      let last = performance.now();
      const started = last;
      const observer = new MutationObserver(() => { last = performance.now(); });
      observer.observe(document.documentElement, {
        subtree: true, childList: true, attributes: true, characterData: true,
      });
      const tick = () => {
        const now = performance.now();
        if (now - last >= cfg.quietMs || now - started >= cfg.capMs) {
          observer.disconnect();
          resolve(Math.round(now - started));
        } else {
          setTimeout(tick, 25);
        }
      };
      setTimeout(tick, 25);
    }),
  }
})()
