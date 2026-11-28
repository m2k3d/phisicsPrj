export const slowMotionFactor = 40

export function createSimulationClock(startMs: number, slowMotion = false) {
  let anchorMs = startMs
  let elapsedAtAnchorS = 0
  let rate = slowMotion ? 1 / slowMotionFactor : 1

  function elapsedSeconds(nowMs: number) {
    return elapsedAtAnchorS + (nowMs - anchorMs) / 1000 * rate
  }

  return {
    elapsedSeconds,
    setSlowMotion(enabled: boolean, nowMs: number) {
      elapsedAtAnchorS = elapsedSeconds(nowMs)
      anchorMs = nowMs
      rate = enabled ? 1 / slowMotionFactor : 1
    },
    reset(nowMs: number) {
      anchorMs = nowMs
      elapsedAtAnchorS = 0
    },
  }
}
