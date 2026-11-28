import { describe, expect, it } from 'vitest'
import { createFrequencyMeter } from './meter'
import { getDisplacement, getStringParameters, massesG, strings } from './string'

describe('частотомер', () => {
  it.each(strings.flatMap(diameter => massesG.map(mass => [diameter, mass] as const)))(
    'измеряет пять периодов для струны %s мм с грузом %s г',
    (diameter, mass) => {
      const { frequencyHz } = getStringParameters(diameter, mass)
      for (const initialDisplacementM of [0.012, -0.008]) {
        const meter = createFrequencyMeter(time => getDisplacement({ frequencyHz, initialDisplacementM }, time, 0.5))
        expect(meter.advance(4.9 / frequencyHz)).toBeNull()
        const reading = meter.advance(6 / frequencyHz)!
        expect(reading.frequencyHz).toBeCloseTo(frequencyHz, 3)
        expect(reading.durationS).toBeCloseTo(5 / frequencyHz, 6)
      }
    },
  )

  it('измеряет частоту сигнала независимо от размера шага обновления', () => {
    const signal = (time: number) => Math.sin(2 * Math.PI * 87 * time - 0.4)
    const meter = createFrequencyMeter(signal)
    for (const step of [0.003, 0.023, 0.054, 0.11]) meter.advance(step)
    expect(meter.advance(0.13)).toEqual(createFrequencyMeter(signal).advance(0.13))
  })

  it('пропускает сигнал покоя', () => {
    expect(createFrequencyMeter(() => 0).advance(0.18)).toBeNull()
  })
})
