/**
 * Hangman frame transitions.
 *
 * Miss frames are additive Illustrator exports. Settled art stays mounted; only
 * newly added filled brush paths wipe in through a clip. Win/kill and other
 * non-additive swaps crossfade whole drawings — no outline racing.
 */
(function (global) {
  const SVG_NS = 'http://www.w3.org/2000/svg'
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
    if (
      !svg ||
      svg.nodeName.toLowerCase() !== 'svg' ||
      doc.querySelector('parsererror')
    ) {
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

  function keySet (keys) {
    const seen = Object.create(null)
    keys.forEach(function (key) {
      seen[key] = true
    })
    return seen
  }

  function isAdditive (oldKeys, newKeys) {
    if (!oldKeys.length) {
      return false
    }
    const seen = keySet(newKeys)
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

  function viewBoxOf (svg) {
    const raw = svg.getAttribute('viewBox')
    if (raw) {
      return raw
    }
    const w = svg.getAttribute('width') || '1728'
    const h = svg.getAttribute('height') || '1296'
    return '0 0 ' + w + ' ' + h
  }

  function unionBox (paths) {
    let minX = Infinity
    let minY = Infinity
    let maxX = -Infinity
    let maxY = -Infinity
    Array.prototype.forEach.call(paths, function (path) {
      let box
      try {
        box = path.getBBox()
      } catch (err) {
        return
      }
      if (!box.width && !box.height) {
        return
      }
      minX = Math.min(minX, box.x)
      minY = Math.min(minY, box.y)
      maxX = Math.max(maxX, box.x + box.width)
      maxY = Math.max(maxY, box.y + box.height)
    })
    if (!isFinite(minX)) {
      return null
    }
    return {
      x: minX,
      y: minY,
      width: Math.max(maxX - minX, 1),
      height: Math.max(maxY - minY, 1)
    }
  }

  function clearInkOverlay (host) {
    const overlay = host.querySelector('svg.hangman-ink-overlay')
    if (overlay) {
      overlay.remove()
    }
  }

  function mountBase (host, svg) {
    clearInkOverlay(host)
    svg.classList.add('hangman-base')
    const previous = host.querySelector('svg.hangman-base')
    if (previous) {
      previous.replaceWith(svg)
    } else {
      host.replaceChildren(svg)
    }
  }

  function crossfadeTo (host, svg, done) {
    clearInkOverlay(host)
    const current = host.querySelector('svg.hangman-base')
    svg.classList.add('hangman-base', 'hangman-fade-in')
    host.appendChild(svg)
    if (!current) {
      svg.classList.add('is-shown')
      done()
      return
    }
    current.classList.add('hangman-fade-out')
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        svg.classList.add('is-shown')
        current.classList.add('is-hidden')
      })
    })
    setTimeout(function () {
      if (current.parentNode === host) {
        current.remove()
      }
      svg.classList.remove('hangman-fade-in', 'is-shown')
      done()
    }, 420)
  }

  /**
   * Keep the settled drawing mounted. Wipe in clones of only the new paths,
   * then swap the base to the full next frame once the ink is visible.
   */
  function wipeInFresh (host, nextSvg, oldKeys, done) {
    const seen = keySet(oldKeys)
    const fresh = []
    Array.prototype.forEach.call(nextSvg.querySelectorAll('path'), function (path) {
      const key = path.getAttribute('d') || ''
      if (key && !seen[key]) {
        fresh.push(path)
      }
    })

    if (!fresh.length) {
      mountBase(host, nextSvg)
      done()
      return
    }

    clearInkOverlay(host)

    const overlay = document.createElementNS(SVG_NS, 'svg')
    overlay.classList.add('hangman-ink-overlay')
    overlay.setAttribute('viewBox', viewBoxOf(nextSvg))
    overlay.setAttribute('aria-hidden', 'true')

    const style = nextSvg.querySelector('style')
    if (style) {
      overlay.appendChild(style.cloneNode(true))
    }

    const defs = document.createElementNS(SVG_NS, 'defs')
    const clipId = 'hangman-ink-clip-' + String(token)
    const clip = document.createElementNS(SVG_NS, 'clipPath')
    clip.setAttribute('id', clipId)
    clip.setAttribute('clipPathUnits', 'userSpaceOnUse')
    defs.appendChild(clip)
    overlay.appendChild(defs)

    const layer = document.createElementNS(SVG_NS, 'g')
    layer.setAttribute('clip-path', 'url(#' + clipId + ')')
    fresh.forEach(function (path) {
      layer.appendChild(path.cloneNode(true))
    })
    overlay.appendChild(layer)
    host.appendChild(overlay)

    const box = unionBox(layer.querySelectorAll('path'))
    if (!box) {
      mountBase(host, nextSvg)
      done()
      return
    }

    const pad = Math.max(box.width, box.height) * 0.1
    const vertical = box.height >= box.width * 0.85
    const rect = document.createElementNS(SVG_NS, 'rect')
    const x = box.x - pad
    const y = box.y - pad
    const w = box.width + pad * 2
    const h = box.height + pad * 2
    rect.setAttribute('x', String(x))
    rect.setAttribute('y', String(y))
    if (vertical) {
      rect.setAttribute('width', String(w))
      rect.setAttribute('height', '0')
      rect.style.height = '0px'
    } else {
      rect.setAttribute('width', '0')
      rect.setAttribute('height', String(h))
      rect.style.width = '0px'
    }
    clip.appendChild(rect)

    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        if (vertical) {
          rect.style.transition =
            'height 0.65s cubic-bezier(0.22, 1, 0.36, 1)'
          rect.style.height = h + 'px'
          rect.setAttribute('height', String(h))
        } else {
          rect.style.transition =
            'width 0.65s cubic-bezier(0.22, 1, 0.36, 1)'
          rect.style.width = w + 'px'
          rect.setAttribute('width', String(w))
        }
      })
    })

    setTimeout(function () {
      mountBase(host, nextSvg)
      done()
    }, 700)
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
    const current =
      front.getAttribute('data-hangman-src') || front.getAttribute('src') || ''
    if (
      current === src &&
      stage &&
      stage.querySelector('.hangman-stage-svg svg.hangman-base')
    ) {
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
    const oldSvg = host.querySelector('svg.hangman-base')
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
        svg.setAttribute('viewBox', viewBoxOf(svg))
        const newKeys = pathKeys(svg)
        const additive = !immediate && isAdditive(oldKeys, newKeys)

        function done () {
          commit(src)
        }

        if (immediate || !oldSvg) {
          mountBase(host, svg)
          done()
          return
        }

        if (additive) {
          wipeInFresh(host, svg, oldKeys, done)
          return
        }

        crossfadeTo(host, svg, done)
      })
      .catch(fail)
  }

  global.HangmanStage = { setDrawing }
})(window)
