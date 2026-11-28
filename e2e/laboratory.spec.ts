import { expect, test, type Page } from '@playwright/test'

const expected = [
  { button: '0,3 мм', x: -1.55, readings: [70.30, 99.42, 121.77] },
  { button: '0,4 мм', x: -0.40, readings: [52.73, 74.57, 91.33] },
  { button: '0,5 мм', x: 0.75, readings: [42.18, 59.65, 73.06] },
]

async function wirePoint(page: Page, worldX: number) {
  const canvas = page.locator('canvas')
  await expect(canvas).toBeVisible()
  const bounds = (await canvas.boundingBox())!
  const zoom = Math.min(bounds.width / 6.55, bounds.height / 4.72)
  return {
    x: bounds.x + bounds.width / 2 + (worldX - 0.46) * zoom,
    y: bounds.y + bounds.height / 2 - 0.31 * zoom,
  }
}

async function dragWire(page: Page, worldX: number) {
  const point = await wirePoint(page, worldX)
  await page.mouse.move(point.x, point.y)
  await page.mouse.down()
  await page.mouse.move(point.x + 29, point.y, { steps: 5 })
  await page.mouse.up()
}

async function showsMountedWeight(page: Page, worldX: number, index: number) {
  const canvas = page.locator('canvas')
  const { width, height } = (await canvas.boundingBox())!
  const zoom = Math.min(width / 6.55, height / 4.72)
  const x = Math.round(width / 2 + (worldX - 0.42) * zoom)
  const y = Math.round(height / 2 + (1.30 + index * 0.033) * zoom)
  const png = (await canvas.screenshot({ scale: 'css' })).toString('base64')
  return page.evaluate(async ({ png, x, y }) => {
    const image = await createImageBitmap(await (await fetch(`data:image/png;base64,${png}`)).blob())
    const target = new OffscreenCanvas(5, 5).getContext('2d')!
    target.drawImage(image, x - 2, y - 2, 5, 5, 0, 0, 5, 5)
    const pixels = target.getImageData(0, 0, 5, 5).data
    return pixels[48] > 85 && pixels[48] - pixels[50] > 40 && pixels[49] - pixels[50] > 15
  }, { png, x, y })
}

test('измеряет все девять сочетаний при прямом щипке', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto('/')
  await page.getByRole('switch', { name: 'Звук' }).click()
  const readout = page.getByTestId('frequency')

  for (const string of expected) {
    await page.getByRole('button', { name: string.button, exact: true }).click()
    for (const [index, mass] of [100, 200, 300].entries()) {
      const weight = page.getByRole('button', { name: `Груз ${mass} г`, exact: true })
      await weight.click()
      await expect(weight).toHaveAttribute('aria-pressed', 'true')
      await expect(readout).toHaveText('—')
      await dragWire(page, string.x)
      const hz = string.readings[index].toFixed(2).replace('.', ',')
      await expect(readout).toHaveText(hz, { timeout: 2500 })
      expect(await showsMountedWeight(page, string.x, index), `Груз ${mass} г под струной ${string.button}`).toBe(true)
      const row = page.getByRole('row').filter({ hasText: new RegExp(`${string.button.slice(0, 3)}\\s*${mass}`) })
      await expect(row.getByRole('cell').nth(2)).toHaveText(hz)
    }
  }
  await expect(page.getByText('Измерено сочетаний: 9 из 9')).toBeVisible()
  await expect(page.getByRole('img', { name: /границы пяти периодов/ })).toBeVisible()
  expect(errors).toEqual([])
})

