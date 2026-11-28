import { createRoot } from 'react-dom/client'
import { massesG, strings } from './physics/string'
import { Bench } from './scene/Bench'
import { Results, format } from './Results'
import { useExperiment, type Experiment } from './useExperiment'
import './style.css'

function Instruments({ lab }: { lab: Experiment }) {
  const { phase, reading, watchS, watchRunning, toggleWatch, resetWatch } = lab
  const status = phase === 'measuring'
    ? 'Измеряет пять периодов…'
    : phase === 'measured' ? 'Измерение завершено' : lab.mass === null ? 'Ожидает груз на струне' : 'Готов к измерению'

  return (
    <aside className="instruments" aria-label="Измерительные приборы">
      <div className="instrument">
        <h2>Частотомер</h2>
        <div className="readout" role="status" aria-label="Измеренная частота">
          <span data-testid="frequency">{reading ? format(reading.frequencyHz) : '—'}</span>
          <span className="unit">Гц</span>
        </div>
        <p className="sensor-status" data-phase={phase}><i aria-hidden="true" />{status}</p>
      </div>
      <div className="instrument">
        <h2>Секундомер</h2>
        <div className="readout watch" aria-label="Время модели">
          <span data-testid="stopwatch">{format(watchS, 3)}</span><span className="unit">с</span>
        </div>
        <div className="watch-actions">
          <button type="button" onClick={toggleWatch}>{watchRunning ? 'Стоп' : 'Пуск'}</button>
          <button type="button" onClick={resetWatch}>Сброс</button>
        </div>
        <p className="watch-note">Время модели учитывает замедление</p>
      </div>
    </aside>
  )
}

function App() {
  const lab = useExperiment()
  return (
    <main className="page" data-enter>
      <header className="page-header">
        <div>
          <p className="context">Виртуальная лаборатория</p>
          <h1>Стоячие волны<br className="title-break" /> на струне</h1>
        </div>
        <p className="purpose">Исследуй, как масса груза и толщина струны влияют на частоту колебаний.</p>
      </header>
      <section className="laboratory" aria-label="Лабораторная установка" data-moment="instrument">
        <div className="lab-tools">
          <span className="stage-title">Установка</span>
          <div className="toggles">
            <button type="button" role="switch" aria-checked={lab.slow} onClick={lab.changeSpeed}>
              <span className="toggle-indicator" aria-hidden="true" /> Замедление ×40
            </button>
            <button type="button" role="switch" aria-checked={lab.sound} onClick={lab.changeSound}>
              <span className="toggle-indicator" aria-hidden="true" /> Звук
            </button>
          </div>
        </div>
        <div className="stage">
          <Instruments lab={lab} />
          <Bench lab={lab} />
        </div>
        <div className="experiment-controls">
          <fieldset>
            <legend>Диаметр стальной струны</legend>
            <div className="choices">
              {strings.map(diameter => (
                <button key={diameter} type="button" aria-pressed={lab.diameter === diameter}
                  onClick={() => lab.selectString(diameter)}>{format(diameter, 1)} мм</button>
              ))}
            </div>
          </fieldset>
          <fieldset>
            <legend>Груз на крючке</legend>
            <div className="choices">
              {massesG.map(mass => (
                <button key={mass} type="button" aria-pressed={lab.mass === mass} aria-label={`Груз ${mass} г`}
                  onClick={() => lab.mountWeight(lab.mass === mass ? null : mass)}>{mass} г</button>
              ))}
            </div>
          </fieldset>
          <button type="button" className="pluck-button" disabled={lab.mass === null} onClick={() => lab.pluck()}>
            Щипнуть струну <span aria-hidden="true">↗</span>
          </button>
        </div>
        <p className="instructions">Выбери струну и груз. Потяни струну вбок за середину и отпусти.</p>
      </section>
      <Results lab={lab} />
    </main>
  )
}

createRoot(document.getElementById('root')!).render(<App />)
