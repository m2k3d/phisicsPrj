export const measuredPeriods = 5
const sampleRateHz = 8192

export type Reading = {
  frequencyHz: number
  durationS: number
  startS: number
  endS: number
}

export function createFrequencyMeter(sample: (timeS: number) => number) {
  let index = 1
  let previous = sample(0)
  let firstCrossing: number | undefined
  let crossings = 0
  let reading: Reading | null = null

  return {
    advance(timeS: number) {
      while (!reading && index / sampleRateHz <= timeS) {
        const value = sample(index / sampleRateHz)
        if (previous < 0 && value >= 0) {
          const crossing = (index - 1 - previous / (value - previous)) / sampleRateHz
          firstCrossing ??= crossing
          if (++crossings === measuredPeriods + 1) {
            const durationS = crossing - firstCrossing
            reading = { frequencyHz: measuredPeriods / durationS, durationS, startS: firstCrossing, endS: crossing }
          }
        }
        previous = value
        index++
      }
      return reading
    },
  }
}
