import { getDisplacement, type Pluck } from './physics/string'
import { measuredPeriods, type Reading } from './physics/meter'
import type { Experiment } from './useExperiment'

export function format(value: number, digits = 2) {
  return value.toLocaleString('ru-RU', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

const left = 58, right = 516, top = 24, bottom = 123
const center = (top + bottom) / 2

function SignalPlot({ pluck, reading }: { pluck: Pluck | null; reading: Reading | null }) {
  const durationS = reading ? Math.ceil(reading.endS / 0.01) * 0.01 : 0.10
  const amplitudeMm = pluck && reading ? Math.ceil(Math.abs(pluck.initialDisplacementM) * 1000) : 10
  const plotX = (time: number) => left + time / durationS * (right - left)
  const path = pluck && reading ? Array.from({ length: 281 }, (_, i) => {
    const time = i / 280 * durationS
    const mm = getDisplacement(pluck, time, 0.5) * 1000
    return `${i ? 'L' : 'M'}${plotX(time).toFixed(2)} ${(center - mm / amplitudeMm * (center - top)).toFixed(2)}`
  }).join(' ') : ''

  return (
    <svg className="plot" viewBox="0 0 560 151" role="img"
      aria-label={reading ? 'График колебаний. Пунктиром отмечены границы пяти периодов измерения.' : 'График смещения появится после измерения'}>
      <text x="7" y="14">мм</text>
      {[top, center, bottom].map((y, i) => <g key={y}>
        <text x="47" y={y + 4} textAnchor="end">{i === 0 ? amplitudeMm : i === 1 ? '0' : `−${amplitudeMm}`}</text>
        <line className={i === 1 ? 'plot-axis' : 'plot-grid'} x1={left} x2={right} y1={y} y2={y} />
      </g>)}
      {[0, 1, 2, 3, 4, 5].map(tick => {
        const time = durationS * tick / 5
        const x = plotX(time)
        return <g key={tick}>
          <line className="plot-grid" x1={x} x2={x} y1={top} y2={bottom} />
          <text x={x} y="141" textAnchor="middle">{Math.round(time * 1000)}</text>
        </g>
      })}
      <text x="550" y="141" textAnchor="end">мс</text>
      {reading && (
        <>
          <rect className="plot-range" x={plotX(reading.startS)} y={top} height={bottom - top}
            width={plotX(reading.endS) - plotX(reading.startS)} />
          {[reading.startS, reading.endS].map(time =>
            <line key={time} className="plot-marker" x1={plotX(time)} x2={plotX(time)} y1={top} y2={bottom} />)}
          <path className="plot-signal" d={path} />
        </>
      )}
    </svg>
  )
}

export function Results({ lab }: { lab: Experiment }) {
  return (
    <div className="observations">
      <section className="observation" aria-labelledby="signal-title">
        <h2 id="signal-title">График колебаний</h2>
        <p>{lab.reading ? `${measuredPeriods} периодов за ${format(lab.reading.durationS * 1000, 2)} мс` : 'Смещение середины струны во времени'}</p>
        <SignalPlot pluck={lab.motion.current.pluck} reading={lab.reading} />
      </section>
      <section className="observation" aria-labelledby="results-title">
        <h2 id="results-title">Журнал опыта</h2>
        <p>{lab.results.length ? `Измерено сочетаний: ${lab.results.length} из 9` : 'Здесь можно сравнить показания датчика с расчётом'}</p>
        <table>
          <thead><tr><th scope="col">Струна, мм</th><th scope="col">Груз, г</th><th scope="col">Датчик, Гц</th><th scope="col">Расчёт, Гц</th></tr></thead>
          <tbody>
            {lab.results.length === 0 ? (
              <tr><td colSpan={4} className="empty-cell">Пока без измерений</td></tr>
            ) : lab.results.map(row => (
              <tr key={`${row.diameter}-${row.mass}`}>
                <td>{format(row.diameter, 1)}</td><td>{row.mass}</td>
                <td>{format(row.frequencyHz)}</td><td>{format(row.theoreticalHz)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  )
}
