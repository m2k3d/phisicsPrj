import { RoundedBox } from '@react-three/drei'
import { useMemo, useEffect } from 'react'
import {
  CanvasTexture, CatmullRomCurve3, DataTexture, LinearFilter, LinearMipmapLinearFilter,
  RepeatWrapping, SRGBColorSpace, TubeGeometry, Vector3,
} from 'three'
import { massesG, strings, type MassG } from '../physics/string'

export const wireXs = [-1.55, -0.4, 0.75]
export const boardY = 3.86
export const hookY = boardY - 3
const trayX = 2.34
const trayZ = 0.64
const massSize = {
  100: { radius: 0.161, height: 0.20 },
  200: { radius: 0.195, height: 0.275 },
  300: { radius: 0.217, height: 0.336 },
}

const steel = '#9aaebb'
const brass = '#bd8741'

export function Board({ active }: { active: number }) {
  const brush = useMemo(() => {
    const pixels = new Uint8Array(64 * 4)
    for (let row = 0; row < 64; row++) {
      const value = 128 + Math.round(28 * Math.sin(row * 2.41) + 15 * Math.sin(row * 0.83))
      pixels.set([value, value, value, 255], row * 4)
    }
    const texture = new DataTexture(pixels, 1, 64)
    texture.wrapT = RepeatWrapping
    texture.repeat.y = 2
    texture.magFilter = LinearFilter
    texture.minFilter = LinearMipmapLinearFilter
    texture.generateMipmaps = true
    texture.needsUpdate = true
    return texture
  }, [])
  useEffect(() => () => brush.dispose(), [brush])

  const slot = 0.073
  const edge = [-2.34, ...wireXs.flatMap(x => [x - slot / 2, x + slot / 2]), 1.55]

  return (
    <>
      <RoundedBox args={[3.89, 0.15, 0.67]} position={[-0.395, boardY + 0.075, -0.55]}
        radius={0.018} smoothness={2} castShadow receiveShadow>
        <meshStandardMaterial color="#9aabb6" metalness={0.39} roughness={0.34} bumpMap={brush} bumpScale={0.006} />
      </RoundedBox>
      {edge.filter((_, i) => i % 2 === 0).map((left, i) => {
        const right = edge[i * 2 + 1]
        return (
          <RoundedBox key={left} args={[right - left, 0.15, 0.54]}
            position={[(left + right) / 2, boardY + 0.075, 0.055]}
            radius={0.018} smoothness={2} castShadow receiveShadow>
            <meshStandardMaterial color="#9aabb6" metalness={0.39} roughness={0.34} bumpMap={brush} bumpScale={0.006} />
          </RoundedBox>
        )
      })}
      {wireXs.map((x, index) => (
        <group key={x} position={[x, boardY, 0]}>
          <mesh position={[0, 0.075, 0]} castShadow>
            <cylinderGeometry args={[0.013, 0.013, 0.15, 10]} />
            <meshStandardMaterial color={active === index ? brass : steel} metalness={0.35} />
          </mesh>
          <mesh position={[0, 0.192, 0]} castShadow>
            <cylinderGeometry args={[0.084, 0.099, 0.084, 32]} />
            <meshStandardMaterial color={active === index ? brass : '#c2cbd0'} metalness={0.36} roughness={0.28} />
          </mesh>
          <mesh position={[0, 0.235, 0]}>
            <cylinderGeometry args={[0.029, 0.029, 0.003, 16]} />
            <meshStandardMaterial color={active === index ? '#815422' : '#6a7a84'} roughness={0.35} />
          </mesh>
        </group>
      ))}
    </>
  )
}

export function StringHook({ x }: { x: number }) {
  const geometry = useMemo(() => {
    const points = [new Vector3(0, 0, 0), new Vector3(0, -0.022, 0)]
    for (let i = 0; i <= 24; i++) {
      const angle = Math.PI + i * 1.62 * Math.PI / 24
      points.push(new Vector3(0.039 + 0.039 * Math.cos(angle), -0.047 + 0.039 * Math.sin(angle), 0))
    }
    points.push(new Vector3(0.062, -0.005, 0))
    return new TubeGeometry(new CatmullRomCurve3(points), 48, 0.012, 8, false)
  }, [])
  useEffect(() => () => geometry.dispose(), [geometry])

  return (
    <mesh position={[x, hookY, 0]} geometry={geometry} castShadow>
      <meshStandardMaterial color="#bcccd4" metalness={0.40} roughness={0.26} />
    </mesh>
  )
}

