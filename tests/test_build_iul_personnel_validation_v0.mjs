import assert from 'node:assert/strict'
import test from 'node:test'

import {
  classifyRole,
  extractRoster,
  isIulPdf,
  parseCsv,
} from '../tools/build_iul_personnel_validation_v0.mjs'


test('accepts only IUL PDF and rejects detached signatures', () => {
  assert.equal(isIulPdf('ИУЛ_003_АР.pdf'), true)
  assert.equal(isIulPdf('уил Раздел № 7 ПОКР.pdf'), true)
  assert.equal(isIulPdf('ИУЛ_003_АР.pdf.sig'), false)
  assert.equal(isIulPdf('Раздел АР.pdf'), false)
})

test('extracts role-separated roster entries', () => {
  const roster = extractRoster(`
    Разработал
    Левина П.А.
    ГИП
    Рузаев А.И.
    Н. контроль
    Рузаев А.И.
  `)
  assert.equal(roster.filter((row) => row.role_class === 'developer').length, 1)
  assert.equal(roster.filter((row) => row.role_class === 'gip').length, 1)
  assert.equal(roster.filter((row) => row.role_class === 'control').length, 1)
  assert.ok(roster.every((row) => /^[0-9a-f]{40}$/.test(row.person_hash)))
  assert.ok(roster.every((row) => /^[0-9a-f]{40}$/.test(row.surname_hash)))
})

test('extracts surname-only roster entries when role is explicit', () => {
  const roster = extractRoster(`
    Разработал
    Кузнецов
    Проверил
    Третьяков
  `)
  assert.equal(roster.filter((row) => row.role_class === 'developer').length, 1)
  assert.equal(roster.filter((row) => row.role_class === 'control').length, 1)
  assert.ok(roster.every((row) => row.person_key_kind === 'surname_only'))
})

test('extracts person when role follows the name', () => {
  const roster = extractRoster(`
    Аксенова
    ГИП
    02.12.2024
  `)
  assert.equal(roster.filter((row) => row.role_class === 'gip').length, 1)
})

test('classifies common IUL roles', () => {
  assert.equal(classifyRole('Разработал'), 'developer')
  assert.equal(classifyRole('ГИП'), 'gip')
  assert.equal(classifyRole('Н. контроль'), 'control')
  assert.equal(classifyRole('Утвердил'), 'approved')
})

test('parses quoted CSV', () => {
  const rows = parseCsv('a,b\r\n"x,y","z""q"\r\n')
  assert.deepEqual(rows, [{ a: 'x,y', b: 'z"q' }])
})
