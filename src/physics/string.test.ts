import { describe, expect, it } from 'vitest'
import {
  massesG,
  strings,
  getStringParameters,
  getAmplitude,
  getDisplacement,
} from './string'

const referenceFrequencies = [
  { diameterMm: 0.3, massG: 100, hz: 70.3 },
  { diameterMm: 0.3, massG: 200, hz: 99.4 },
  { diameterMm: 0.3, massG: 300, hz: 121.8 },
  { diameterMm: 0.4, massG: 100, hz: 52.7 },
  { diameterMm: 0.4, massG: 200, hz: 74.6 },
  { diameterMm: 0.4, massG: 300, hz: 91.3 },
  { diameterMm: 0.5, massG: 100, hz: 42.2 },
  { diameterMm: 0.5, massG: 200, hz: 59.7 },
  { diameterMm: 0.5, massG: 300, hz: 73.1 },
] as const

describe('натянутая стальная струна', () => {
  it('даёт девять комбинаций для опыта', () => {
    expect(strings).toEqual([0.3, 0.4, 0.5])
    expect(massesG).toEqual([100, 200, 300])
  })

  it.each(referenceFrequencies)('$diameterMm мм и $massG г: $hz Гц', ({ diameterMm, massG, hz }) => {
    const parameters = getStringParameters(diameterMm, massG)
    expect(parameters.frequencyHz).toBeCloseTo(hz, 1)
    expect(parameters.tensionN).toBeCloseTo(massG * 0.00981, 8)
    expect(parameters.linearDensityKgM * parameters.lengthM).toBeLessThan(0.0005)
  })

  it('возвращается в исходную фазу за период с меньшей амплитудой', () => {
    const { frequencyHz } = getStringParameters(0.3, 100)
    const pluck = { frequencyHz, initialDisplacementM: -0.004 }
    const periodS = 1 / frequencyHz

    expect(getDisplacement(pluck, 0, 0.5)).toBe(-0.004)
    expect(getDisplacement(pluck, periodS / 4, 0.5)).toBeCloseTo(0, 10)
    expect(getDisplacement(pluck, periodS / 2, 0.5)).toBeCloseTo(getAmplitude(pluck, periodS / 2), 10)
    expect(getDisplacement(pluck, periodS, 0.5)).toBeCloseTo(-getAmplitude(pluck, periodS), 10)
    expect(getAmplitude(pluck, periodS)).toBeLessThan(0.004)
  })

  it('оставляет концы на месте и даёт наибольшее смещение посередине', () => {
    const pluck = { frequencyHz: 70, initialDisplacementM: 0.004 }
    expect(getDisplacement(pluck, 0, 0)).toBe(0)
    expect(getDisplacement(pluck, 0, 1)).toBe(0)
    expect(getDisplacement(pluck, 0, 0.25)).toBeCloseTo(0.004 / Math.sqrt(2), 10)
  })
})
