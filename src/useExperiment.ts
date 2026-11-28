import { useEffect, useRef, useState } from 'react'
import { createStringAudio } from './audio'
import { createSimulationClock } from './physics/clock'
import { createFrequencyMeter, type Reading } from './physics/meter'
import { getDisplacement, getStringParameters, type DiameterMm, type MassG, type Pluck } from './physics/string'

export type Motion = {
  clock: ReturnType<typeof createSimulationClock>
  pluck: Pluck | null
  dragM: number | null
}

type Result = Reading & { diameter: DiameterMm; mass: MassG; theoreticalHz: number }
type Stopwatch = { startS: number | null; accumulatedS: number }

export function useExperiment() {
  const [diameter, setDiameter] = useState<DiameterMm>(0.3)
  const [mass, setMass] = useState<MassG | null>(null)
  const [slow, setSlow] = useState(false)
  const [sound, setSound] = useState(true)
  const [phase, setPhase] = useState<'idle' | 'measuring' | 'measured'>('idle')
  const [reading, setReading] = useState<Reading | null>(null)
  const [results, setResults] = useState<Result[]>([])
  const [watchS, setWatchS] = useState(0)
  const [watchRunning, setWatchRunning] = useState(false)
  const conditions = useRef({ diameter, mass })
  const motion = useRef<Motion>({ clock: createSimulationClock(performance.now()), pluck: null, dragM: null })
  const modelTime = useRef(createSimulationClock(performance.now()))
  const watch = useRef<Stopwatch>({ startS: null, accumulatedS: 0 })
  const audio = useRef(createStringAudio())
  const pending = useRef<{ meter: ReturnType<typeof createFrequencyMeter>; diameter: DiameterMm; mass: MassG; theoreticalHz: number } | null>(null)

  useEffect(() => {
    const timer = window.setInterval(() => {
      const now = performance.now()
      const { startS, accumulatedS } = watch.current
      if (startS !== null) setWatchS(accumulatedS + modelTime.current.elapsedSeconds(now) - startS)

      const experiment = pending.current
      if (!experiment) return
      const next = experiment.meter.advance(motion.current.clock.elapsedSeconds(now))
      if (!next) return
      pending.current = null
      setReading(next)
      setPhase('measured')
      const { diameter, mass, theoreticalHz } = experiment
      setResults(previous => {
        const row = { ...next, diameter, mass, theoreticalHz }
        const index = previous.findIndex(item => item.diameter === diameter && item.mass === mass)
        return index < 0 ? [...previous, row] : previous.map((item, i) => i === index ? row : item)
      })
    }, 20)
    const soundEngine = audio.current
    return () => {
      window.clearInterval(timer)
      soundEngine.silence()
    }
  }, [])

  function clearMeasurement() {
    motion.current.pluck = null
    motion.current.dragM = null
    pending.current = null
    audio.current.silence()
    setReading(null)
    setPhase('idle')
  }

  function selectString(next: DiameterMm) {
    if (conditions.current.diameter === next) return
    clearMeasurement()
    conditions.current.diameter = next
    setDiameter(next)
  }

  function mountWeight(next: MassG | null) {
    if (conditions.current.mass === next) return
    clearMeasurement()
    conditions.current.mass = next
    setMass(next)
  }

  function startDrag(next: DiameterMm) {
    selectString(next)
    if (conditions.current.mass === null) return false
    clearMeasurement()
    motion.current.dragM = 0
    return true
  }

  function pluck(displacementM = 0.014) {
    const { diameter, mass } = conditions.current
    motion.current.dragM = null
    if (mass === null || Math.abs(displacementM) < 0.001) return
    const { frequencyHz } = getStringParameters(diameter, mass)
    const current = { frequencyHz, initialDisplacementM: displacementM }
    motion.current.pluck = current
    motion.current.clock.reset(performance.now())
    pending.current = {
      meter: createFrequencyMeter(time => getDisplacement(current, time, 0.5)),
      diameter, mass, theoreticalHz: frequencyHz,
    }
    setPhase('measuring')
    setReading(null)
    if (sound) audio.current.play(frequencyHz, Math.abs(displacementM))
  }

  function changeSpeed() {
    const now = performance.now()
    motion.current.clock.setSlowMotion(!slow, now)
    modelTime.current.setSlowMotion(!slow, now)
    setSlow(!slow)
  }

  function changeSound() {
    if (sound) audio.current.silence()
    setSound(!sound)
  }

  function toggleWatch() {
    const now = modelTime.current.elapsedSeconds(performance.now())
    if (watch.current.startS === null) {
      watch.current.startS = now
      setWatchRunning(true)
    } else {
      watch.current.accumulatedS += now - watch.current.startS
      watch.current.startS = null
      setWatchS(watch.current.accumulatedS)
      setWatchRunning(false)
    }
  }

  function resetWatch() {
    watch.current = { startS: null, accumulatedS: 0 }
    setWatchS(0)
    setWatchRunning(false)
  }

  return {
    diameter, mass, slow, sound, phase, reading, results, watchS, watchRunning, motion,
    selectString, mountWeight, startDrag, pluck, changeSpeed, changeSound, toggleWatch, resetWatch,
  }
}

export type Experiment = ReturnType<typeof useExperiment>