function Weight({ mass, position, onClick }: {
  mass: MassG
  position: [number, number, number]
  onClick?: () => void
}) {
  const { radius, height } = massSize[mass]
  return (
    <group position={position} onClick={event => { event.stopPropagation(); onClick?.() }}>
      <mesh castShadow receiveShadow>
        <cylinderGeometry args={[radius, radius * 0.98, height, 48]} />
        <meshStandardMaterial color={brass} metalness={0.42} roughness={0.31} />
      </mesh>
      <mesh position={[0, height / 2 - 0.012, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[radius - 0.007, 0.008, 8, 48]} />
        <meshStandardMaterial color="#ddad68" metalness={0.43} roughness={0.28} />
      </mesh>
      <mesh position={[0, height / 2 + 0.038, 0]} rotation={[0, Math.PI / 2, 0]} castShadow>
        <torusGeometry args={[0.035, 0.009, 10, 32]} />
        <meshStandardMaterial color="#b8c4cd" metalness={0.40} roughness={0.25} />
      </mesh>
    </group>
  )
}

function TrayLabel({ mass, x }: { mass: MassG; x: number }) {
  const label = useMemo(() => {
    const canvas = document.createElement('canvas')
    canvas.width = 128
    canvas.height = 32
    const pen = canvas.getContext('2d')!
    pen.font = '600 25px sans-serif'
    pen.textAlign = 'center'
    pen.textBaseline = 'middle'
    pen.fillStyle = '#dbe7ec'
    pen.fillText(`${mass} г`, 64, 16)
    const texture = new CanvasTexture(canvas)
    texture.colorSpace = SRGBColorSpace
    return texture
  }, [mass])
  useEffect(() => () => label.dispose(), [label])
  return (
    <mesh position={[x, 0.14, trayZ + 0.432]}>
      <planeGeometry args={[0.43, 0.1075]} />
      <meshBasicMaterial map={label} transparent depthWrite={false} toneMapped={false} />
    </mesh>
  )
}

export function Weights({ active, mass, mount }: {
  active: (typeof strings)[number]
  mass: MassG | null
  mount: (mass: MassG | null) => void
}) {
  return (
    <>
      <RoundedBox args={[2.10, 0.115, 0.86]} position={[trayX, 0.059, trayZ]}
        radius={0.028} smoothness={2} castShadow receiveShadow>
        <meshStandardMaterial color="#293a46" metalness={0.25} roughness={0.41} />
      </RoundedBox>
      {[trayZ - 0.405, trayZ + 0.405].map(z => (
        <RoundedBox key={z} args={[2.10, 0.118, 0.052]} position={[trayX, 0.14, z]}
          radius={0.013} smoothness={2} castShadow receiveShadow>
          <meshStandardMaterial color="#435460" metalness={0.29} roughness={0.39} />
        </RoundedBox>
      ))}
      {[trayX - 1.024, trayX + 1.024].map(x => (
        <RoundedBox key={x} args={[0.052, 0.117, 0.765]} position={[x, 0.14, trayZ]}
          radius={0.013} smoothness={2} castShadow receiveShadow>
          <meshStandardMaterial color="#435460" metalness={0.29} roughness={0.39} />
        </RoundedBox>
      ))}
      {massesG.map((value, index) => {
        const x = trayX + (index - 1) * 0.64
        const mounted = mass === value
        const { height } = massSize[value]
        const position: [number, number, number] = mounted
          ? [wireXs[strings.indexOf(active)] + 0.039, hookY - 0.118 - height / 2, 0]
          : [x, 0.132 + height / 2, trayZ]
        return (
          <group key={value}>
            <mesh position={[x, 0.123, trayZ]} receiveShadow>
              <cylinderGeometry args={[0.248, 0.248, 0.015, 40]} />
              <meshStandardMaterial color={mounted ? '#344352' : '#647580'} roughness={0.42} metalness={0.32} />
            </mesh>
            <TrayLabel mass={value} x={x} />
            <Weight mass={value} position={position} onClick={() => mount(mounted ? null : value)} />
          </group>
        )
      })}
    </>
  )
}
