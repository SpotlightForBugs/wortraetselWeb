/**
 * Hangman frame transitions.
 *
 * Miss frames are additive Illustrator exports. Settled art stays put.
 * Stroke paths (head) draw with dashoffset along their own geometry.
 * Filled brush paths each wipe along that path's long axis, staggered so
 * the ink feels per-stroke rather than one fat slab.
 */
(function (global) {
  const SVG_NS = 'http://www.w3.org/2000/svg'
  const FILL_STROKE_MS = 380
  const FILL_STAGGER_MS = 26
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

  function pathBox (path) {
    try {
      const box = path.getBBox()
      if (!box.width && !box.height) {
        return null
      }
      return box
    } catch (err) {
      return null
    }
  }

  function unionBox (paths) {
    let minX = Infinity
    let minY = Infinity
    let maxX = -Infinity
    let maxY = -Infinity
    Array.prototype.forEach.call(paths, function (path) {
      const box = pathBox(path)
      if (!box) {
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
    paths.forEach(function (path, index) {
      let length = 1
      try {
        length = Math.max(path.getTotalLength(), 1)
      } catch (err) {
        length = 400
      }
      path.setAttribute('stroke-dasharray', String(length))
      path.setAttribute('stroke-dashoffset', String(length))
      setTimeout(function () {
        if (mine !== token) {
          return
        }
        animateDash(path, length, 0, 700, mine, function () {
          path.removeAttribute('stroke-dasharray')
          path.removeAttribute('stroke-dashoffset')
          remaining -= 1
          if (remaining <= 0) {
            done()
          }
        })
      }, index * 40)
    })
  }

  function sortPathsForStrokeDirection (paths) {
    const group = unionBox(paths)
    const vertical = !group || group.height >= group.width * 0.85
    return paths.slice().sort(function (a, b) {
      const ba = pathBox(a)
      const bb = pathBox(b)
      if (!ba || !bb) {
        return 0
      }
      if (vertical) {
        const dy = ba.y - bb.y
        if (Math.abs(dy) > 3) {
          return dy
        }
        return ba.x - bb.x
      }
      const dx = ba.x - bb.x
      if (Math.abs(dx) > 3) {
        return dx
      }
      return ba.y - bb.y
    })
  }

  /**
   * Wipe one filled brush path along its own long axis (stroke direction).
   */
  function paintOneFill (svg, path, index, mine, done) {
    const box = pathBox(path)
    const parent = path.parentNode
    if (!box || !parent) {
      path.style.visibility = ''
      done()
      return
    }

    const defs = ensureDefs(svg)
    const maskId = 'hangman-ink-mask-' + String(mine) + '-' + String(index)
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

    const wrap = document.createElementNS(SVG_NS, 'g')
    wrap.setAttribute('mask', 'url(#' + maskId + ')')
    wrap.classList.add('hangman-ink-wrap')
    parent.insertBefore(wrap, path)
    wrap.appendChild(path)
    // Reveal only after the mask is attached so unfinished strokes stay hidden.
    path.style.visibility = ''

    const vertical = box.height >= box.width * 0.9
    const cx = box.x + box.width / 2
    const cy = box.y + box.height / 2
    const brushWidth = Math.max((vertical ? box.width : box.height) * 1.4, 6)
    const pad = brushWidth * 0.4
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
    brush.setAttribute('stroke-width', String(brushWidth))

    let length = 1
    try {
      length = Math.max(brush.getTotalLength(), 1)
    } catch (err) {
      length = Math.max(vertical ? box.height : box.width, 1) + pad * 2
    }
    brush.setAttribute('stroke-dasharray', String(length))
    brush.setAttribute('stroke-dashoffset', String(length))

    animateDash(brush, length, 0, FILL_STROKE_MS, mine, function () {
      if (mine !== token) {
        return
      }
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
        const wrapParent = wrap.parentNode
        if (wrapParent) {
          while (wrap.firstChild) {
            wrapParent.insertBefore(wrap.firstChild, wrap)
          }
          wrap.remove()
        }
        mask.remove()
        done()
      })
    })
  }

  function wipeFillPaths (svg, paths, mine, done) {
    if (!paths.length) {
      done()
      return
    }

    const ordered = sortPathsForStrokeDirection(paths)
    let remaining = ordered.length
    ordered.forEach(function (path, index) {
      setTimeout(function () {
        if (mine !== token) {
          return
        }
        paintOneFill(svg, path, index, mine, function () {
          remaining -= 1
          if (remaining <= 0) {
            done()
          }
        })
      }, index * FILL_STAGGER_MS)
    })
  }

  /**
   * Mount the final frame immediately. Stroke parts draw along their path;
   * filled parts each wipe along their own stroke direction, staggered.
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
      // Fills stay hidden until each paintOneFill attaches its mask.
      wipeFillPaths(nextSvg, fills, mine, oneDone)
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