test('груз можно выбрать прямо в лотке, а ракурс вернуть', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/')
  const canvas = page.locator('canvas')
  await expect(canvas).toBeVisible()
  await page.waitForTimeout(350)
  const bounds = (await canvas.boundingBox())!
  const zoom = Math.min(bounds.width / 6.55, bounds.height / 4.72)
  const initial = await canvas.screenshot()
  await page.mouse.click(bounds.x + bounds.width / 2 + 1.85 * zoom, bounds.y + bounds.height / 2 + 1.9 * zoom)
  await expect(page.getByRole('button', { name: 'Груз 200 г', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await page.mouse.move(1, 1)
  const withWeight = await canvas.screenshot()
  expect(withWeight.equals(initial)).toBe(false)

  await page.mouse.move(bounds.x + bounds.width * 0.81, bounds.y + bounds.height * 0.34)
  await page.mouse.down()
  await page.mouse.move(bounds.x + bounds.width * 0.87, bounds.y + bounds.height * 0.38, { steps: 7 })
  await page.mouse.up()
  await page.waitForTimeout(350)
  expect((await canvas.screenshot()).equals(withWeight)).toBe(false)
  await page.getByRole('button', { name: 'Сбросить ракурс' }).click()
  await page.mouse.move(1, 1)
  await expect.poll(async () => (await canvas.screenshot()).equals(withWeight)).toBe(true)
})

test('секундомер идёт по времени модели, звук сохраняет физическую частоту', async ({ page }) => {
  await page.addInitScript(() => {
    const calls: { frequency: number; wave: string }[] = []
    Object.assign(window, { audioCalls: calls })
    const create = AudioContext.prototype.createOscillator
    AudioContext.prototype.createOscillator = function () {
      const oscillator = create.call(this)
      const set = oscillator.frequency.setValueAtTime.bind(oscillator.frequency)
      oscillator.frequency.setValueAtTime = (frequency, time) => {
        calls.push({ frequency, wave: oscillator.type })
        return set(frequency, time)
      }
      return oscillator
    }
  })
  await page.goto('/')
  const tones = () => page.evaluate(() => (window as Window & {
    audioCalls?: { frequency: number; wave: string }[]
  }).audioCalls)
  const readout = page.getByTestId('frequency')
  const slowdown = page.getByRole('switch', { name: 'Замедление ×40' })
  const sound = page.getByRole('switch', { name: 'Звук' })
  const pluck = page.getByRole('button', { name: 'Щипнуть струну' })

  await expect(pluck).toBeDisabled()
  await page.getByRole('button', { name: 'Груз 300 г', exact: true }).click()
  await pluck.focus()
  await page.keyboard.press('Enter')
  await expect(readout).toHaveText('121,77')
  await slowdown.click()
  await page.getByRole('button', { name: 'Пуск', exact: true }).click()
  await pluck.click()
  await expect(page.getByText('Измеряет пять периодов…')).toBeVisible()
  await page.waitForTimeout(550)
  await page.getByRole('button', { name: 'Стоп', exact: true }).click()
  const stopwatch = page.getByTestId('stopwatch')
  const stoppedValue = Number((await stopwatch.innerText()).replace(',', '.'))
  expect(stoppedValue).toBeGreaterThan(0.01)
  expect(stoppedValue).toBeLessThan(0.16)
  await expect(readout).toHaveText('121,77', { timeout: 7000 })
  expect(await tones()).toEqual([
    { frequency: expect.closeTo(121.767, 2), wave: 'triangle' },
    { frequency: expect.closeTo(121.767, 2), wave: 'triangle' },
  ])
  await page.getByRole('button', { name: 'Сброс', exact: true }).click()
  await expect(stopwatch).toHaveText('0,000')

  await sound.click()
  await slowdown.click()
  await pluck.click()
  await expect(readout).toHaveText('121,77')
  expect(await tones()).toHaveLength(2)
  await page.getByRole('button', { name: '0,4 мм', exact: true }).click()
  await expect(readout).toHaveText('—')
  await expect(page.getByText('Измерено сочетаний: 1 из 9')).toBeVisible()
})

test('опыт работает касанием на узком экране', async ({ browser, baseURL }) => {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true })
  try {
    await page.goto(baseURL!)
    await page.getByRole('switch', { name: 'Звук' }).tap()
    await page.getByRole('button', { name: 'Груз 100 г', exact: true }).tap()
    await page.locator('canvas').scrollIntoViewIfNeeded()
    const point = await wirePoint(page, -1.55)
    const cdp = await page.context().newCDPSession(page)
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [point] })
    for (const dx of [5, 12, 18, 23]) {
      await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: point.x + dx, y: point.y }] })
    }
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
    await expect(page.getByTestId('frequency')).toHaveText('70,30')
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390)
  } finally {
    await page.close()
  }
})
