/**
 * Crossfade hangman SVG frames inside a .stage.
 * Frames are separate Illustrator exports (one compound path each), so a
 * short opacity/settle transition is the practical way to animate between them.
 */
(function (global) {
  let token = 0

  function prefersReducedMotion () {
    return !!(
      window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    )
  }

  function ensureOverlay (stage, front) {
    let overlay = stage.querySelector('.hangman-image-overlay')
    if (overlay) {
      return overlay
    }
    overlay = document.createElement('img')
    overlay.className = 'hangman-image hangman-image-overlay'
    overlay.alt = ''
    overlay.setAttribute('aria-hidden', 'true')
    overlay.width = front.width || 640
    overlay.height = front.height || 480
    stage.classList.add('has-drawing-layers')
    stage.appendChild(overlay)
    return overlay
  }

  function snap (front, overlay, src) {
    front.setAttribute('src', src)
    if (!overlay) {
      return
    }
    overlay.classList.remove('is-shown')
    overlay.removeAttribute('src')
  }

  /**
   * @param {HTMLImageElement} front #drawing
   * @param {string} src next themed drawing URL
   * @param {{ immediate?: boolean }} [opts]
   */
  function setDrawing (front, src, opts) {
    opts = opts || {}
    if (!front || !src) {
      return
    }
    const stage = front.closest ? front.closest('.stage') : null
    const current = front.getAttribute('src') || ''
    if (current === src) {
      return
    }
    if (!stage) {
      front.setAttribute('src', src)
      return
    }

    const overlay = ensureOverlay(stage, front)
    token += 1
    const mine = token
    const immediate = opts.immediate || prefersReducedMotion() || !current

    overlay.onload = null
    overlay.onerror = null
    overlay.classList.remove('is-shown')

    if (immediate) {
      snap(front, overlay, src)
      return
    }

    function finish () {
      if (mine !== token) {
        return
      }
      front.setAttribute('src', src)
      overlay.classList.remove('is-shown')
      // Drop overlay payload after paint so the next miss starts clean.
      requestAnimationFrame(function () {
        if (mine === token) {
          overlay.removeAttribute('src')
        }
      })
    }

    let revealed = false
    function reveal () {
      if (mine !== token || revealed) {
        return
      }
      revealed = true
      void overlay.offsetWidth
      overlay.classList.add('is-shown')
      let settled = false
      function onEnd (event) {
        if (event && event.propertyName && event.propertyName !== 'opacity') {
          return
        }
        if (settled) {
          return
        }
        settled = true
        overlay.removeEventListener('transitionend', onEnd)
        finish()
      }
      overlay.addEventListener('transitionend', onEnd)
      setTimeout(onEnd, 450)
    }

    overlay.onload = function () {
      reveal()
    }
    overlay.onerror = function () {
      if (mine !== token) {
        return
      }
      snap(front, overlay, src)
    }
    overlay.setAttribute('src', src)
    if (overlay.complete && overlay.naturalWidth) {
      reveal()
    }
  }

  global.HangmanStage = { setDrawing }
})(window)
