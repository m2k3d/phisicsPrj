import { useEffect, useMemo, useRef, type RefObject } from 'react'
import { useFrame, useThree, type ThreeEvent } from '@react-three/fiber'
import { CylinderGeometry, Mesh, Plane, PlaneGeometry, Vector3 } from 'three'
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib'
import { getAmplitude, getDisplacement, type DiameterMm } from '../physics/string'
import type { Experiment } from '../useExperiment'
import { boardY, hookY } from './parts'

const midpointY = (boardY + hookY) / 2
const wirePlane = new Plane(new Vector3(0, 0, 1), 0)
const intersection = new Vector3()
const vertexShader = `
  varying vec2 surfaceUv;
  void main() {
    surfaceUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`
const fragmentShader = `
  varying vec2 surfaceUv;
  void main() {
    float center = 1.0 - abs(surfaceUv.x * 2.0 - 1.0);
    float taper = smoothstep(0.0, 0.16, surfaceUv.y) * smoothstep(0.0, 0.16, 1.0 - surfaceUv.y);
    gl_FragColor = vec4(1.0, 0.63, 0.28, (0.14 + 0.35 * center) * taper * smoothstep(0.0, 0.17, center));
  }
`

export function Wire({ x, diameter, lab, controls }: {
  x: number
  diameter: DiameterMm
  lab: Experiment
  controls: RefObject<OrbitControlsImpl | null>
}) {
  const selected = lab.diameter === diameter
  const dragging = useRef<{ id: number; fromX: number } | null>(null)
  const envelope = useRef<Mesh>(null)
  const cylinder = useMemo(() => new CylinderGeometry(diameter * 0.029, diameter * 0.029, 3, 10, 48), [diameter])
  const ribbon = useMemo(() => new PlaneGeometry(2, 3, 20, 40), [])
  const cylinderBase = useMemo(() => cylinder.attributes.position.clone(), [cylinder])
  const ribbonBase = useMemo(() => ribbon.attributes.position.clone(), [ribbon])
  const lastWidth = useRef(0)
  const lastDisplacement = useRef(0)
  const invalidate = useThree(state => state.invalidate)
  const canvas = useThree(state => state.gl.domElement)
  const motionRef = lab.motion

  useEffect(() => () => { cylinder.dispose(); ribbon.dispose() }, [cylinder, ribbon])
  useEffect(() => {
    function cancel(event: PointerEvent) {
      if (dragging.current?.id !== event.pointerId) return
      dragging.current = null
      motionRef.current.dragM = null
      if (controls.current) controls.current.enabled = true
      invalidate()
    }
    canvas.addEventListener('pointercancel', cancel)
    canvas.addEventListener('lostpointercapture', cancel)
    return () => {
      canvas.removeEventListener('pointercancel', cancel)
      canvas.removeEventListener('lostpointercapture', cancel)
    }
  }, [canvas, controls, invalidate, motionRef])

  useFrame(() => {
    const motion = lab.motion.current
    const pluck = selected ? motion.pluck : null
    const time = motion.clock.elapsedSeconds(performance.now())
    const amplitudeM = pluck ? getAmplitude(pluck, time) : 0
    const oscillating = amplitudeM > 0.00038
    if (oscillating) invalidate()
    const displacementM = selected ? motion.dragM ?? (pluck && lab.slow && oscillating ? getDisplacement(pluck, time, 0.5) : 0) : 0
    const widthM = lab.slow ? 0 : amplitudeM
    const bend = displacementM * 10

    if (Math.abs(bend - lastDisplacement.current) > 0.00004 || (bend === 0 && lastDisplacement.current !== 0)) {
      const points = cylinder.attributes.position
      for (let i = 0; i < points.count; i++) {
        const arc = Math.cos(Math.PI * cylinderBase.getY(i) / 3)
        points.setX(i, cylinderBase.getX(i) + bend * arc)
      }
      points.needsUpdate = true
      lastDisplacement.current = bend
    }

    if (envelope.current) envelope.current.visible = widthM > 0.00038
    if (widthM <= 0.00038 || Math.abs(widthM - lastWidth.current) < 0.000012) return
    const points = ribbon.attributes.position
    for (let i = 0; i < points.count; i++) {
      const arc = Math.cos(Math.PI * ribbonBase.getY(i) / 3)
      points.setX(i, ribbonBase.getX(i) * widthM * 10 * arc)
    }
    points.needsUpdate = true
    lastWidth.current = widthM
  })

  function start(event: ThreeEvent<PointerEvent>) {
    if (event.button !== 0 || !event.isPrimary || dragging.current) return
    event.stopPropagation()
    if (!event.ray.intersectPlane(wirePlane, intersection) || !lab.startDrag(diameter)) return
    dragging.current = { id: event.pointerId, fromX: intersection.x }
    if (controls.current) controls.current.enabled = false
    const capture = event.target as unknown as Element
    capture.setPointerCapture(event.pointerId)
  }

  function move(event: ThreeEvent<PointerEvent>) {
    const drag = dragging.current
    if (!drag || drag.id !== event.pointerId || lab.motion.current.dragM === null) return
    event.stopPropagation()
    if (!event.ray.intersectPlane(wirePlane, intersection)) return
    lab.motion.current.dragM = Math.min(0.023, Math.max(-0.023, (intersection.x - drag.fromX) / 10))
    invalidate()
  }

  function finish(event: ThreeEvent<PointerEvent>) {
    if (dragging.current?.id !== event.pointerId) return
    event.stopPropagation()
    const displacement = lab.motion.current.dragM
    dragging.current = null
    lab.motion.current.dragM = null
    if (controls.current) controls.current.enabled = true
    const capture = event.target as unknown as Element
    if (capture.hasPointerCapture(event.pointerId)) capture.releasePointerCapture(event.pointerId)
    if (displacement !== null) lab.pluck(displacement)
    invalidate()
  }

  return (
    <group position={[x, midpointY, 0]}>
      <mesh geometry={cylinder} frustumCulled={false}>
        <meshStandardMaterial color={selected ? '#f0af59' : '#bfcdd5'} metalness={0.19} roughness={0.34} />
      </mesh>
      <mesh ref={envelope} geometry={ribbon} visible={false} frustumCulled={false}>
        <shaderMaterial transparent depthWrite={false} vertexShader={vertexShader} fragmentShader={fragmentShader} />
      </mesh>
      <mesh visible={false} onPointerDown={start} onPointerMove={move} onPointerUp={finish}
        onPointerOver={event => { event.nativeEvent.target instanceof HTMLElement && (event.nativeEvent.target.style.cursor = lab.mass ? 'grab' : 'pointer') }}
        onPointerOut={event => { if (event.nativeEvent.target instanceof HTMLElement) event.nativeEvent.target.style.cursor = '' }}>
        <boxGeometry args={[0.28, 2.40, 0.17]} />
      </mesh>
    </group>
  )
}
