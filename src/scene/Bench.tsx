import { ContactShadows, OrbitControls } from '@react-three/drei'
import { Canvas, useThree } from '@react-three/fiber'
import { Component, memo, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { OrthographicCamera } from 'three'
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib'
import prototype from '../../assets/blender/prototype.png'
import { strings } from '../physics/string'
import type { Experiment } from '../useExperiment'
import { Board, StringHook, Weights, wireXs } from './parts'
import { Wire } from './Wire'

const viewPosition: [number, number, number] = [0.78, 4.55, 8.95]
const viewTarget: [number, number, number] = [0.46, 2.03, 0]
const shadowScale: [number, number] = [8, 5]

function Camera({ controls, version }: {
  controls: React.RefObject<OrbitControlsImpl | null>
  version: number
}) {
  const { camera, size, invalidate } = useThree()
  const zoom = Math.min(size.width / 6.55, size.height / 4.72)

  useLayoutEffect(() => {
    if (!(camera instanceof OrthographicCamera)) return
    const orbit = controls.current
    const damping = orbit?.enableDamping ?? false
    if (orbit) {
      orbit.enableDamping = false
      orbit.update()
    }
    camera.zoom = zoom
    camera.position.set(...viewPosition)
    camera.updateProjectionMatrix()
    if (orbit) {
      orbit.target.set(...viewTarget)
      orbit.update()
      orbit.enableDamping = damping
    }
    invalidate()
  }, [camera, controls, invalidate, version, zoom])

  return (
    <OrbitControls ref={controls} target={viewTarget} enablePan={false}
      minZoom={zoom * 0.9} maxZoom={zoom * 2.05}
      minAzimuthAngle={-0.53} maxAzimuthAngle={0.53}
      minPolarAngle={Math.PI * 0.24} maxPolarAngle={Math.PI * 0.51} />
  )
}

const FloorShadows = memo(function FloorShadows(_: Pick<Experiment, 'diameter' | 'mass'>) {
  // Render the shadows again only when a load changes position.
  return <ContactShadows position={[0.4, 0.001, 0.5]} scale={shadowScale}
    opacity={0.78} blur={2.6} far={1.55} resolution={256} frames={1} color="#192530" />
})

function Stage({ lab, version }: { lab: Experiment; version: number }) {
  const controls = useRef<OrbitControlsImpl>(null)
  return (
    <>
      <Camera controls={controls} version={version} />
      <hemisphereLight args={['#d9ecff', '#8090a0', 2.35]} />
      <directionalLight position={[-3.8, 6.4, 4.3]} color="#e2efff" intensity={2.45} />
      <directionalLight position={[4, 3, 0.6]} color="#ffe2b7" intensity={1.46} />
      <directionalLight position={[-0.6, 4, -4.5]} color="#bacdea" intensity={1.5} />
      <Board active={strings.indexOf(lab.diameter)} />
      {strings.map((diameter, i) => (
        <group key={diameter}>
          <Wire x={wireXs[i]} diameter={diameter} lab={lab} controls={controls} />
          <StringHook x={wireXs[i]} />
        </group>
      ))}
      <Weights active={lab.diameter} mass={lab.mass} mount={lab.mountWeight} />
      <FloorShadows diameter={lab.diameter} mass={lab.mass} />
    </>
  )
}

function StaticBench() {
  return (
    <div className="scene-fallback">
      <img src={prototype} alt="Схема установки с тремя струнами, приборами и грузами" />
      <p>3D недоступно в этом браузере. Для опыта используй кнопки под установкой.</p>
    </div>
  )
}

class GraphicsBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() { return this.state.failed ? <StaticBench /> : this.props.children }
}

export function Bench({ lab }: { lab: Experiment }) {
  const [version, setVersion] = useState(0)
  return (
    <div className="bench" data-testid="bench">
      <div className="viewport" aria-label="Трёхмерная установка">
        <GraphicsBoundary>
          <Canvas orthographic camera={{ position: viewPosition, near: 0.1, far: 100 }}
            dpr={[1, 1.6]} frameloop="demand" fallback={<StaticBench />}>
            <Stage lab={lab} version={version} />
          </Canvas>
        </GraphicsBoundary>
      </div>
      <button className="view-reset" type="button" title="Вернуть исходный ракурс" onClick={() => setVersion(v => v + 1)}>
        <span aria-hidden="true">↶</span> Сбросить ракурс
      </button>
    </div>
  )
}
