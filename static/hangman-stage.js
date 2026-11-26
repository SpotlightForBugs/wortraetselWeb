/**
 * Hangman frame transitions.
 *
 * Consecutive miss frames are additive Illustrator exports (new filled brush
 * paths appear). Those new paths are stroked on with dashoffset, then filled.
 * Non-additive swaps (win / kill / theme) fade the whole drawing.
 */
(function (global) {
  let token = 0
  const cache = Object.create(null)

  function prefersReducedMotion () {
    return !!(
      window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    )
  }

  function ensureHost (stage, front) {
    let host = stage.querySelector('.hangman-stage-svg')
    if (!host) {
      host = document.createElement('div')
      host.className = 'hangman-stage-svg'
      host.setAttribute('aria-hidden', 'true')
      stage.appendChild(host)
    }
    stage.classList.add('has-inline-hangman')
    front.classList.add('hangman-image-base', 'is-svg-backed')
    return host
  }

  function parseSvg (text) {
    const doc = new DOMParser().parseFromString(text, 'image/svg+xml')
    const svg = doc.documentElement
    if (!svg || svg.nodeName.toLowerCase() !== 'svg' || doc.querySelector('parsererror')) {
      throw new Error('bad svg')
    }
    return document.importNode(svg, true)
  }

  function pathKeys (root) {
    return Array.prototype.map
      .call(root.querySelectorAll('path'), function (path) {
        return path.getAttribute('d') || ''
      })
      .filter(Boolean)
  }

  function isAdditive (oldKeys, newKeys) {
    if (!oldKeys.length) {
      return false
    }
    const seen = Object.create(null)
    newKeys.forEach(function (key) {
      seen[key] = true
    })
    for (let i = 0; i < oldKeys.length; i += 1) {
      if (!seen[oldKeys[i]]) {
        return false
      }
    }
    return newKeys.length >= oldKeys.length
  }

  function loadSvg (src) {
    if (cache[src]) {
      return Promise.resolve(cache[src])
    }
    return fetch(src, { credentials: 'same-origin' })
      .then(function (res) {
        if (!res.ok) {
          throw new Error('svg ' + res.status)
        }
        return res.text()
      })
      .then(function (text) {
        cache[src] = text
        return text
      })
  }

  function inkFor (path) {
    const cls = path.getAttribute('class') || ''
    const cs = window.getComputedStyle(path)
    const strokeOnly = cls.indexOf('st3') !== -1 || cs.fill === 'none'
    let ink = strokeOnly ? cs.stroke : cs.fill
    if (!ink || ink === 'none' || ink === 'rgba(0, 0, 0, 0)') {
      ink = strokeOnly ? '#000' : cs.color || '#000'
    }
    return { ink, strokeOnly, strokeWidth: cs.strokeWidth || '6px' }
  }

  function prepareDraw (path) {
    let len = 1
    try {
      len = Math.max(path.getTotalLength(), 1)
    } catch (err) {
      len = 400
    }
    const style = inkFor(path)
    path.style.stroke = style.ink
    path.style.strokeWidth = style.strokeOnly ? style.strokeWidth : '2.5px'
    path.style.strokeLinecap = 'round'
    path.style.strokeLinejoin = 'round'
    path.style.fillOpacity = '0'
    path.style.strokeDasharray = String(len)
    path.style.strokeDashoffset = String(len)
    path.style.transition = 'none'
    path.classList.add('is-drawing')
    return style.strokeOnly
  }

  function runDraw (paths, done) {
    if (!paths.length) {
      done()
      return
    }
    paths.forEach(function (path) {
      prepareDraw(path)
    })
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        paths.forEach(function (path) {
          const strokeOnly = (path.getAttribute('class') || '').indexOf('st3') !== -1
          path.style.transition =
            'stroke-dashoffset 0.58s ease-out, fill-opacity 0.22s ease ' +
            (strokeOnly ? '0.05s' : '0.42s') +
            ', stroke-opacity 0.2s ease 0.5s'
          path.style.strokeDashoffset = '0'
          path.style.fillOpacity = strokeOnly ? '0' : '1'
        })
      })
    })
    setTimeout(function () {
      paths.forEach(function (path) {
        path.classList.remove('is-drawing')
        path.style.strokeDasharray = ''
        path.style.strokeDashoffset = ''
        path.style.transition = ''
        // Keep intentional stroke paths; clear temporary brush outline strokes.
        if ((path.getAttribute('class') || '').indexOf('st3') === -1) {
          path.style.stroke = ''
          path.style.strokeWidth = ''
          path.style.strokeLinecap = ''
          path.style.strokeLinejoin = ''
          path.style.strokeOpacity = ''
        }
        path.style.fillOpacity = ''
      })
      done()
    }, 820)
  }

  function mountSvg (host, svg, oldKeys, animate) {
    let fresh = []
    if (animate && oldKeys && oldKeys.length) {
      const seen = Object.create(null)
      oldKeys.forEach(function (key) {
        seen[key] = true
      })
      Array.prototype.forEach.call(svg.querySelectorAll('path'), function (path) {
        const key = path.getAttribute('d') || ''
        if (key && seen[key]) {
          path.classList.add('is-settled')
        } else {
          fresh.push(path)
        }
      })
    } else if (animate) {
      fresh = Array.prototype.slice.call(svg.querySelectorAll('path'))
    }
    host.replaceChildren(svg)
    return fresh
  }

  function fadeSwap (host, svg, animatePaths, done) {
    host.classList.add('is-fading')
    setTimeout(function () {
      const fresh = mountSvg(host, svg, null, animatePaths)
      host.classList.remove('is-fading')
      if (animatePaths) {
        runDraw(fresh, done)
      } else {
        done()
      }
    }, 160)
  }

  function snapImg (front, src) {
    front.setAttribute('src', src)
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
    const current = front.getAttribute('data-hangman-src') || front.getAttribute('src') || ''
    if (current === src && stage && stage.querySelector('.hangman-stage-svg svg')) {
      return
    }
    if (!stage) {
      snapImg(front, src)
      return
    }

    const host = ensureHost(stage, front)
    token += 1
    const mine = token
    const immediate = opts.immediate || prefersReducedMotion()
    const oldSvg = host.querySelector('svg')
    const oldKeys = oldSvg ? pathKeys(oldSvg) : []

    function fail () {
      if (mine !== token) {
        return
      }
      host.replaceChildren()
      stage.classList.remove('has-inline-hangman')
      front.classList.remove('is-svg-backed')
      snapImg(front, src)
      front.removeAttribute('data-hangman-src')
    }

    function commit (srcDone) {
      if (mine !== token) {
        return
      }
      front.setAttribute('data-hangman-src', srcDone)
      snapImg(front, srcDone)
    }

    loadSvg(src)
      .then(function (text) {
        if (mine !== token) {
          return
        }
        const svg = parseSvg(text)
        const newKeys = pathKeys(svg)
        const additive = !immediate && isAdditive(oldKeys, newKeys)

        function done () {
          commit(src)
        }

        if (immediate || !oldSvg) {
          mountSvg(host, svg, null, false)
          done()
          return
        }

        if (additive) {
          const fresh = mountSvg(host, svg, oldKeys, true)
          runDraw(fresh, done)
          return
        }

        // Win / kill / language reset: soft fade, optionally draw the new art.
        fadeSwap(host, svg, newKeys.length > 0 && newKeys.length < 60, done)
      })
      .catch(fail)
  }

  global.HangmanStage = { setDrawing }
})(window)
