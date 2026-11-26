/* eslint-env browser */
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

  /** @returns {boolean} */
  function prefersReducedMotion () {
    return Boolean(
      window.matchMedia &&
        window.matchMedia('(prefers-reduced-motion: reduce)').matches
    )
  }

  /**
   * @param {HTMLElement} stage
   * @param {HTMLImageElement} front
   * @returns {HTMLElement}
   */
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

  /**
   * @param {string} text
   * @returns {SVGSVGElement}
   */
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

  /**
   * @param {Element} root
   * @returns {string[]}
   */
  function pathKeys (root) {
    return Array.prototype.map
      .call(root.querySelectorAll('path'), (path) => path.getAttribute('d') || '')
      .filter(Boolean)
  }

  /**
   * @param {string[]} keys
   * @returns {Object.<string, boolean>}
   */
  function keySet (keys) {
    const seen = Object.create(null)
    keys.forEach((key) => {
      seen[key] = true
    })
    return seen
  }

  /**
   * @param {string[]} oldKeys
   * @param {string[]} newKeys
   * @returns {boolean}
   */
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

  /**
   * @param {string} src
   * @returns {Promise<string>}
   */
  function loadSvg (src) {
    if (cache[src]) {
      return Promise.resolve(cache[src])
    }
    return fetch(src, { credentials: 'same-origin' })
      .then((res) => {
        if (!res.ok) {
          throw new Error(`svg ${res.status}`)
        }
        return res.text()
      })
      .then((text) => {
        cache[src] = text
        return text
      })
  }

  /**
   * @param {SVGSVGElement} svg
   * @returns {string}
   */
  function viewBoxOf (svg) {
    const raw = svg.getAttribute('viewBox')
    if (raw) {
      return raw
    }
    const width = svg.getAttribute('width') || '1728'
    const height = svg.getAttribute('height') || '1296'
    return `0 0 ${width} ${height}`
  }

  /**
   * @param {SVGPathElement} path
   * @returns {DOMRect|null}
   */
  function pathBox (path) {
    try {
      const box = path.getBBox()
      if (!box.width && !box.height) {
        return null
      }
      return box
    } catch {
      return null
    }
  }

  /**
   * @param {ArrayLike<SVGPathElement>} paths
   * @returns {{x: number, y: number, width: number, height: number}|null}
   */
  function unionBox (paths) {
    let minX = Infinity
    let minY = Infinity
    let maxX = -Infinity
    let maxY = -Infinity
    Array.prototype.forEach.call(paths, (path) => {
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

  /**
   * @param {SVGPathElement} path
   * @returns {boolean}
   */
  function isStrokePath (path) {
    const cls = path.getAttribute('class') || ''
    return cls.indexOf('st3') !== -1
  }

  /**
   * @param {number} progress
   * @returns {number}
   */
  function easeOutCubic (progress) {
    return 1 - Math.pow(1 - progress, 3)
  }

  /**
   * @param {Element} el
   * @param {number} from
   * @param {number} to
   * @param {number} ms
   * @param {number} mine
   * @param {Function} [done]
   */
  function animateDash (el, from, to, ms, mine, done) {
    const start = performance.now()
    /** @param {number} now */
    function frame (now) {
      if (mine !== token) {
        return
      }
      const progress = Math.min(1, (now - start) / ms)
      const value = from + (to - from) * easeOutCubic(progress)
      el.setAttribute('stroke-dashoffset', String(value))
      if (progress < 1) {
        requestAnimationFrame(frame)
      } else if (done) {
        done()
      }
    }
    requestAnimationFrame(frame)
  }

  /** @param {HTMLElement} host */
  function clearInkOverlay (host) {
    const overlay = host.querySelector('svg.hangman-ink-overlay')
    if (overlay) {
      overlay.remove()
    }
  }

  /**
   * @param {HTMLElement} host
   * @param {SVGSVGElement} svg
   */
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

  /**
   * @param {HTMLElement} host
   * @param {SVGSVGElement} svg
   * @param {Function} done
   */
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
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        svg.classList.add('is-shown')
        current.classList.add('is-hidden')
      })
    })
    setTimeout(() => {
      if (current.parentNode === host) {
        current.remove()
      }
      svg.classList.remove('hangman-fade-in', 'is-shown')
      done()
    }, 420)
  }

  /**
   * @param {SVGSVGElement} svg
   * @returns {SVGDefsElement}
   */
  function ensureDefs (svg) {
    let defs = svg.querySelector('defs')
    if (!defs) {
      defs = document.createElementNS(SVG_NS, 'defs')
      svg.insertBefore(defs, svg.firstChild)
    }
    return defs
  }

  /**
   * @param {SVGPathElement[]} paths
   * @param {number} mine
   * @param {Function} done
   */
  function drawStrokePaths (paths, mine, done) {
    if (!paths.length) {
      done()
      return
    }
    let remaining = paths.length
    paths.forEach((path, index) => {
      let length = 1
      try {
        length = Math.max(path.getTotalLength(), 1)
      } catch {
        length = 400
      }
      path.setAttribute('stroke-dasharray', String(length))
      path.setAttribute('stroke-dashoffset', String(length))
      setTimeout(() => {
        if (mine !== token) {
          return
        }
        animateDash(path, length, 0, 700, mine, () => {
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

  /**
   * @param {SVGPathElement[]} paths
   * @returns {SVGPathElement[]}
   */
  function sortPathsForStrokeDirection (paths) {
    const group = unionBox(paths)
    const vertical = !group || group.height >= group.width * 0.85
    return paths.slice().sort((pathA, pathB) => {
      const boxA = pathBox(pathA)
      const boxB = pathBox(pathB)
      if (!boxA || !boxB) {
        return 0
      }
      if (vertical) {
        const deltaY = boxA.y - boxB.y
        if (Math.abs(deltaY) > 3) {
          return deltaY
        }
        return boxA.x - boxB.x
      }
      const deltaX = boxA.x - boxB.x
      if (Math.abs(deltaX) > 3) {
        return deltaX
      }
      return boxA.y - boxB.y
    })
  }

  /**
   * Wipe one filled brush path along its own long axis (stroke direction).
   *
   * @param {SVGSVGElement} svg
   * @param {SVGPathElement} path
   * @param {number} index
   * @param {number} mine
   * @param {Function} done
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
    const maskId = `hangman-ink-mask-${String(mine)}-${String(index)}`
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
    wrap.setAttribute('mask', `url(#${maskId})`)
    wrap.classList.add('hangman-ink-wrap')
    parent.insertBefore(wrap, path)
    wrap.appendChild(path)
    // Reveal only after the mask is attached so unfinished strokes stay hidden.
    path.style.visibility = ''

    const vertical = box.height >= box.width * 0.9
    const centerX = box.x + box.width / 2
    const centerY = box.y + box.height / 2
    const brushWidth = Math.max((vertical ? box.width : box.height) * 1.4, 6)
    const pad = brushWidth * 0.4
    const brushPathD = vertical
      ? `M ${centerX} ${box.y - pad} L ${centerX} ${box.y + box.height + pad}`
      : `M ${box.x - pad} ${centerY} L ${box.x + box.width + pad} ${centerY}`
    brush.setAttribute('d', brushPathD)
    brush.setAttribute('stroke-width', String(brushWidth))

    let length = 1
    try {
      length = Math.max(brush.getTotalLength(), 1)
    } catch {
      length = Math.max(vertical ? box.height : box.width, 1) + pad * 2
    }
    brush.setAttribute('stroke-dasharray', String(length))
    brush.setAttribute('stroke-dashoffset', String(length))

    animateDash(brush, length, 0, FILL_STROKE_MS, mine, () => {
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

      requestAnimationFrame(() => {
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

  /**
   * @param {SVGSVGElement} svg
   * @param {SVGPathElement[]} paths
   * @param {number} mine
   * @param {Function} done
   */
  function wipeFillPaths (svg, paths, mine, done) {
    if (!paths.length) {
      done()
      return
    }

    const ordered = sortPathsForStrokeDirection(paths)
    let remaining = ordered.length
    ordered.forEach((path, index) => {
      setTimeout(() => {
        if (mine !== token) {
          return
        }
        paintOneFill(svg, path, index, mine, () => {
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
   *
   * @param {HTMLElement} host
   * @param {SVGSVGElement} nextSvg
   * @param {string[]} oldKeys
   * @param {number} mine
   * @param {Function} done
   */
  function wipeInFresh (host, nextSvg, oldKeys, mine, done) {
    const seen = keySet(oldKeys)
    const strokes = []
    const fills = []
    Array.prototype.forEach.call(nextSvg.querySelectorAll('path'), (path) => {
      const key = path.getAttribute('d') || ''
      if (!key || seen[key]) {
        return
      }
      if (isStrokePath(path)) {
        strokes.push(path)
      } else {
        fills.push(path)
      }
    })

    if (!strokes.length && !fills.length) {
      mountBase(host, nextSvg)
      done()
      return
    }

    fills.forEach((path) => {
      path.style.visibility = 'hidden'
    })
    strokes.forEach((path) => {
      let length = 1
      try {
        length = Math.max(path.getTotalLength(), 1)
      } catch {
        length = 400
      }
      path.setAttribute('stroke-dasharray', String(length))
      path.setAttribute('stroke-dashoffset', String(length))
    })

    mountBase(host, nextSvg)

    let pending = 0
    /** Mark one of the parallel stroke/fill groups finished. */
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

  /**
   * @param {HTMLImageElement} front
   * @param {string} src
   */
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

    /** Fall back to plain <img> if SVG load/parse fails. */
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

    /**
     * @param {string} srcDone
     */
    function commit (srcDone) {
      if (mine !== token) {
        return
      }
      front.setAttribute('data-hangman-src', srcDone)
      snapImg(front, srcDone)
    }

    loadSvg(src)
      .then((text) => {
        if (mine !== token) {
          return
        }
        const svg = parseSvg(text)
        svg.setAttribute('viewBox', viewBoxOf(svg))
        const newKeys = pathKeys(svg)
        const additive = !immediate && isAdditive(oldKeys, newKeys)

        /** Finish this transition and sync the backing <img>. */
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
