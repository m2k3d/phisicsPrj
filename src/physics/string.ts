const gravityMS2 = 9.81
const steelDensityKgM3 = 7800
const lengthM = 0.30
const decayTimeS = 0.35

export const strings = [0.3, 0.4, 0.5] as const
export const massesG = [100, 200, 300] as const

export type DiameterMm = (typeof strings)[number]
export type MassG = (typeof massesG)[number]

export function getStringParameters(diameterMm: DiameterMm, massG: MassG) {
  const diameterM = diameterMm / 1000
  const linearDensityKgM = steelDensityKgM3 * Math.PI * diameterM ** 2 / 4
  const tensionN = massG / 1000 * gravityMS2
  const waveSpeedMS = Math.sqrt(tensionN / linearDensityKgM)
  const frequencyHz = waveSpeedMS / (2 * lengthM)

  return { lengthM, linearDensityKgM, tensionN, waveSpeedMS, frequencyHz }
}

export type Pluck = {
  frequencyHz: number
  initialDisplacementM: number
}

export function getAmplitude(pluck: Pluck, elapsedS: number) {
  return Math.abs(pluck.initialDisplacementM) * Math.exp(-elapsedS / decayTimeS)
}

export function getDisplacement(pluck: Pluck, elapsedS: number, position: number) {
  // In the first fast mode the heavy load is effectively stationary.
  if (position === 0 || position === 1) return 0

  const shape = Math.sin(Math.PI * position)
  const phase = 2 * Math.PI * pluck.frequencyHz * elapsedS
  return Math.sign(pluck.initialDisplacementM) * getAmplitude(pluck, elapsedS) * shape * Math.cos(phase)
}
