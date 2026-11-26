/**
 * Hangman frame transitions.
 *
 * Miss frames are additive Illustrator exports. Settled art stays put. New
 * stroke paths (e.g. the head) draw with dashoffset. New filled brush paths
 * wipe in through an in-place user-unit brush mask — no end remount that
 * suddenly fattens the ink.
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

  function isStrokePath (path) {
    const cls = path.getAttribute('class') || ''
    return cls.indexOf('st3') !== -1
  }

  function easeOutCubic (t) {
    return 1 - Math.pow(1 - t, 3)
  }

  function animateDash (el, from, to, ms, mine, done) {
    const start = performance.now()
    function frame (now) {
      if (mine !== token) {
        return
      }
      const t = Math.min(1, (now - start) / ms)
      const value = from + (to - from) * easeOutCubic(t)
      el.setAttribute('stroke-dashoffset', String(value))
      if (t < 1) {
        requestAnimationFrame(frame)
      } else if (done) {
        done()
      }
    }
    requestAnimationFrame(frame)
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

  function ensureDefs (svg) {
    let defs = svg.querySelector('defs')
    if (!defs) {
      defs = document.createElementNS(SVG_NS, 'defs')
      svg.insertBefore(defs, svg.firstChild)
    }
    return defs
  }

  function drawStrokePaths (paths, mine, done) {
    if (!paths.length) {
      done()
      return
    }
    let remaining = paths.length
    paths.forEach(function (path) {
      let length = 1
      try {
        length = Math.max(path.getTotalLength(), 1)
      } catch (err) {
        length = 400
      }
      path.setAttribute('stroke-dasharray', String(length))
      path.setAttribute('stroke-dashoffset', String(length))
      animateDash(path, length, 0, 700, mine, function () {
        path.removeAttribute('stroke-dasharray')
        path.removeAttribute('stroke-dashoffset')
        remaining -= 1
        if (remaining <= 0) {
          done()
        }
      })
    })
  }

  function wipeFillPaths (svg, paths, mine, done) {
    if (!paths.length) {
      done()
      return
    }

    const box = unionBox(paths)
    if (!box) {
      done()
      return
    }

    const defs = ensureDefs(svg)
    const maskId = 'hangman-ink-mask-' + String(mine)
    const mask = document.createElementNS(SVG_NS, 'mask')
    mask.setAttribute('id', maskId)
    mask.setAttribute('maskUnits', 'userSpaceOnUse')
    mask.setAttribute('maskContentUnits', 'userSpaceOnUse')

    const vb = viewBoxOf(svg).split(/\s+/).map(Number)
    const hide = document.createElementNS(SVG_NS, 'rect')
    hide.setAttribute('x', String(vb[0] || 0))
    hide.setAttribute('y', String(vb[1] || 0))
    hide.setAttribute('width', String(vb[2] || 1728))
    hide.setAttribute('height', String(vb[3] || 1296))
    hide.setAttribute('fill', '#000')
    mask.appendChild(hide)

    const brush = document.createElementNS(SVG_NS, 'path')
    brush.setAttribute('fill', 'none')
    brush.setAttribute('stroke', '#fff')
    brush.setAttribute('stroke-linecap', 'round')
    brush.setAttribute('stroke-linejoin', 'round')
    mask.appendChild(brush)
    defs.appendChild(mask)

    // Cover every fresh fill path with the same mask while it lives in-tree.
    const masked = []
    paths.forEach(function (path) {
      const parent = path.parentNode
      if (!parent) {
        return
      }
      const wrap = document.createElementNS(SVG_NS, 'g')
      wrap.setAttribute('mask', 'url(#' + maskId + ')')
      wrap.classList.add('hangman-ink-wrap')
      parent.insertBefore(wrap, path)
      wrap.appendChild(path)
      masked.push(wrap)
    })

    const vertical = box.height >= box.width * 0.85
    const cx = box.x + box.width / 2
    const cy = box.y + box.height / 2
    // Slightly oversize so the final frame matches unmasked ink (no fattening snap).
    const brushWidth = (vertical ? box.width : box.height) * 1.35
    const pad = brushWidth * 0.45
    let d
    if (vertical) {
      d =
        'M ' +
        cx +
        ' ' +
        (box.y - pad) +
        ' L ' +
        cx +
        ' ' +
        (box.y + box.height + pad)
    } else {
      d =
        'M ' +
        (box.x - pad) +
        ' ' +
        cy +
        ' L ' +
        (box.x + box.width + pad) +
        ' ' +
        cy
    }
    brush.setAttribute('d', d)
    brush.setAttribute('stroke-width', String(Math.max(brushWidth, 8)))

    let length = 1
    try {
      length = Math.max(brush.getTotalLength(), 1)
    } catch (err) {
      length = Math.max(vertical ? box.height : box.width, 1) + pad * 2
    }
    brush.setAttribute('stroke-dasharray', String(length))
    brush.setAttribute('stroke-dashoffset', String(length))

    animateDash(brush, length, 0, 700, mine, function () {
      if (mine !== token) {
        return
      }
      // Finish fully covered, then unwrap in place — same pixels, no remount.
      const cover = document.createElementNS(SVG_NS, 'rect')
      cover.setAttribute('x', String(box.x - pad))
      cover.setAttribute('y', String(box.y - pad))
      cover.setAttribute('width', String(box.width + pad * 2))
      cover.setAttribute('height', String(box.height + pad * 2))
      cover.setAttribute('fill', '#fff')
      mask.appendChild(cover)

      requestAnimationFrame(function () {
        if (mine !== token) {
          return
        }
        masked.forEach(function (wrap) {
          const parent = wrap.parentNode
          if (!parent) {
            return
          }
          while (wrap.firstChild) {
            parent.insertBefore(wrap.firstChild, wrap)
          }
          wrap.remove()
        })
        mask.remove()
        done()
      })
    })
  }

  /**
   * Mount the final frame immediately. Stroke parts draw like the head;
   * filled parts wipe in-place so completion does not fatten the ink.
   */
  function wipeInFresh (host, nextSvg, oldKeys, mine, done) {
    const seen = keySet(oldKeys)
    const strokes = []
    const fills = []
    Array.prototype.forEach.call(
      nextSvg.querySelectorAll('path'),
      function (path) {
        const key = path.getAttribute('d') || ''
        if (!key || seen[key]) {
          return
        }
        if (isStrokePath(path)) {
          strokes.push(path)
        } else {
          fills.push(path)
        }
      }
    )

    if (!strokes.length && !fills.length) {
      mountBase(host, nextSvg)
      done()
      return
    }

    // Hide fresh fills until masked so the mount does not flash full ink.
    fills.forEach(function (path) {
      path.style.visibility = 'hidden'
    })
    strokes.forEach(function (path) {
      let length = 1
      try {
        length = Math.max(path.getTotalLength(), 1)
      } catch (err) {
        length = 400
      }
      path.setAttribute('stroke-dasharray', String(length))
      path.setAttribute('stroke-dashoffset', String(length))
    })

    mountBase(host, nextSvg)

    let pending = 0
    function oneDone () {
      pending -= 1
      if (pending <= 0) {
        done()
      }
    }

    if (strokes.length) {
      pending += 1
    }
    if (fills.length) {
      pending += 1
    }
    if (!pending) {
      done()
      return
    }

    if (strokes.length) {
      drawStrokePaths(strokes, mine, oneDone)
    }
    if (fills.length) {
      // Keep fills hidden until the mask wrap is attached, then reveal.
      wipeFillPaths(nextSvg, fills, mine, oneDone)
      fills.forEach(function (path) {
        path.style.visibility = ''
      })
    }
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
          wipeInFresh(host, svg, oldKeys, mine, done)
          return
        }

        crossfadeTo(host, svg, done)
      })
      .catch(fail)
  }

  global.HangmanStage = { setDrawing }
})(window)
