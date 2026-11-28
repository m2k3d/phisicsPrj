export function createStringAudio() {
  let context: AudioContext | undefined
  let active: { oscillator: OscillatorNode; gain: GainNode } | undefined

  function silence() {
    if (!context || !active) return
    const time = context.currentTime
    const parameter = active.gain.gain
    if (typeof parameter.cancelAndHoldAtTime === 'function') {
      parameter.cancelAndHoldAtTime(time)
    } else {
      const value = parameter.value
      parameter.cancelScheduledValues(time)
      parameter.setValueAtTime(value, time)
    }
    parameter.linearRampToValueAtTime(0, time + 0.02)
    active.oscillator.stop(time + 0.025)
    active = undefined
  }

  return {
    play(frequencyHz: number, amplitudeM: number) {
      if (!window.AudioContext) return
      context ??= new AudioContext()
      void context.resume().catch(() => {})
      silence()
      const oscillator = context.createOscillator()
      const gain = context.createGain()
      const time = context.currentTime
      oscillator.type = 'triangle'
      oscillator.frequency.setValueAtTime(frequencyHz, time)
      gain.gain.setValueAtTime(0, time)
      gain.gain.linearRampToValueAtTime(Math.min(0.24, 0.045 + amplitudeM * 9), time + 0.008)
      gain.gain.exponentialRampToValueAtTime(0.0001, time + 1.05)
      oscillator.connect(gain).connect(context.destination)
      const note = { oscillator, gain }
      active = note
      oscillator.onended = () => {
        oscillator.disconnect()
        gain.disconnect()
        if (active === note) active = undefined
      }
      oscillator.start(time)
      oscillator.stop(time + 1.08)
    },
    silence,
  }
}
