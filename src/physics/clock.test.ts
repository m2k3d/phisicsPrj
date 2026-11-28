import { describe, expect, it } from 'vitest'
import { createSimulationClock } from './clock'

describe('часы модели', () => {
  it('идут в реальном времени и меняют скорость без скачка времени', () => {
    const clock = createSimulationClock(1_000)
    expect(clock.elapsedSeconds(1_500)).toBe(0.5)
    clock.setSlowMotion(true, 1_500)
    expect(clock.elapsedSeconds(1_500)).toBe(0.5)
    expect(clock.elapsedSeconds(3_500)).toBeCloseTo(0.55, 10)
    clock.setSlowMotion(false, 3_500)
    expect(clock.elapsedSeconds(3_750)).toBeCloseTo(0.8, 10)
  })

  it('начинает новый опыт с нуля на текущей скорости', () => {
    const clock = createSimulationClock(1_000, true)
    expect(clock.elapsedSeconds(2_000)).toBeCloseTo(0.025, 10)
    clock.reset(2_000)
    expect(clock.elapsedSeconds(2_000)).toBe(0)
    expect(clock.elapsedSeconds(3_000)).toBeCloseTo(0.025, 10)
  })
})
